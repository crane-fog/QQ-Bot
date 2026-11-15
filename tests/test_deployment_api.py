import json
import threading

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from src.deployment.app import create_app
from src.deployment.auth import create_credentials
from src.deployment.config import ComposeDocument, DeploymentError
from src.deployment.runner import ComposeRunner
from src.deployment.toml_config import ConfigStore
from tests.test_deployment_config import SOURCE


class FakeRunner:
    def __init__(self):
        self.calls = []
        self.failure = False

    async def validate(self, source):
        self.calls.append("validate")
        if self.failure:
            raise DeploymentError("Compose 校验失败")
        return {"services": {"db": {"image": "postgres:18"}, "webcontroller": {"image": "panel:1"}}}


@pytest.fixture
def panel(tmp_path):
    (tmp_path / "compose.yaml").write_text(SOURCE, encoding="utf-8")
    state = tmp_path / ".webcontroller"
    document = ComposeDocument(tmp_path, state)
    runner = FakeRunner()
    credentials = create_credentials("test-password")
    with TestClient(
        create_app(document, runner, credentials), base_url="http://localhost"
    ) as client:
        yield client, document, runner


def login(client):
    response = client.post("/api/login", json={"password": "test-password"})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf"]}


def test_authentication_and_csrf_required(panel):
    client, document, runner = panel
    assert client.get("/api/compose").status_code == 401
    assert client.post("/api/login", json={"password": "wrong"}).status_code == 401
    headers = login(client)
    assert client.get("/api/compose").status_code == 200
    body = {"source": SOURCE, "version": document.read()["version"]}
    assert client.put("/api/compose", json=body).status_code == 403
    assert (
        client.put(
            "/api/compose", json=body, headers={**headers, "Origin": "http://evil.test"}
        ).status_code
        == 403
    )
    assert runner.calls == []


def test_initial_password_file_removed_on_successful_login(panel):
    client, document, runner = panel
    initial = document.state / "initial-password"
    initial.write_text("stale\n", encoding="utf-8")
    assert client.post("/api/login", json={"password": "wrong"}).status_code == 401
    assert initial.exists()
    assert client.post("/api/login", json={"password": "test-password"}).status_code == 200
    assert not initial.exists()


def test_validation_failure_does_not_write_file(panel):
    client, document, runner = panel
    runner.failure = True
    body = {
        "source": SOURCE.replace("postgres:18", "postgres:19"),
        "version": document.read()["version"],
    }
    response = client.put("/api/compose", json=body, headers=login(client))
    assert response.status_code == 422
    assert document.source() == SOURCE
    assert document.backups() == []


def test_save_and_logout(panel):
    client, document, runner = panel
    headers = login(client)
    result = client.put(
        "/api/compose",
        json={
            "source": SOURCE.replace("postgres:18", "postgres:19"),
            "version": document.read()["version"],
        },
        headers=headers,
    )
    assert result.status_code == 200
    assert "postgres:19" in document.source()
    assert runner.calls == ["validate"]
    assert client.post("/api/logout", headers=headers).status_code == 200
    assert client.get("/api/compose").status_code == 401


def test_limiter_blocks_repeated_failed_logins(panel):
    client, _, _ = panel
    for _ in range(5):
        assert client.post("/api/login", json={"password": "wrong"}).status_code == 401
    assert client.post("/api/login", json={"password": "wrong"}).status_code == 429


@pytest.mark.asyncio
async def test_runner_uses_fixed_project_context_and_env_file(tmp_path):
    (tmp_path / "compose.yaml").write_text(SOURCE, encoding="utf-8")
    (tmp_path / ".env").write_text("DB_PASSWORD=private-value\n", encoding="utf-8")
    runner = ComposeRunner(tmp_path, "original-project")
    commands = []

    async def execute(args, source="", timeout=60):
        commands.append(args)
        return json.dumps({"services": {"webcontroller": {}, "db": {}}})

    runner.execute = execute
    await runner.validate(SOURCE)
    assert commands and all("up" not in args and "down" not in args for args in commands)
    joined = " ".join(commands[0])
    assert "--project-directory" in joined and "original-project" in joined
    assert "--env-file" in joined
    values = runner.redaction_values(SOURCE)
    assert "private-value" in values
    assert "private-value" not in runner.redact("output private-value", values=values)


def test_bot_restart_requires_control_and_reports_unavailable(panel):
    client, _, _ = panel
    headers = login(client)
    assert client.get("/api/capabilities").json()["bot_restart"] is False
    response = client.post("/api/bot/restart", headers=headers)
    assert response.status_code == 503


def test_bot_restart_sets_event_and_terminates_child(tmp_path):
    import asyncio

    from fastapi.testclient import TestClient

    from src.deployment.app import create_app
    from src.deployment.auth import create_credentials

    class FakeProcess:
        returncode = None

        def __init__(self):
            self.terminated = False

        def terminate(self):
            self.terminated = True

    class FakeControl:
        def __init__(self):
            self.stop = asyncio.Event()
            self.restart = asyncio.Event()
            self.process = FakeProcess()

    control = FakeControl()
    (tmp_path / "compose.yaml").write_text(SOURCE, encoding="utf-8")
    document = ComposeDocument(tmp_path, tmp_path / ".webcontroller")
    app = create_app(
        document, FakeRunner(), create_credentials("test-password"), bot_control=control
    )
    with TestClient(app, base_url="http://localhost") as client:
        headers = login(client)
        assert client.get("/api/capabilities").json()["bot_restart"] is True
        body = {"source": SOURCE, "version": document.read()["version"]}
        assert client.put("/api/compose", json=body).status_code == 403
        response = client.post("/api/bot/restart", headers=headers)
        assert response.status_code == 200 and response.json()["restarted"] is True
    assert control.restart.is_set() and control.process.terminated


def test_unknown_host_and_large_chunked_body_are_rejected(panel):
    client, _, _ = panel
    assert client.get("/", headers={"Host": "unexpected.example"}).status_code == 400
    assert (
        client.post("/api/login", content=iter([b"x" * 1100000, b"x" * 1100000])).status_code == 413
    )


@pytest.mark.parametrize(
    ("bind_host", "requested", "status"),
    [
        (None, "192.168.1.5", 400),
        ("192.168.1.5", "192.168.1.5", 200),
        ("192.168.1.5", "unexpected.example", 400),
        ("0.0.0.0", "unexpected.example", 200),
    ],
)
def test_bind_host_extends_host_allowlist(tmp_path, bind_host, requested, status):
    (tmp_path / "compose.yaml").write_text(SOURCE, encoding="utf-8")
    document = ComposeDocument(tmp_path, tmp_path / ".webcontroller")
    app = create_app(document, FakeRunner(), create_credentials("test-password"), host=bind_host)
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/", headers={"Host": requested}).status_code == status


@pytest.mark.asyncio
async def test_disk_io_runs_off_the_event_loop(tmp_path, monkeypatch):
    (tmp_path / "compose.yaml").write_text(SOURCE, encoding="utf-8")
    state = tmp_path / ".webcontroller"
    document = ComposeDocument(tmp_path, state)
    store = ConfigStore(tmp_path, state)
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    (configs_dir / "plugins.toml").write_text("[Example]\nenable = false\n", encoding="utf-8")
    main_thread = threading.get_ident()
    loop_threads = []
    real_read = document.read
    real_save = store.save

    def document_read():
        loop_threads.append(threading.get_ident())
        return real_read()

    def store_save(*args):
        loop_threads.append(threading.get_ident())
        return real_save(*args)

    monkeypatch.setattr(document, "read", document_read)
    monkeypatch.setattr(store, "save", store_save)
    app = create_app(document, FakeRunner(), create_credentials("test-password"), configs=store)
    async with app.router.lifespan_context(app):
        loop_threads.append(threading.get_ident())
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://localhost") as client:
            response = await client.post("/api/login", json={"password": "test-password"})
            assert response.status_code == 200
            headers = {"X-CSRF-Token": response.json()["csrf"]}
            assert (await client.get("/api/compose")).status_code == 200
            original = store.read("plugins.toml")
            body = {
                "source": original["source"].replace("false", "true"),
                "version": original["version"],
            }
            response = await client.put("/api/configs/plugins.toml", json=body, headers=headers)
            assert response.status_code == 200
    # 第一次记录是事件循环线程，其后是磁盘操作实际运行的线程，必须不同。
    assert loop_threads[0] == main_thread
    assert len(loop_threads) == 3
    assert all(thread != main_thread for thread in loop_threads[1:])


@pytest.mark.asyncio
async def test_resolved_env_file_values_are_filtered_from_logs(tmp_path):
    runner = ComposeRunner(tmp_path, "test-project")

    async def execute(args, source="", timeout=60):
        return json.dumps(
            {
                "services": {
                    "webcontroller": {},
                    "db": {"environment": {"PASSWORD": "from-env-file"}},
                }
            }
        )

    runner.execute = execute
    await runner.validate(SOURCE)
    assert "from-env-file" not in runner.redact("output from-env-file", SOURCE)
