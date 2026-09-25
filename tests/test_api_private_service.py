"""AsyncPrivateService 私聊发送接口的单元测试。"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.Api import Api


@pytest.fixture
def service():
    api = Api()
    api.set_server_address("127.0.0.1:3001")
    return api.asyncPrivateService


def _fake_response(payload: dict):
    resp = MagicMock()
    resp.json.return_value = payload
    return resp


@pytest.mark.asyncio
async def test_send_private_msg_with_text(service):
    service.api.client.post = AsyncMock(
        return_value=_fake_response({"status": "async", "retcode": 0})
    )
    result = await service.send_private_msg(123456, "hello")
    service.api.client.post.assert_awaited_once_with(
        "http://127.0.0.1:3001/send_private_msg",
        json={"user_id": 123456, "message": "hello"},
    )
    assert result == {"status": "async", "retcode": 0}


@pytest.mark.asyncio
async def test_send_private_msg_with_segments(service):
    service.api.client.post = AsyncMock(return_value=_fake_response({"retcode": 0}))
    segments = [
        {"type": "text", "data": {"text": "[Gitea] issue #42"}},
        {"type": "at", "data": {"qq": 123456}},
    ]
    await service.send_private_msg(123456, segments)
    service.api.client.post.assert_awaited_once_with(
        "http://127.0.0.1:3001/send_private_msg",
        json={"user_id": 123456, "message": segments},
    )
