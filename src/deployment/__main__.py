import argparse
import asyncio
import getpass
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from . import default_source_root
from .auth import create_credentials
from .config import ComposeDocument, DeploymentError, atomic_write
from .runtime import detect_runtime, serve
from .setup import discover_project, initialize, initialize_source, print_initial_password


def process_alive(pid):
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_uint32]
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def pid_record(root):
    return root / ".webcontroller" / "panel.pid"


def start_background(root, port):
    state = root / ".webcontroller"
    if not state.is_dir():
        raise SystemExit("状态目录不存在，请先执行 --init 初始化")
    record = pid_record(root)
    if record.is_file():
        recorded = record.read_text(encoding="utf-8").strip()
        if recorded.isdigit() and process_alive(int(recorded)):
            raise SystemExit(f"面板已在后台运行（PID {recorded}），如需重启请先执行 --stop")
        record.unlink()
    log_path = state / "panel.log"
    # -m resolves the package through sys.path, so the child must run with the
    # deploy root as cwd; an arbitrary caller cwd would not find it.
    command = [
        sys.executable,
        "-m",
        "src.deployment",
        "--root",
        str(root),
        "--port",
        str(port),
    ]
    flags = (
        {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    with open(log_path, "ab") as log:
        child = subprocess.Popen(
            command,
            cwd=default_source_root(),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            **flags,
        )
    record.write_text(str(child.pid) + "\n", encoding="utf-8")
    time.sleep(1)
    if child.poll() is not None:
        record.unlink(missing_ok=True)
        raise SystemExit(f"后台面板启动失败，请查看日志：{log_path}")
    print(f"面板已在后台运行（PID {child.pid}）")
    print(f"日志：{log_path}")
    print("停止：uv run -m src.deployment --stop")
    print_initial_password(root)
    return child


def stop_background(root):
    record = pid_record(root)
    if not record.is_file():
        print("没有正在后台运行的面板")
        return
    pid = int(record.read_text(encoding="utf-8").strip())
    if not process_alive(pid):
        record.unlink()
        print(f"记录的 PID {pid} 已退出，清理残留记录")
        return
    if os.name == "nt":
        # /T kills the supervised Bot child along with the panel.
        finished = subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        if finished.returncode != 0:
            detail = (finished.stderr or finished.stdout).decode(errors="replace").strip()
            raise SystemExit(f"停止失败：{detail}")
    else:
        os.kill(pid, signal.SIGTERM)
    record.unlink(missing_ok=True)
    print(f"已停止后台面板（PID {pid}）")


def prompt_password(text, explicit):
    if explicit is not None:
        return explicit
    password = getpass.getpass(text)
    if password != getpass.getpass("再次输入密码: "):
        raise DeploymentError("两次密码不一致")
    return password


def run_setup(root, mode, args, parser):
    if mode == "source":
        if args.accept_panel_upgrade or args.project_name:
            parser.error("源码模式不接受 Compose 维护参数")
        if args.reset_password:
            settings_path = root / ".webcontroller" / "settings.json"
            if not settings_path.is_file():
                raise DeploymentError("面板尚未初始化，请先执行 --init")
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            if settings.get("root") != str(root):
                raise DeploymentError(
                    f"状态目录记录的部署目录为 {settings.get('root')!r}，与当前 {str(root)!r} 不同"
                )
            password = prompt_password("新管理员密码: ", args.password)
            atomic_write(
                root / ".webcontroller/credentials.json", json.dumps(create_credentials(password))
            )
            (root / ".webcontroller/initial-password").unlink(missing_ok=True)
            print("管理员密码已重置，重启面板后使用新密码登录")
            return
        initialize_source(root, args.password)
        print("源码面板初始化完成，执行 uv run -m src.deployment 启动面板和 Bot")
        print_initial_password(root)
        return
    project = discover_project(root, args.project_name)
    # Explicit host-side maintenance commands; never exposed through the web API.
    state = root / ".webcontroller"
    settings_path = state / "settings.json"
    if settings_path.exists():
        existing = json.loads(settings_path.read_text(encoding="utf-8"))
        if existing.get("root") != str(root):
            raise DeploymentError(
                f"状态目录记录的部署目录为 {existing.get('root')!r}，与当前 {str(root)!r} 不同"
            )
        if existing.get("project", project) != project:
            raise DeploymentError(
                f"状态目录记录的 Compose 项目名为 {existing.get('project')!r}，与当前 {project!r} 不同"
            )
    if args.reset_password:
        if not settings_path.exists():
            raise DeploymentError("面板尚未初始化，请先执行 --init")
        password = prompt_password("新管理员密码: ", args.password)
        atomic_write(state / "credentials.json", json.dumps(create_credentials(password)))
        (state / "initial-password").unlink(missing_ok=True)
        print("管理员密码已重置，重启面板后使用新密码登录")
        return
    if args.accept_panel_upgrade:
        protected = ComposeDocument.protection(
            ComposeDocument.decode((root / "compose.yaml").read_text(encoding="utf-8"))
        )
        atomic_write(state / "protected.json", json.dumps(protected, ensure_ascii=False))
    initialize(root, project, args.password)
    print(f"面板初始化完成，Compose 项目：{project}")
    print("执行 docker compose up -d 后访问 http://127.0.0.1:7001")
    print_initial_password(root)


def main():
    parser = argparse.ArgumentParser(description="Theresa 部署面板：面板拉起并守护 Bot")
    parser.add_argument("--root", type=Path, help="源码模式的检出目录，默认取包所在仓库")
    parser.add_argument("--port", type=int, default=7001)
    parser.add_argument("--bg", action="store_true", help="以后台进程运行，日志写入状态目录")
    parser.add_argument("--stop", action="store_true", help="停止后台运行的面板")
    parser.add_argument("--init", action="store_true", help="初始化部署身份与配置后退出")
    parser.add_argument("--reset-password", action="store_true", help="重置管理员密码后退出")
    parser.add_argument("--password", help="与 --init 或 --reset-password 搭配，非交互指定密码")
    parser.add_argument("--project-name", help="Compose 项目名，覆盖从 compose.yaml 推断的名称")
    parser.add_argument(
        "--accept-panel-upgrade", action="store_true", help="重新登记面板服务保护配置"
    )
    args = parser.parse_args()
    if args.init and args.reset_password:
        parser.error("--init 不能与 --reset-password 同时使用")
    setup_mode = args.init or args.reset_password or args.accept_panel_upgrade
    if setup_mode and (args.bg or args.stop):
        parser.error("初始化或维护模式不能与 --bg/--stop 同时使用")
    if args.password is not None and not setup_mode:
        parser.error("--password 需要与 --init 或 --reset-password 搭配")
    if not 1 <= args.port <= 65535:
        parser.error("端口必须在 1 到 65535 之间")
    root, mode = detect_runtime(args.root)
    if args.stop:
        stop_background(root)
        return
    if mode == "compose" and not root.is_dir():
        raise SystemExit(
            f"部署目录不存在：{root}。容器部署默认使用 /deploy 挂载，"
            "源码部署可用 --root 指定检出目录"
        )
    if args.bg:
        start_background(root, args.port)
        return
    if setup_mode:
        run_setup(root, mode, args, parser)
        return
    try:
        asyncio.run(serve(args.port, root, mode))
    except DeploymentError as exc:
        raise SystemExit(f"初始化失败：{exc}") from None


if __name__ == "__main__":
    main()
