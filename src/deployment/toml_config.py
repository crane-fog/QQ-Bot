"""Offline, allowlisted Bot configuration editing shared by both deployment modes."""

import difflib
import hashlib
import math
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

import tomlkit
from tomlkit.exceptions import ParseError

from ..config_schema import BOT_SCHEMA, CONFIG_FILES
from .config import MAX_SOURCE, DeploymentError, atomic_write

CONFIG_NAMES = CONFIG_FILES
BOT_FIELDS = {
    section: {key: expected for key, (expected, _) in fields.items()}
    for section, fields in BOT_SCHEMA.items()
}


def form_values(value):
    """JSON projection only; the original TOML remains the source of truth."""
    if isinstance(value, dict):
        return {key: form_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [form_values(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


class ConfigStore:
    def __init__(self, root: Path, state: Path):
        self.root = root.resolve()
        self.state = state.resolve()

    def path(self, name):
        if name not in CONFIG_NAMES:
            raise DeploymentError("不支持的配置文件", 404)
        path = self.root / "configs" / name
        if path.is_symlink() or path.parent.is_symlink() or path.parent.is_junction():
            raise DeploymentError("配置目录或文件不能是链接")
        if path.resolve().parent != self.root / "configs":
            raise DeploymentError("配置路径超出部署目录")
        return path

    def source(self, name):
        path = self.path(name)
        if not path.exists():
            return None
        if not path.is_file() or path.stat().st_size > MAX_SOURCE:
            raise DeploymentError("配置文件不可读取或超过 1 MiB")
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeError:
            raise DeploymentError("配置必须采用 UTF-8 编码") from None
        except OSError:
            raise DeploymentError("读取配置失败，请检查文件权限", 500) from None

    @staticmethod
    def version(source):
        # Missing and an existing empty file must have distinct revisions.
        return hashlib.sha256(
            ("missing" if source is None else "present:" + source).encode()
        ).hexdigest()

    def read(self, name):
        source = self.source(name)
        result = {
            "name": name,
            "source": source or "",
            "exists": source is not None,
            "version": self.version(source),
            "values": None,
            "error": None,
        }
        try:
            result["values"] = form_values(self.validate(name, source or "").unwrap())
        except DeploymentError as exc:
            result["error"] = str(exc)
        return result

    def check_version(self, name, version):
        source = self.source(name)
        if self.version(source) != version:
            raise DeploymentError("配置已被其他操作修改，请重新读取并比较草稿", 409)
        return source

    def validate(self, name, source):
        self.path(name)
        if len(source.encode("utf-8")) > MAX_SOURCE:
            raise DeploymentError("配置超过 1 MiB")
        try:
            document = tomlkit.parse(source)
            values = document.unwrap()
        except (ParseError, ValueError, RecursionError):
            # Parser exceptions can include source lines containing secrets.
            raise DeploymentError("TOML 格式错误，请检查语法；草稿已保留") from None
        if name == "bot.toml":
            for section, fields in BOT_FIELDS.items():
                table = values.get(section)
                if not isinstance(table, dict):
                    raise DeploymentError(f"缺少配置表 {section}")
                for key, expected in fields.items():
                    if type(table.get(key)) is not expected:
                        raise DeploymentError(f"{section}.{key} 缺失或类型错误")
                    if key.endswith("address"):
                        address = table[key]
                        host, sep, port = address.rpartition(":")
                        if not sep or not host or not port.isdigit() or not 1 <= int(port) <= 65535:
                            raise DeploymentError(f"{section}.{key} 应为主机:端口")
        elif name in {"plugins.toml", "groups.toml", "scheduler.toml"}:
            for key, table in values.items():
                if not isinstance(table, dict):
                    raise DeploymentError("配置顶层必须为表")
                if name == "groups.toml":
                    if not key.isdigit() or not all(
                        type(value) is bool for value in table.values()
                    ):
                        raise DeploymentError("群号必须为数字，插件开关必须为布尔值")
                else:
                    if "enable" in table and type(table["enable"]) is not bool:
                        raise DeploymentError("enable 必须为布尔值")
                    if (
                        name == "scheduler.toml"
                        and "kwargs" in table
                        and not isinstance(table["kwargs"], dict)
                    ):
                        raise DeploymentError("kwargs 必须为表")
        else:
            for key in ("provider", "profile", "tool"):
                if key in values and (
                    not isinstance(values[key], dict)
                    or not all(isinstance(value, dict) for value in values[key].values())
                ):
                    raise DeploymentError(f"{key} 必须包含具名配置表")
        return document

    def patch(self, name, source, changes):
        document = self.validate(name, source)
        for change in changes:
            path = change["path"]
            if not path or len(path) > 3 or not all(isinstance(key, str) and key for key in path):
                raise DeploymentError("表单字段路径无效")
            if name == "bot.toml":
                if len(path) != 2 or path[1] not in BOT_FIELDS.get(path[0], {}):
                    raise DeploymentError("不支持的表单字段")
            elif name == "plugins.toml":
                if len(path) != 2 or path[1] != "enable" or path[0] not in document:
                    raise DeploymentError("不支持的插件开关")
            elif name == "groups.toml":
                if len(path) not in {1, 2} or not path[0].isdigit():
                    raise DeploymentError("群聊配置路径无效")
            else:
                raise DeploymentError("此配置请使用完整 TOML 编辑")
            current = document
            for key in path[:-1]:
                if key not in current:
                    current[key] = tomlkit.table()
                current = current[key]
            if change.get("delete", False):
                current.pop(path[-1], None)
            else:
                value = change.get("value")
                if value is None:
                    raise DeploymentError("TOML 表单不支持空值")
                if name == "bot.toml" and type(value) is not BOT_FIELDS[path[0]][path[1]]:
                    raise DeploymentError("表单字段类型错误")
                if name == "plugins.toml" and type(value) is not bool:
                    raise DeploymentError("插件开关必须为布尔值")
                if name == "groups.toml" and (
                    (len(path) == 1 and value != {}) or (len(path) == 2 and type(value) is not bool)
                ):
                    raise DeploymentError("新群配置必须为空表，插件开关必须为布尔值")
                current[path[-1]] = value
        result = tomlkit.dumps(document)
        self.validate(name, result)
        return result

    def diff(self, name, source):
        return "".join(
            difflib.unified_diff(
                (self.source(name) or "").splitlines(True),
                source.splitlines(True),
                fromfile="当前文件",
                tofile="草稿",
            )
        )

    def backup_directory(self, name):
        self.path(name)
        directory = self.state / "config-backups" / name
        if directory.resolve() != self.state / "config-backups" / name:
            raise DeploymentError("备份目录不能是链接")
        return directory

    def save(self, name, source, version):
        self.validate(name, source)
        current = self.check_version(name, version)
        if source != current:
            try:
                if current is not None:
                    backup = (
                        datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
                        + "-"
                        + uuid.uuid4().hex
                        + ".toml"
                    )
                    atomic_write(self.backup_directory(name) / backup, current)
                self.check_version(name, version)
                atomic_write(self.path(name), source)
            except OSError:
                raise DeploymentError("写入配置失败，请检查目录权限；原文件未被覆盖", 500) from None
        return self.read(name)

    def backups(self, name):
        directory = self.backup_directory(name)
        return [
            {"id": path.name, "size": path.stat().st_size}
            for path in sorted(directory.glob("*.toml"), reverse=True)
            if not path.is_symlink()
        ]

    def backup_source(self, name, backup):
        if not re.fullmatch(r"\d{8}T\d{6}-[a-f0-9]{32}\.toml", backup):
            raise DeploymentError("无效的备份标识", 404)
        path = self.backup_directory(name) / backup
        if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_SOURCE:
            raise DeploymentError("备份不存在或不可读取", 404)
        return path.read_text(encoding="utf-8")
