import asyncio

import pytest

from src.deployment.ipc import (
    FileControl,
    poll_control,
    read_request,
    read_status,
    write_request,
)


@pytest.mark.asyncio
async def test_file_control_round_trip(tmp_path):
    control = FileControl(tmp_path)
    executed = []

    async def handler():
        executed.append("restart_bot")

    stop = asyncio.Event()
    task = asyncio.create_task(
        poll_control(tmp_path, {"restart_bot": handler}, stop, interval=0.02)
    )
    try:
        seq = await asyncio.to_thread(control.restart_bot)
        status = await control.wait_status(seq, timeout=5)
        assert status is not None
        assert status["ok"] is True
        assert status["seq"] == seq
        assert executed == ["restart_bot"]
    finally:
        stop.set()
        await asyncio.wait_for(task, 5)


@pytest.mark.asyncio
async def test_poll_control_dedups_seq(tmp_path):
    calls = []

    async def handler():
        calls.append(1)

    stop = asyncio.Event()
    task = asyncio.create_task(
        poll_control(tmp_path, {"restart_bot": handler}, stop, interval=0.02)
    )
    try:
        # 同一 seq 写入两次，只应执行一次。
        await asyncio.to_thread(write_request, tmp_path, "restart_bot", 42)
        for _ in range(100):
            if read_status(tmp_path) and read_status(tmp_path)["seq"] == 42:
                break
            await asyncio.sleep(0.02)
        await asyncio.to_thread(write_request, tmp_path, "restart_bot", 42)
        await asyncio.sleep(0.2)
        assert calls == [1]
        # 新 seq 触发再次执行。
        await asyncio.to_thread(write_request, tmp_path, "restart_bot", 43)
        for _ in range(100):
            status = read_status(tmp_path)
            if status and status["seq"] == 43:
                break
            await asyncio.sleep(0.02)
        assert calls == [1, 1]
    finally:
        stop.set()
        await asyncio.wait_for(task, 5)


@pytest.mark.asyncio
async def test_poll_control_unknown_action(tmp_path):
    stop = asyncio.Event()
    task = asyncio.create_task(poll_control(tmp_path, {}, stop, interval=0.02))
    try:
        await asyncio.to_thread(write_request, tmp_path, "nope", 7)
        for _ in range(100):
            status = read_status(tmp_path)
            if status and status["seq"] == 7:
                break
            await asyncio.sleep(0.02)
        assert status["ok"] is False
        assert "未知控制动作" in status["message"]
    finally:
        stop.set()
        await asyncio.wait_for(task, 5)


@pytest.mark.asyncio
async def test_poll_control_ignores_preexisting_request(tmp_path):
    # 启动前已存在的请求不应被重复执行。
    await asyncio.to_thread(write_request, tmp_path, "restart_bot", 99)
    calls = []

    async def handler():
        calls.append(1)

    stop = asyncio.Event()
    task = asyncio.create_task(
        poll_control(tmp_path, {"restart_bot": handler}, stop, interval=0.02)
    )
    try:
        await asyncio.sleep(0.2)
        assert calls == []
        assert read_request(tmp_path)["seq"] == 99
    finally:
        stop.set()
        await asyncio.wait_for(task, 5)


def test_prepare_wires_file_control(tmp_path):
    from src.deployment.runtime import prepare
    from src.deployment.setup import PANEL_CONFIG_NAME, initialize_source
    from src.deployment.toml_config import CONFIG_NAMES

    configs = tmp_path / "configs"
    configs.mkdir()
    for name in (*CONFIG_NAMES, PANEL_CONFIG_NAME):
        (configs / f"{name}.template").write_text("", encoding="utf-8")
    initialize_source(tmp_path, "pw")
    control = FileControl(tmp_path / ".webcontroller")
    app = prepare(tmp_path, "source", control=control)
    # 生产路径必须把控制句柄接入应用，bot_restart 才可用（修复 prepare 丢 control 断链）。
    assert app.state.bot_control is control
