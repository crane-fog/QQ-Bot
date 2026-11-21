"""Isolated Linux Docker integration; never targets the real deployment."""

import os
import shutil
import subprocess
import sys
import uuid

import pytest

from src.deployment.config import ComposeDocument
from src.deployment.runner import ComposeRunner

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_WEB_DOCKER_TESTS") != "1"
    or sys.platform != "linux"
    or not shutil.which("docker"),
    reason="Requires Linux Docker and RUN_WEB_DOCKER_TESTS=1",
)


@pytest.mark.asyncio
async def test_real_compose_relative_bind_env_and_recreation(tmp_path):
    project = "paneltest-" + uuid.uuid4().hex
    data = tmp_path / "data"
    data.mkdir()
    (data / "value.txt").write_text("exists", encoding="utf-8")
    (tmp_path / ".env").write_text("CHECK_VALUE=private-integration-value\n", encoding="utf-8")
    source = """services:
  webcontroller:
    image: alpine:3.21
    command: [sleep, '300']
  worker:
    image: alpine:3.21
    command: [sleep, '300']
    environment:
      CHECK_VALUE: ${CHECK_VALUE}
      REVISION: '1'
    volumes:
      - ./data:/data:ro
      - store:/store
    healthcheck:
      test: [CMD, test, -f, /data/value.txt]
      interval: 1s
      timeout: 1s
      retries: 3
  sidecar:
    image: alpine:3.21
    command: [sleep, '300']
    profiles: [extra]
volumes:
  store:
"""
    (tmp_path / "compose.yaml").write_text(source, encoding="utf-8")
    document = ComposeDocument(tmp_path, tmp_path / ".webcontroller")
    runner = ComposeRunner(tmp_path, project)
    prefix = [
        "docker",
        "compose",
        "--project-directory",
        str(tmp_path),
        "-p",
        project,
        "-f",
        str(document.path),
    ]

    def command(*args):
        return subprocess.run(
            prefix + list(args), check=True, capture_output=True, text=True
        ).stdout.strip()

    try:
        resolved = await runner.validate(source)
        assert (
            resolved["services"]["worker"]["environment"]["CHECK_VALUE"]
            == "private-integration-value"
        )
        assert resolved["services"]["worker"]["volumes"][0]["source"] == str(data)
        # The panel only validates config; bringing services up is a host-side action.
        command("up", "-d", "--wait", "--wait-timeout", "60", "worker")
        services_up = command("ps", "--all", "--format", "{{.Service}}").split()
        assert "worker" in services_up
        assert "sidecar" not in services_up, "profiled service must not be started"
    finally:
        # Only the unique temporary project created above is removed.
        command("down", "--volumes", "--remove-orphans")
