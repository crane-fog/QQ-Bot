"""GiteaReply 插件与 GiteaApi 客户端的单元测试。"""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from plugins.GiteaReply.GiteaReply import GiteaReply
from src.Bot import Bot
from src.event_handler.GroupMessageEventHandler import GroupMessageEvent
from src.gitea.GiteaApi import GiteaApi, GiteaApiError
from src.gitea.Models import Comment, Issue

ISSUE_PAYLOAD = {
    "id": 1,
    "url": "https://gitea.example.com/api/v1/repos/owner/repo/issues/7",
    "html_url": "https://gitea.example.com/owner/repo/issues/7",
    "number": 7,
    "user": {"id": 2, "login": "dev"},
    "title": "修复登录失败",
    "state": "open",
    "is_locked": False,
    "comments": 0,
    "created_at": "2026-09-01T00:00:00Z",
    "updated_at": "2026-09-01T00:00:00Z",
}

COMMENT_PAYLOAD = {
    "id": 10,
    "html_url": "https://gitea.example.com/owner/repo/issues/7#issuecomment-10",
    "issue_url": "https://gitea.example.com/owner/repo/issues/7",
    "user": {"id": 3, "login": "bot"},
    "body": "来自 QQ 群反馈",
    "created_at": "2026-09-13T00:00:00Z",
    "updated_at": "2026-09-13T00:00:00Z",
}


class _FakeResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = "not found" if status_code == 404 else ""

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, response: _FakeResponse):
        self.response = response
        self.calls: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def request(self, method: str, url: str, **kwargs) -> _FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.response


def _fake_client_factory(response: _FakeResponse):
    """返回 (client 构造器, client 实例)，client 实例可用于断言请求参数。"""
    client = _FakeAsyncClient(response)
    return (lambda *args, **kwargs: client), client


def _make_plugin(repo: str = "owner/repo", gitea=None) -> GiteaReply:
    plugin = object.__new__(GiteaReply)
    plugin.name = "GiteaReply"
    plugin.status = "running"
    plugin.repo = repo
    plugin.gitea = gitea if gitea is not None else cast(Any, SimpleNamespace())
    return cast(GiteaReply, plugin)


def _make_event(message: str) -> GroupMessageEvent:
    return cast(
        GroupMessageEvent,
        cast(
            object,
            SimpleNamespace(
                message=message,
                group_id=20001,
                user_id=10001,
                card="张三",
                nickname="zs",
            ),
        ),
    )


def _mock_gitea(issue=None, comment=None, error: Exception | None = None):
    get_issue = AsyncMock(return_value=issue)
    create_issue_comment = AsyncMock(return_value=comment)
    if error is not None:
        get_issue.side_effect = error
    return SimpleNamespace(get_issue=get_issue, create_issue_comment=create_issue_comment)


@pytest.mark.asyncio
async def test_gitea_api_create_issue_comment_builds_request():
    client_class, client = _fake_client_factory(_FakeResponse(201, COMMENT_PAYLOAD))
    api = GiteaApi("https://gitea.example.com", "token")

    with patch("src.gitea.GiteaApi.AsyncClient", client_class):
        comment = await api.create_issue_comment("owner/repo", 7, "回复内容")

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://gitea.example.com/api/v1/repos/owner/repo/issues/7/comments"
    assert call["headers"] == {"Authorization": "token token"}
    assert call["json"] == {"body": "回复内容"}
    assert comment.html_url == COMMENT_PAYLOAD["html_url"]


@pytest.mark.asyncio
async def test_gitea_api_get_issue_not_found_raises_with_status():
    client_class, _ = _fake_client_factory(_FakeResponse(404))
    api = GiteaApi("https://gitea.example.com", "token")

    with patch("src.gitea.GiteaApi.AsyncClient", client_class):
        with pytest.raises(GiteaApiError) as exc_info:
            await api.get_issue("owner/repo", 999)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_reply_posts_comment_and_sends_receipt():
    gitea = _mock_gitea(
        issue=Issue.model_validate(ISSUE_PAYLOAD), comment=Comment.model_validate(COMMENT_PAYLOAD)
    )
    plugin = _make_plugin(gitea=gitea)
    service = SimpleNamespace(send_group_msg=AsyncMock())

    with patch("src.Api.api.asyncService", service):
        await cast(Any, GiteaReply.main).__wrapped__(
            plugin, _make_event("#7 登录一直报 500"), debug=False
        )

    gitea.create_issue_comment.assert_awaited_once()
    args = gitea.create_issue_comment.await_args
    assert args.args[:3] == ("owner/repo", 7, "**来自 QQ 群反馈**（张三）：\n\n登录一直报 500")

    service.send_group_msg.assert_awaited_once()
    kwargs = service.send_group_msg.await_args.kwargs
    assert kwargs["group_id"] == 20001
    assert "已回复 issue #7「修复登录失败」" in kwargs["message"]
    assert COMMENT_PAYLOAD["html_url"] in kwargs["message"]


@pytest.mark.asyncio
async def test_reply_missing_issue_sends_friendly_hint():
    gitea = _mock_gitea(error=GiteaApiError("Gitea API 返回 404", 404))
    plugin = _make_plugin(gitea=gitea)
    service = SimpleNamespace(send_group_msg=AsyncMock())

    with patch("src.Api.api.asyncService", service):
        await cast(Any, GiteaReply.main).__wrapped__(plugin, _make_event("#999 报错"), debug=False)

    gitea.create_issue_comment.assert_not_awaited()
    message = service.send_group_msg.await_args.kwargs["message"]
    assert "issue #999 不存在" in message


@pytest.mark.asyncio
async def test_reply_api_error_sends_failure_hint():
    gitea = _mock_gitea(error=GiteaApiError("Gitea API 请求失败：timeout"))
    plugin = _make_plugin(gitea=gitea)
    service = SimpleNamespace(send_group_msg=AsyncMock())

    with patch("src.Api.api.asyncService", service):
        await cast(Any, GiteaReply.main).__wrapped__(plugin, _make_event("#7 内容"), debug=False)

    message = service.send_group_msg.await_args.kwargs["message"]
    assert "[Gitea] 回复失败" in message


@pytest.mark.asyncio
@pytest.mark.parametrize("message", ["#abc 内容", "#7", "#7 ", "#0731话题闲聊", "随便聊聊 #7"])
async def test_reply_ignores_malformed_message(message):
    gitea = _mock_gitea(issue=ISSUE_PAYLOAD, comment=COMMENT_PAYLOAD)
    plugin = _make_plugin(gitea=gitea)
    service = SimpleNamespace(send_group_msg=AsyncMock())

    with patch("src.Api.api.asyncService", service):
        await cast(Any, GiteaReply.main).__wrapped__(plugin, _make_event(message), debug=False)

    gitea.get_issue.assert_not_awaited()
    service.send_group_msg.assert_not_awaited()


@pytest.mark.asyncio
async def test_reply_ignores_when_repo_not_configured():
    gitea = _mock_gitea(issue=ISSUE_PAYLOAD, comment=COMMENT_PAYLOAD)
    plugin = _make_plugin(repo="", gitea=gitea)
    service = SimpleNamespace(send_group_msg=AsyncMock())

    with patch("src.Api.api.asyncService", service):
        await cast(Any, GiteaReply.main).__wrapped__(plugin, _make_event("#7 内容"), debug=False)

    gitea.get_issue.assert_not_awaited()
    service.send_group_msg.assert_not_awaited()


def test_gitea_api_requires_non_empty_url():
    with pytest.raises(ValueError, match=r"\[Gitea\] api_url 不能为空"):
        GiteaApi("  ", "token")


def test_gitea_api_strips_trailing_slash():
    api = GiteaApi("https://gitea.example.com/", "token")
    assert api.api_url == "https://gitea.example.com"


def test_plugin_construction_reads_repo_config():
    bot = cast(
        Bot,
        cast(
            object,
            SimpleNamespace(
                bot_config={"Gitea": {"reply_repo": "owner/repo"}},
                gitea_api_url="https://gitea.example.com",
                gitea_api_token="token",
            ),
        ),
    )
    with patch("plugins.GiteaReply.GiteaReply.Plugins.init_status", MagicMock()):
        plugin = GiteaReply(bot)

    assert plugin.repo == "owner/repo"
    assert plugin.gitea.api_url == "https://gitea.example.com"
