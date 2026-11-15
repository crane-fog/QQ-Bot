"""Daemon-first runtime: a supervisor owns both the panel and the Bot.

``python main.py`` is a thin root launcher that starts the daemon (``python -m
src.deployment``) as a process-group leader and mirrors its exit code. The daemon
holds the signal handlers and supervises two child applications: the HTTP panel
(``--panel``) and the Bot. A panel crash never stops the Bot and a Bot crash never
stops the panel; the daemon restarts either with exponential backoff. Reloading
the panel is just the daemon restarting the panel child, leaving the Bot running.
``bot.py`` still runs the Bot alone, without the daemon or panel.
"""

import asyncio
import ipaddress
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import uvicorn

from . import default_source_root
from .app import create_app
from .config import ComposeDocument
from .runner import ComposeRunner
from .setup import (
    discover_project,
    initialize,
    initialize_source,
    print_initial_password,
    read_settings,
)
from .toml_config import ConfigStore

PANEL_DEPLOY_MOUNT = "/deploy"


def detect_runtime(root=None):
    """A /deploy bind mount means the Compose deployment; otherwise run on the checkout.

    The mount also fixes the deploy root, so ``root`` only applies to source runs.
    """
    deploy = Path(PANEL_DEPLOY_MOUNT)
    if deploy.is_dir() and (deploy / "compose.yaml").is_file():
        return deploy.resolve(), "compose"
    return Path(root or default_source_root()).resolve(), "source"


def build_app(root, mode=None, bot_control=None, *, host=None):
    root = Path(root).resolve()
    if mode is None:
        _, mode = detect_runtime(root)
    state = root / ".webcontroller"
    settings = json.loads((state / "settings.json").read_text(encoding="utf-8"))
    if settings.get("root") != str(root):
        raise RuntimeError(
            f"部署目录与初始化记录不一致：状态记录 {settings.get('root')!r}，当前为 {str(root)!r}"
        )
    credentials = json.loads((state / "credentials.json").read_text(encoding="utf-8"))
    if mode == "source":
        return create_app(
            None,
            None,
            credentials,
            configs=ConfigStore(root, state),
            bot_control=bot_control,
            host=host,
        )
    document = ComposeDocument(root, state)
    runner = ComposeRunner(root, settings["project"])
    return create_app(document, runner, credentials, bot_control=bot_control, host=host)


def prepare(root, mode, control=None, host=None):
    """Auto-initialize on first run, then build the app."""
    root = Path(root).resolve()
    if not (root / ".webcontroller" / "settings.json").is_file():
        if mode == "source":
            initialize_source(root, None)
        else:
            initialize(root, discover_project(root), None)
        print_initial_password(root)
    return build_app(root, host=host)


def _notify(message):
    print(message, flush=True)


def resolve_panel_bind(root, mode, host=None, port=None):
    """解析面板绑定地址：命令行 > 持久化设置 > 部署默认。

    持久化值来自 .webcontroller/settings.json 的 panel_host/panel_port；
    缺失或非法时回退默认（源码回环、容器全接口，端口 7001）。
    """
    settings = read_settings(Path(root) / ".webcontroller")
    if host is None:
        persisted_host = settings.get("panel_host")
        host = persisted_host if isinstance(persisted_host, str) and persisted_host else None
    if port is None:
        persisted_port = settings.get("panel_port")
        if isinstance(persisted_port, int) and 1 <= persisted_port <= 65535:
            port = persisted_port
    if host is None:
        host = "127.0.0.1" if mode == "source" else "0.0.0.0"
    if port is None:
        port = 7001
    return host, port


async def run_panel(root, mode, host=None, port=None):
    """面板子进程入口：构建并服务 HTTP 面板，直到收到停机信号。

    绑定地址经 resolve_panel_bind 解析（命令行 > 持久化 > 默认）。面板异常只记录
    日志并以非零码退出，由守护进程退避重启；Bot 不受影响。
    """
    root = Path(root).resolve()
    bind, port = resolve_panel_bind(root, mode, host, port)
    try:
        app = prepare(root, mode, host=bind)
        config = uvicorn.Config(
            app,
            host=bind,
            port=port,
            access_log=False,
            proxy_headers=False,
        )
        await uvicorn.Server(config).serve()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        kind = type(exc).__name__
        _notify(f"WebController 面板异常退出，Bot 不受影响（{kind}）：{exc}")
        raise SystemExit(1) from None


class BotControl:
    """Shared handle between the supervisor and the panel API.

    ``stop`` shuts the supervisor down; ``restart`` asks for an immediate child
    restart that skips the backoff (used by the "重启 Bot" panel action).
    """

    def __init__(self):
        self.stop = asyncio.Event()
        self.restart = asyncio.Event()
        self.process = None


class PanelControl:
    """Daemon-side handle for the panel child.

    ``stop`` shuts the panel supervisor down; ``reload`` asks for an immediate
    panel restart that skips the backoff (used by the "重载面板" panel action).
    """

    def __init__(self):
        self.stop = asyncio.Event()
        self.reload = asyncio.Event()
        self.process = None


async def supervise_child(
    control,
    command,
    cwd,
    label,
    restart_event,
    backoff_start=1.0,
    backoff_cap=600.0,
    reset_after=60.0,
):
    """Run a child application and restart it with exponential backoff.

    A child that stayed up for `reset_after` seconds counts as stable and the
    next crash restarts at `backoff_start` again; a restart request bypasses
    the backoff entirely. Shared by the Bot and panel supervisors.
    """
    stop = control.stop
    backoff = backoff_start
    while not stop.is_set():
        started = asyncio.get_running_loop().time()
        try:
            process = await asyncio.create_subprocess_exec(*command, cwd=cwd)
        except OSError as exc:
            _notify(f"无法启动 {label} 进程，放弃拉起：{exc}")
            return
        control.process = process
        _notify(f"{label} 进程已启动（PID {process.pid}）")
        waiter = asyncio.create_task(process.wait())
        stopper = asyncio.create_task(stop.wait())
        restarter = asyncio.create_task(restart_event.wait())
        await asyncio.wait({waiter, stopper, restarter}, return_when=asyncio.FIRST_COMPLETED)
        stopper.cancel()
        restarter.cancel()
        requested = restart_event.is_set()
        if (stop.is_set() or requested) and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except TimeoutError:
                process.kill()
                await process.wait()
        code = await waiter
        restart_event.clear()
        if stop.is_set():
            return
        if requested:
            # 配置应用类重启：立即拉起，退避归零。
            backoff = backoff_start
            continue
        if asyncio.get_running_loop().time() - started >= reset_after:
            backoff = backoff_start
        _notify(f"{label} 进程退出（exit {code}），{backoff:g} 秒后重启")
        waiters = [asyncio.create_task(stop.wait()), asyncio.create_task(restart_event.wait())]
        try:
            await asyncio.wait(waiters, timeout=backoff, return_when=asyncio.FIRST_COMPLETED)
        finally:
            # asyncio.wait 超时不会取消传入的任务；不取消则每次崩溃重启都留下挂起任务。
            for waiter in waiters:
                waiter.cancel()
            await asyncio.gather(*waiters, return_exceptions=True)
        backoff = min(backoff * 2, backoff_cap)


async def supervise_bot(
    control, command, cwd, backoff_start=1.0, backoff_cap=600.0, reset_after=60.0
):
    """Supervise the Bot child (backoff restart, stable-run reset)."""
    await supervise_child(
        control,
        command,
        cwd,
        "Bot",
        control.restart,
        backoff_start=backoff_start,
        backoff_cap=backoff_cap,
        reset_after=reset_after,
    )


async def supervise_panel(
    control, command, cwd, backoff_start=1.0, backoff_cap=60.0, reset_after=60.0
):
    """Supervise the panel child; a reload request restarts it immediately."""
    await supervise_child(
        control,
        command,
        cwd,
        "面板",
        control.reload,
        backoff_start=backoff_start,
        backoff_cap=backoff_cap,
        reset_after=reset_after,
    )


def panel_command(root, mode, host, port):
    """构造面板子进程命令行（显式传入解析后的绑定，确保守护与面板一致）。"""
    command = [
        sys.executable,
        "-m",
        "src.deployment",
        "--panel",
        "--root",
        str(root),
        "--host",
        host,
        "--port",
        str(port),
    ]
    return command


async def serve_daemon(root, mode, host, port, stop):
    """守护两个子应用：面板与 Bot。任一崩溃都不影响另一个，停机时一并停止。"""
    if mode == "compose":
        # 容器内跑镜像侧代码，入口链含数据库初始化与 QQ 登录等待。
        bot_command = ["bash", "scripts/entrypoint.sh", "python3", "bot.py"]
        bot_cwd = default_source_root()
    else:
        bot_command = [sys.executable, "bot.py"]
        bot_cwd = root
    bot_control = BotControl()
    panel_control = PanelControl()
    bot = asyncio.create_task(supervise_bot(bot_control, bot_command, bot_cwd))
    # 面板子进程以 -m src.deployment 启动，须在包所在仓库根运行才能导入模块；
    # 部署目录（--root）可能不含源码（如独立部署目录），不能用作 cwd。
    panel = asyncio.create_task(
        supervise_panel(panel_control, panel_command(root, mode, host, port), default_source_root())
    )
    stopper = asyncio.create_task(stop.wait())
    try:
        await stopper
    finally:
        bot_control.stop.set()
        panel_control.stop.set()
        for task in (panel, bot):
            if not task.done():
                task.cancel()
        await asyncio.gather(panel, bot, return_exceptions=True)


async def serve(port=None, root=None, mode=None, host=None):
    """守护进程入口：解析绑定、装信号处理，守护面板与 Bot 两个子进程。"""
    if root is None or mode is None:
        root, mode = detect_runtime(root)
    root = Path(root).resolve()
    bind, port = resolve_panel_bind(root, mode, host, port)
    if not ipaddress.ip_address(bind).is_loopback:
        _notify(
            f"警告：面板绑定非回环地址 {bind}，HTTP 明文传输，管理员密码与配置可能被同网段窃听；"
            "建议改用回环地址加 SSH 隧道访问。"
        )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            # Covers the phases before/after the children's own signal capture; as
            # PID 1 the process would otherwise ignore SIGTERM entirely.
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass
    await serve_daemon(root, mode, bind, port, stop)


def _stop_tree(process):
    """Stop the panel process and the Bot it supervises in one shot.

    The panel was started as a session/process-group leader, so its pid is the
    group id and one signal reaches the supervised Bot as well.
    """
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True)
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return


async def launch():
    """Root entry behind ``python main.py``: run the daemon, which owns both apps.

    The daemon supervises the panel and the Bot as child processes; ``main.py``
    only adds a thin parent that mirrors the daemon's exit code and forwards stop
    signals to the whole tree. Running the Bot alone, without the daemon, is
    ``bot.py``.
    """
    flags = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "src.deployment",
            cwd=default_source_root(),
            **flags,
        )
    except OSError as exc:
        raise SystemExit(f"无法启动部署面板：{exc}") from None
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            # POSIX only; on Windows Ctrl+C surfaces as KeyboardInterrupt below.
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass
    waiter = asyncio.create_task(process.wait())
    stopper = asyncio.create_task(stop.wait())
    try:
        await asyncio.wait({waiter, stopper}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        # Signal stop (or cancellation, which is how Windows Ctrl+C arrives):
        # take the panel and the supervised Bot down before exiting.
        if process.returncode is None:
            _stop_tree(process)
    code = await waiter
    if code:
        raise SystemExit(code)
