"""Bot 配置的共享知识与安全读写原语。

Bot（启动时读取、群开关写回）和部署面板（离线编辑）需要同一份配置知识：
配置文件清单、bot.toml 的字段约定，以及不留下半写文件的替换操作。
本模块是唯一来源，只依赖标准库和 tomlkit，不 import 任何一侧。
"""

import os
import stat
import tempfile
from pathlib import Path

import tomlkit
from tomlkit.exceptions import ParseError

CONFIG_FILES = ("bot.toml", "plugins.toml", "groups.toml", "ai.toml", "scheduler.toml")

# bot.toml 字段约定：section -> key -> (类型, 启动是否必需)。
# 面板据此拒绝白名单之外的表单修改并校验类型；Bot 在必需字段缺失时拒绝启动。
BOT_SCHEMA = {
    "Init": {
        "server_address": (str, True),
        "client_address": (str, True),
        "bot_name": (str, True),
        "debug": (bool, True),
        "database_enable": (bool, True),
        "database_username": (str, True),
        "database_address": (str, True),
        "database_passwd": (str, True),
        "database_name": (str, True),
        "owner_id": (int, True),
        "assistant_group": (int, True),
        "enable_webhook_handler": (bool, True),
    },
    "Gitea": {
        "webhook_handler_address": (str, True),
        "webhook_response_group": (int, True),
        "api_url": (str, True),
        "api_token": (str, True),
    },
}


def load_toml(path):
    """解析 TOML 文件；语法或编码问题转成可读的 ValueError。

    返回 tomlkit 文档，写回的调用方因此保留注释与排版。异常消息只含位置、
    不含解析器原文——后者可能携带源文件行（含密码）。
    """
    try:
        with open(path, encoding="utf-8") as f:
            return tomlkit.load(f)
    except ParseError as exc:
        line, col = getattr(exc, "line", None), getattr(exc, "col", None)
        where = f"（第 {line} 行，第 {col} 列）" if line else ""
        raise ValueError(f"{Path(path).name} 语法错误{where}，请检查格式") from None
    except UnicodeError:
        raise ValueError(f"{Path(path).name} 必须采用 UTF-8 编码") from None


def atomic_write(path: Path, source: str, mode: int = 0o600) -> None:
    """原子替换文件内容：同目录临时文件 + fsync + rename，不留半写状态。

    已存在的文件保留原有权限位；新建文件用 `mode`。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        current = stat.S_IMODE(path.stat().st_mode)
    except OSError:
        current = mode
    descriptor, temporary = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as output:
            output.write(source)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, current)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
