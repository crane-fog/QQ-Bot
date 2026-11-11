"""Initialize standalone source or Compose panel credentials and deployment identity."""

import json
import os
import re
from pathlib import Path

from .auth import create_credentials, generate_password
from .config import ComposeDocument, DeploymentError, atomic_write, plain
from .toml_config import CONFIG_NAMES, ConfigStore


def initialize_source(root: Path, password=None):
    root = root.resolve()
    state = root / ".webcontroller"
    settings = {"root": str(root)}
    settings_path = state / "settings.json"
    if settings_path.exists():
        existing = json.loads(settings_path.read_text(encoding="utf-8"))
        if existing.get("root") != settings["root"]:
            raise DeploymentError(
                f"已初始化的部署目录不同：状态记录 {existing.get('root')!r}，当前 {settings['root']!r}"
            )
    store = ConfigStore(root, state)
    missing = []
    for name in CONFIG_NAMES:
        path = store.path(name)
        if not path.exists():
            template = path.with_suffix(path.suffix + ".template")
            if not template.is_file() or template.is_symlink():
                raise DeploymentError(f"缺少配置模板：{name}.template")
            missing.append((path, template.read_text(encoding="utf-8")))
    credentials = state / "credentials.json"
    if not credentials.exists():
        if password is None:
            password = generate_password()
            atomic_write(state / "initial-password", password + "\n")
        atomic_write(credentials, json.dumps(create_credentials(password)))
    for path, source in missing:
        atomic_write(path, source)
    atomic_write(settings_path, json.dumps(settings))
    if os.name != "nt":
        state.chmod(0o700)
    return store


def discover_project(root: Path, explicit=None):
    """Derive the Compose project name from compose.yaml, .env, or the directory name."""
    root = root.resolve()
    if explicit:
        project = explicit
    else:
        compose_path = root / "compose.yaml"
        if not compose_path.is_file():
            raise DeploymentError(f"部署目录缺少 compose.yaml：{root}")
        name = plain(ComposeDocument.decode(compose_path.read_text(encoding="utf-8"))).get("name")
        env_path = root / ".env"
        if env_path.is_file():
            match = re.search(
                r"^\s*(?:export\s+)?COMPOSE_PROJECT_NAME\s*=\s*(.*?)\s*$",
                env_path.read_text(encoding="utf-8"),
                re.M,
            )
            if match:
                name = match.group(1).strip("\"'")
        if name and "$" in name:
            raise DeploymentError("Compose 项目名称包含变量，请使用 --project-name 明确指定")
        project = name or re.sub(r"[^a-z0-9_-]", "", root.name.lower()).lstrip("_-")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", project):
        raise DeploymentError("无法确定合法的 Compose 项目名称，请使用 --project-name")
    return project


def initialize(root: Path, project: str, password=None):
    root = root.resolve()
    state = root / ".webcontroller"
    settings_path = state / "settings.json"
    settings = {"root": str(root), "project": project}
    if settings_path.exists():
        existing = json.loads(settings_path.read_text(encoding="utf-8"))
        if existing.get("root") != str(root):
            raise DeploymentError(
                f"已初始化的部署目录不同：状态记录 {existing.get('root')!r}，当前 {str(root)!r}"
            )
        if existing.get("project", project) != project:
            raise DeploymentError(
                f"已初始化的 Compose 项目名不同：状态记录 {existing.get('project')!r}，当前 {project!r}"
            )
    document = ComposeDocument(root, state)
    document.parse(document.source())
    credentials = state / "credentials.json"
    if not credentials.exists():
        if password is None:
            password = generate_password()
            atomic_write(state / "initial-password", password + "\n")
        atomic_write(credentials, json.dumps(create_credentials(password)))
    atomic_write(settings_path, json.dumps(settings))
    for directory in (state, state / "backups"):
        directory.mkdir(exist_ok=True, mode=0o700)
        directory.chmod(0o700)
    return document


def print_initial_password(root: Path):
    initial = root / ".webcontroller" / "initial-password"
    if initial.exists():
        print(f"初始管理员密码已生成：{initial}")
        print("首次成功登录后面板会删除该文件；请尽快用 --reset-password 修改密码。")
