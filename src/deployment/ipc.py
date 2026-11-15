"""面板子进程与守护进程之间的文件 IPC。

面板把控制请求写入 ``.webcontroller/control-request.json``（action + 递增 seq），
守护进程轮询执行并把结果写入 ``control-status.json``。两者不共享内存，也不新开
端口；请求与状态都用 atomic_write 落盘，seq 去重保证幂等。
"""

import asyncio
import json
import time
from pathlib import Path

from ..config_schema import atomic_write

REQUEST_NAME = "control-request.json"
STATUS_NAME = "control-status.json"


def request_path(state: Path) -> Path:
    return state / REQUEST_NAME


def status_path(state: Path) -> Path:
    return state / STATUS_NAME


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_request(state: Path, action: str, seq: int) -> None:
    atomic_write(request_path(state), json.dumps({"action": action, "seq": seq}))


def read_request(state: Path):
    return _read_json(request_path(state))


def write_status(state: Path, seq: int, ok: bool, message: str = "") -> None:
    atomic_write(
        status_path(state),
        json.dumps({"seq": seq, "ok": ok, "message": message, "ts": time.time()}),
    )


def read_status(state: Path):
    return _read_json(status_path(state))


class FileControl:
    """面板侧控制代理：把重启 Bot 等请求经文件转发给守护进程。

    与旧的进程内 BotControl 接口对齐（capabilities 据此判断 bot_restart 可用），
    但实际动作由守护进程执行；面板不直接持有 Bot 子进程句柄。
    """

    def __init__(self, state: Path):
        self.state = Path(state)
        self._seq = int(time.time() * 1000)

    def request(self, action: str) -> int:
        self._seq += 1
        write_request(self.state, action, self._seq)
        return self._seq

    def restart_bot(self) -> int:
        return self.request("restart_bot")

    async def wait_status(self, seq: int, timeout: float = 10.0):
        """轮询守护进程回报的状态；超时返回 None。"""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            status = await asyncio.to_thread(read_status, self.state)
            if status and status.get("seq") == seq:
                return status
            await asyncio.sleep(0.1)
        return None


async def poll_control(state: Path, handlers: dict, stop: asyncio.Event, interval: float = 0.5):
    """守护侧轮询控制请求并执行；seq 去重，未知动作回报错误。

    handlers 把 action 映射到无参 callable（可同步可异步）。每次执行后写状态，
    面板据此得知结果。停机事件置位后退出。
    """
    last_seq = None
    # 启动时若已有请求文件，记录其 seq，避免重复执行历史请求。
    existing = read_request(state)
    if existing and isinstance(existing.get("seq"), int):
        last_seq = existing["seq"]
    while not stop.is_set():
        request = await asyncio.to_thread(read_request, state)
        if request and isinstance(request.get("seq"), int):
            seq = request["seq"]
            if seq != last_seq:
                last_seq = seq
                action = request.get("action")
                handler = handlers.get(action)
                if handler is None:
                    await asyncio.to_thread(
                        write_status, state, seq, False, f"未知控制动作：{action}"
                    )
                else:
                    try:
                        result = handler()
                        if asyncio.iscoroutine(result):
                            await result
                        await asyncio.to_thread(write_status, state, seq, True, "ok")
                    except Exception as exc:  # noqa: BLE001 - 回报任意执行失败
                        await asyncio.to_thread(write_status, state, seq, False, str(exc))
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            continue
