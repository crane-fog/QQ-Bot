import json
import os
import sys
from pathlib import Path

import pytest

from src.deployment import default_source_root
from src.deployment.__main__ import main
from src.deployment.auth import Authentication
from src.deployment.config import DeploymentError
from src.deployment.setup import (
    discover_project,
    initialize,
    initialize_source,
)
from src.deployment.toml_config import CONFIG_NAMES
from tests.test_deployment_config import SOURCE


def test_initialization_preserves_existing_files_and_credentials(tmp_path):
    (tmp_path / "compose.yaml").write_text(SOURCE, encoding="utf-8")
    (tmp_path / ".env").write_text("# keep comment\nOTHER=value\n", encoding="utf-8")
    initialize(tmp_path, "existing-project", "test-password")
    credential_path = tmp_path / ".webcontroller" / "credentials.json"
    credentials = credential_path.read_text(encoding="utf-8")
    assert "test-password" not in credentials
    assert (tmp_path / ".env").read_text(encoding="utf-8") == "# keep comment\nOTHER=value\n"
    initialize(tmp_path, "existing-project")
    assert credential_path.read_text(encoding="utf-8") == credentials
    settings = json.loads(
        (tmp_path / ".webcontroller" / "settings.json").read_text(encoding="utf-8")
    )
    assert settings == {
        "root": str(tmp_path.resolve()),
        "project": "existing-project",
    }
    with pytest.raises(DeploymentError):
        initialize(tmp_path, "different-project")


def test_project_detection_reads_compose_name(tmp_path):
    (tmp_path / "compose.yaml").write_text(SOURCE + "name: from-compose\n", encoding="utf-8")
    assert discover_project(tmp_path) == "from-compose"


def test_explicit_project_name_overrides_detection(tmp_path):
    (tmp_path / "compose.yaml").write_text(SOURCE, encoding="utf-8")
    assert discover_project(tmp_path, "override") == "override"
    with pytest.raises(DeploymentError):
        discover_project(tmp_path, "Invalid Name!")


def test_project_detection_requires_compose_file(tmp_path):
    with pytest.raises(DeploymentError):
        discover_project(tmp_path)


def test_new_deployment_honors_env_project_name(tmp_path):
    (tmp_path / "compose.yaml").write_text(SOURCE + "name: from-compose\n", encoding="utf-8")
    (tmp_path / ".env").write_text("COMPOSE_PROJECT_NAME='chosen'\n", encoding="utf-8")
    assert discover_project(tmp_path) == "chosen"


def test_default_source_root_points_at_checkout():
    root = default_source_root()
    assert (root / "pyproject.toml").is_file()
    assert (root / "src" / "deployment").is_dir()


def test_source_main_defaults_to_package_root(tmp_path, monkeypatch):
    configs = tmp_path / "configs"
    configs.mkdir()
    for name in CONFIG_NAMES:
        (configs / f"{name}.template").write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["src.deployment", "--init"])
    monkeypatch.setattr("src.deployment.runtime.default_source_root", lambda: tmp_path)
    main()
    settings = json.loads(
        (tmp_path / ".webcontroller" / "settings.json").read_text(encoding="utf-8")
    )
    assert settings == {"root": str(tmp_path.resolve())}
    initial = tmp_path / ".webcontroller" / "initial-password"
    assert len(initial.read_text(encoding="utf-8").strip()) >= 12


def test_initial_password_file_lifecycle(tmp_path):
    configs = tmp_path / "configs"
    configs.mkdir()
    for name in CONFIG_NAMES:
        (configs / f"{name}.template").write_text("", encoding="utf-8")
    initialize_source(tmp_path)
    initial = tmp_path / ".webcontroller" / "initial-password"
    password = initial.read_text(encoding="utf-8").strip()
    assert len(password) >= 12
    if os.name != "nt":
        assert initial.stat().st_mode & 0o777 == 0o600
    credentials = json.loads(
        (tmp_path / ".webcontroller" / "credentials.json").read_text(encoding="utf-8")
    )
    Authentication(credentials).login(password)
    initialize_source(tmp_path)
    assert initial.read_text(encoding="utf-8") == password + "\n"


def test_compose_init_generates_initial_password(tmp_path):
    (tmp_path / "compose.yaml").write_text(SOURCE, encoding="utf-8")
    initialize(tmp_path, "generated-project")
    initial = tmp_path / ".webcontroller" / "initial-password"
    assert len(initial.read_text(encoding="utf-8").strip()) >= 12


@pytest.mark.asyncio
async def test_serve_auto_initializes(tmp_path, monkeypatch):
    import asyncio
    import sys as _sys

    from src.deployment import runtime

    configs = tmp_path / "configs"
    configs.mkdir()
    for name in CONFIG_NAMES:
        (configs / f"{name}.template").write_text("", encoding="utf-8")
    recorded = {}

    async def fake_supervise_bot(control, command, cwd, **kwargs):
        recorded["command"] = command
        recorded["cwd"] = cwd
        await control.stop.wait()

    async def fake_supervise_panel(control, command, cwd, **kwargs):
        recorded["panel_command"] = command
        # 面板子进程启动时自动初始化（prepare 内完成）。
        runtime.prepare(tmp_path, "source")
        await control.stop.wait()

    monkeypatch.setattr(runtime, "supervise_bot", fake_supervise_bot)
    monkeypatch.setattr(runtime, "supervise_panel", fake_supervise_panel)
    task = asyncio.create_task(runtime.serve(root=tmp_path, mode="source"))
    for _ in range(200):
        if (tmp_path / ".webcontroller" / "settings.json").is_file():
            break
        await asyncio.sleep(0.02)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert (tmp_path / ".webcontroller" / "settings.json").is_file()
    assert (tmp_path / ".webcontroller" / "initial-password").is_file()
    assert recorded["command"] == [_sys.executable, "bot.py"]
    assert recorded["cwd"] == tmp_path.resolve()
    assert "--panel" in recorded["panel_command"]


@pytest.mark.asyncio
async def test_compose_serve_auto_initializes(tmp_path, monkeypatch):
    import asyncio

    from src.deployment import runtime

    (tmp_path / "compose.yaml").write_text(SOURCE, encoding="utf-8")

    async def fake_supervise_bot(control, command, cwd, **kwargs):
        await control.stop.wait()

    async def fake_supervise_panel(control, command, cwd, **kwargs):
        runtime.prepare(tmp_path, "compose")
        await control.stop.wait()

    monkeypatch.setattr(runtime, "supervise_bot", fake_supervise_bot)
    monkeypatch.setattr(runtime, "supervise_panel", fake_supervise_panel)
    monkeypatch.setattr(runtime, "PANEL_DEPLOY_MOUNT", str(tmp_path))
    task = asyncio.create_task(runtime.serve(root=tmp_path, mode="compose"))
    for _ in range(200):
        if (tmp_path / ".webcontroller" / "settings.json").is_file():
            break
        await asyncio.sleep(0.02)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    settings = json.loads(
        (tmp_path / ".webcontroller" / "settings.json").read_text(encoding="utf-8")
    )
    assert settings == {
        "root": str(tmp_path.resolve()),
        "project": runtime.discover_project(tmp_path),
    }
    assert (tmp_path / ".webcontroller" / "initial-password").is_file()
    assert (tmp_path / ".webcontroller" / "protected.json").is_file()


@pytest.mark.asyncio
async def test_compose_serve_supervises_entrypoint_chain(tmp_path, monkeypatch):
    import asyncio

    from src.deployment import runtime

    (tmp_path / "compose.yaml").write_text(SOURCE, encoding="utf-8")
    recorded = {}

    async def fake_supervise_bot(control, command, cwd, **kwargs):
        recorded["command"] = command
        recorded["cwd"] = cwd
        await control.stop.wait()

    async def fake_supervise_panel(control, command, cwd, **kwargs):
        await control.stop.wait()

    monkeypatch.setattr(runtime, "supervise_bot", fake_supervise_bot)
    monkeypatch.setattr(runtime, "supervise_panel", fake_supervise_panel)
    monkeypatch.setattr(runtime, "PANEL_DEPLOY_MOUNT", str(tmp_path))
    task = asyncio.create_task(runtime.serve(root=tmp_path, mode="compose"))
    for _ in range(200):
        if "command" in recorded:
            break
        await asyncio.sleep(0.02)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert recorded["command"] == ["bash", "scripts/entrypoint.sh", "python3", "bot.py"]
    assert recorded["cwd"] == runtime.default_source_root().resolve()


@pytest.mark.asyncio
async def test_supervise_bot_restarts_then_stops(tmp_path):
    import asyncio
    import sys

    from src.deployment.runtime import BotControl, supervise_bot

    control = BotControl()
    marker = tmp_path / "marker"
    command = [sys.executable, "-c", f"open({str(marker)!r}, 'a').write('x')"]
    task = asyncio.create_task(
        supervise_bot(control, command, tmp_path, backoff_start=0.05, backoff_cap=0.1)
    )
    try:
        for _ in range(200):
            if marker.is_file() and len(marker.read_text(encoding="utf-8")) >= 3:
                break
            await asyncio.sleep(0.05)
        assert marker.is_file() and len(marker.read_text(encoding="utf-8")) >= 3, (
            "supervisor did not restart the child"
        )
    finally:
        control.stop.set()
        await asyncio.wait_for(task, 10)


@pytest.mark.asyncio
async def test_supervise_bot_restart_request_skips_backoff(tmp_path):
    import asyncio
    import sys
    import time

    from src.deployment.runtime import BotControl, supervise_bot

    control = BotControl()
    command = [sys.executable, "-c", "import time; time.sleep(30)"]
    task = asyncio.create_task(supervise_bot(control, command, tmp_path, backoff_cap=600.0))
    try:
        for _ in range(100):
            if control.process is not None:
                break
            await asyncio.sleep(0.05)
        first_pid = control.process.pid
        started = time.monotonic()
        control.restart.set()
        for _ in range(200):
            if control.process is not None and control.process.pid != first_pid:
                break
            await asyncio.sleep(0.05)
        assert control.process.pid != first_pid, "restart request did not respawn the child"
        assert time.monotonic() - started < 5, "restart request waited on backoff"
    finally:
        control.stop.set()
        await asyncio.wait_for(task, 10)


@pytest.mark.asyncio
async def test_supervise_bot_terminates_child_on_stop(tmp_path):
    import asyncio
    import sys

    from src.deployment.runtime import BotControl, supervise_bot

    control = BotControl()
    command = [sys.executable, "-c", "import time; time.sleep(30)"]
    task = asyncio.create_task(supervise_bot(control, command, tmp_path, backoff_start=0.05))
    await asyncio.sleep(0.5)
    control.stop.set()
    await asyncio.wait_for(task, 10)


@pytest.mark.asyncio
async def test_supervise_bot_resets_backoff_after_stable_run(tmp_path):
    import asyncio
    import sys
    import time

    from src.deployment.runtime import BotControl, supervise_bot

    control = BotControl()
    restarts = tmp_path / "restarts"
    # First child exits immediately; the second sleeps long enough to count as
    # stable (reset_after), so the next crash must restart at backoff_start.
    command = [
        sys.executable,
        "-c",
        (
            "import sys, time\n"
            f"p = {str(restarts)!r}\n"
            "open(p, 'a').write('x')\n"
            "if len(open(p).read()) > 1:\n"
            "    time.sleep(1)\n"
            "sys.exit(1)\n"
        ),
    ]
    task = asyncio.create_task(
        supervise_bot(
            control, command, tmp_path, backoff_start=0.05, backoff_cap=5.0, reset_after=0.5
        )
    )
    try:
        deadline = time.monotonic() + 20
        while True:
            if restarts.is_file() and len(restarts.read_text(encoding="utf-8")) >= 3:
                break
            assert time.monotonic() < deadline, "supervisor did not restart after stable run"
            await asyncio.sleep(0.05)
    finally:
        control.stop.set()
        await asyncio.wait_for(task, 10)


@pytest.mark.asyncio
async def test_supervise_bot_backoff_cancels_waiters(tmp_path, monkeypatch):
    import asyncio
    import sys
    import time

    from src.deployment.runtime import BotControl, supervise_bot

    control = BotControl()
    launches = tmp_path / "launches"
    command = [
        sys.executable,
        "-c",
        f"p = {str(launches)!r}\nopen(p, 'a').write('x')\nif len(open(p).read()) >= 3:\n    import time; time.sleep(30)\n",
    ]
    # 前两次退避强制超时，第三次退避中停机；只追踪退避等待创建的任务，
    # 守护循环主等待的任务不算泄漏。
    real_wait = asyncio.wait
    backoff_waiters = []

    async def tracking_wait(fs, **kwargs):
        if kwargs.get("timeout") is not None:
            backoff_waiters.extend(fs)
        return await real_wait(fs, **kwargs)

    monkeypatch.setattr(asyncio, "wait", tracking_wait)
    task = asyncio.create_task(
        supervise_bot(control, command, tmp_path, backoff_start=0.05, backoff_cap=0.05)
    )
    try:
        deadline = time.monotonic() + 20
        while True:
            if launches.is_file() and len(launches.read_text(encoding="utf-8")) >= 3:
                break
            assert time.monotonic() < deadline, "supervisor did not respawn"
            await asyncio.sleep(0.02)
        assert len(backoff_waiters) >= 4, "expected two timed-out backoff waits"
        for waiter in backoff_waiters[:4]:
            for _ in range(100):
                if waiter.done():
                    break
                await asyncio.sleep(0.02)
            assert waiter.done(), "backoff timeout leaked a waiter task"
            assert waiter.cancelled(), "backoff waiter should be cancelled after timeout"
    finally:
        control.stop.set()
        await asyncio.wait_for(task, 10)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("host", "mode", "warns"),
    [(None, "source", False), ("127.0.0.1", "compose", False), (None, "compose", True)],
)
async def test_serve_warns_on_non_loopback_bind(tmp_path, monkeypatch, host, mode, warns):
    from src.deployment import runtime

    notifications = []

    async def fake_serve_daemon(root, mode, host, port, stop):
        stop.set()

    monkeypatch.setattr(runtime, "serve_daemon", fake_serve_daemon)
    monkeypatch.setattr(runtime, "_notify", notifications.append)
    await runtime.serve(root=tmp_path, mode=mode, host=host)
    assert any("明文" in message for message in notifications) is warns


def test_merge_settings_preserves_panel_bind(tmp_path):
    from src.deployment.setup import merge_settings, read_settings

    configs = tmp_path / "configs"
    configs.mkdir()
    for name in CONFIG_NAMES:
        (configs / f"{name}.template").write_text("", encoding="utf-8")
    initialize_source(tmp_path, "pw")
    state = tmp_path / ".webcontroller"
    merge_settings(state, panel_host="0.0.0.0", panel_port=8080)
    # 重新初始化不得丢弃面板绑定设置。
    initialize_source(tmp_path)
    settings = read_settings(state)
    assert settings["panel_host"] == "0.0.0.0"
    assert settings["panel_port"] == 8080
    assert settings["root"] == str(tmp_path.resolve())


def test_resolve_panel_bind_priority(tmp_path):
    from src.deployment.runtime import resolve_panel_bind
    from src.deployment.setup import merge_settings

    state = tmp_path / ".webcontroller"
    # 无持久化：源码回环、容器全接口，默认端口。
    assert resolve_panel_bind(tmp_path, "source") == ("127.0.0.1", 7001)
    assert resolve_panel_bind(tmp_path, "compose") == ("0.0.0.0", 7001)
    merge_settings(state, panel_host="192.168.1.5", panel_port=8080)
    # 持久化生效。
    assert resolve_panel_bind(tmp_path, "source") == ("192.168.1.5", 8080)
    # 命令行覆盖持久化。
    assert resolve_panel_bind(tmp_path, "source", host="127.0.0.1", port=9000) == (
        "127.0.0.1",
        9000,
    )
    # 非法持久化值回退默认。
    merge_settings(state, panel_host="", panel_port=99999)
    assert resolve_panel_bind(tmp_path, "source") == ("127.0.0.1", 7001)


def test_detect_runtime_uses_deploy_mount(tmp_path, monkeypatch):
    from src.deployment import runtime

    (tmp_path / "compose.yaml").write_text(SOURCE, encoding="utf-8")
    monkeypatch.setattr(runtime, "PANEL_DEPLOY_MOUNT", str(tmp_path))
    assert runtime.detect_runtime() == (tmp_path.resolve(), "compose")
    monkeypatch.setattr(runtime, "PANEL_DEPLOY_MOUNT", str(tmp_path / "absent"))
    assert runtime.detect_runtime(str(tmp_path)) == (tmp_path.resolve(), "source")
    root, mode = runtime.detect_runtime()
    assert mode == "source"
    assert (root / "pyproject.toml").is_file()


def test_source_init_with_explicit_password(tmp_path):
    configs = tmp_path / "configs"
    configs.mkdir()
    for name in CONFIG_NAMES:
        (configs / f"{name}.template").write_text("", encoding="utf-8")
    initialize_source(tmp_path, "chosen-pw")
    assert not (tmp_path / ".webcontroller" / "initial-password").exists()
    credentials = json.loads(
        (tmp_path / ".webcontroller" / "credentials.json").read_text(encoding="utf-8")
    )
    Authentication(credentials).login("chosen-pw")


def test_short_password_is_accepted(tmp_path):
    (tmp_path / "compose.yaml").write_text(SOURCE, encoding="utf-8")
    initialize(tmp_path, "short-password-project", "abc")
    credentials = json.loads(
        (tmp_path / ".webcontroller" / "credentials.json").read_text(encoding="utf-8")
    )
    Authentication(credentials).login("abc")


def test_cli_flag_validation(monkeypatch):
    def run(*argv):
        monkeypatch.setattr(sys, "argv", ["src.deployment", *argv])
        main()

    with pytest.raises(SystemExit):
        run("--password", "x")
    with pytest.raises(SystemExit):
        run("--init", "--bg")
    with pytest.raises(SystemExit):
        run("--init", "--reset-password")
    with pytest.raises(SystemExit):
        run("--host", "example.com")


@pytest.mark.asyncio
async def test_launch_spawns_panel_and_mirrors_exit(monkeypatch):
    import sys as _sys

    from src.deployment import runtime

    recorded = {}

    class FakeProcess:
        pid = 4321
        returncode = 3

        async def wait(self):
            return 3

    async def fake_exec(*command, **kwargs):
        recorded["command"] = list(command)
        recorded["cwd"] = kwargs.get("cwd")
        return FakeProcess()

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr(runtime, "default_source_root", lambda: Path("/deploy-root"))
    with pytest.raises(SystemExit) as excinfo:
        await runtime.launch()
    assert excinfo.value.code == 3
    assert recorded["command"] == [_sys.executable, "-m", "src.deployment"]
    assert recorded["cwd"] == Path("/deploy-root")


@pytest.mark.asyncio
async def test_launch_stops_tree_on_cancel(monkeypatch):
    import asyncio

    from src.deployment import runtime

    stopped = []

    class FakeProcess:
        pid = 4321
        returncode = None

        async def wait(self):
            while self.returncode is None:
                await asyncio.sleep(0.01)
            return self.returncode

    async def fake_exec(*command, **kwargs):
        return FakeProcess()

    def fake_stop(process):
        stopped.append(process.pid)
        process.returncode = 0

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr(runtime, "_stop_tree", fake_stop)
    monkeypatch.setattr(runtime, "default_source_root", lambda: Path("/deploy-root"))
    task = asyncio.create_task(runtime.launch())
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert stopped == [4321]


@pytest.mark.skipif(os.name == "nt", reason="POSIX signal forwarding")
@pytest.mark.asyncio
async def test_launch_stops_tree_on_sigterm(monkeypatch):
    import asyncio
    import signal

    from src.deployment import runtime

    stopped = []

    class FakeProcess:
        pid = 4321
        returncode = None

        async def wait(self):
            while self.returncode is None:
                await asyncio.sleep(0.01)
            return self.returncode

    async def fake_exec(*command, **kwargs):
        return FakeProcess()

    def fake_stop(process):
        stopped.append(process.pid)
        process.returncode = 0

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr(runtime, "_stop_tree", fake_stop)
    monkeypatch.setattr(runtime, "default_source_root", lambda: Path("/deploy-root"))
    task = asyncio.create_task(runtime.launch())
    await asyncio.sleep(0.05)
    os.kill(os.getpid(), signal.SIGTERM)
    await asyncio.wait_for(task, 5)
    assert stopped == [4321]
