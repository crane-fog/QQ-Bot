"""issue 新评论私聊提醒（临时会话）的单元测试。"""

from unittest.mock import AsyncMock, patch

import pytest

from src.gitea.Models import GiteaIssueCommentEvent
from src.webhook_handler.EventConfig import EVENT_CONFIG
from src.webhook_handler.NotificationService import NotificationService

NOW = "2026-04-29T12:00:00Z"


def user_payload(login: str) -> dict:
    return {
        "id": 1,
        "login": login,
        "username": login,
        "full_name": login,
        "email": f"{login}@example.com",
        "avatar_url": "",
    }


def repository_payload() -> dict:
    return {
        "id": 100,
        "owner": user_payload("org"),
        "name": "repo",
        "full_name": "org/repo",
        "description": "",
        "private": False,
        "fork": False,
        "html_url": "https://gitea.example.com/org/repo",
        "ssh_url": "",
        "clone_url": "",
        "website": "",
        "stars_count": 0,
        "forks_count": 0,
        "watchers_count": 0,
        "open_issues_count": 0,
        "default_branch": "main",
        "created_at": NOW,
        "updated_at": NOW,
    }


def issue_payload(author: str, assignees: list[str]) -> dict:
    return {
        "id": 200,
        "url": "https://gitea.example.com/api/issues/1",
        "html_url": "https://gitea.example.com/org/repo/issues/1",
        "number": 1,
        "user": user_payload(author),
        "title": "登录样式错乱",
        "body": "body",
        "assignees": [user_payload(login) for login in assignees],
        "labels": [],
        "state": "open",
        "is_locked": False,
        "comments": 1,
        "created_at": NOW,
        "updated_at": NOW,
    }


def comment_event(
    author: str = "2553759",
    assignees: list[str] | None = None,
    commenter: str = "2553761",
    action: str = "created",
) -> GiteaIssueCommentEvent:
    return GiteaIssueCommentEvent.model_validate(
        {
            "action": action,
            "issue": issue_payload(author, assignees or []),
            "comment": {
                "id": 300,
                "html_url": "https://gitea.example.com/org/repo/issues/1#comment-300",
                "issue_url": "https://gitea.example.com/api/issues/1",
                "user": user_payload(commenter),
                "body": "comment body",
                "assets": [],
                "created_at": NOW,
                "updated_at": NOW,
            },
            "repository": repository_payload(),
            "sender": user_payload(commenter),
            "is_pull": False,
        }
    )


class FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeSession:
    def __init__(self, value):
        self._value = value

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def execute(self, statement):
        return FakeResult(self._value)


@pytest.fixture
def service():
    # 1000003 视为助教学号，进排除名单；888 为失败提醒群
    return NotificationService(
        123,
        "https://gitea.example.com",
        "token",
        dm_notify=True,
        dm_notify_exclude=["1000003"],
        dm_notify_group=888,
    )


def patch_lookup(service, mapping: dict[str, str | None]):
    async def fake_lookup(login: str):
        return mapping.get(login)

    service._lookup_qq = fake_lookup


@pytest.mark.asyncio
async def test_dm_sent_to_author_and_assignee(service):
    """作者与被指派人均已绑定 QQ：分别私聊，带 response_group 作为临时会话来源群。"""
    patch_lookup(service, {"2553759": "9000001", "2553760": "9000002"})
    event = comment_event(assignees=["2553760", "1000003"])

    with (
        patch("src.Api.api.asyncPrivateService", new=AsyncMock()) as private,
        patch("src.Api.api.asyncGroupService", new=AsyncMock()) as group,
    ):
        await service._send_comment_dm_notifications(event)

    assert private.send_private_msg.await_count == 2
    called_ids = [call.args[0] for call in private.send_private_msg.await_args_list]
    assert called_ids == [9000001, 9000002]
    for call in private.send_private_msg.await_args_list:
        assert call.kwargs["group_id"] == 123
        assert call.args[1] == (
            "高程答疑平台在你的 Issue 下有新评论：\n"
            "https://gitea.example.com/org/repo/issues/1#comment-300"
        )
    group.send_group_msg.assert_not_awaited()


@pytest.mark.asyncio
async def test_dm_commenter_and_excluded_never_dmed(service):
    """评论者本人与排除名单（助教）不收私聊。"""
    patch_lookup(service, {"2553759": "9000001"})
    event = comment_event(commenter="2553759", assignees=["1000003"])

    with patch("src.Api.api.asyncPrivateService", new=AsyncMock()) as private:
        await service._send_comment_dm_notifications(event)

    private.send_private_msg.assert_not_awaited()


@pytest.mark.asyncio
async def test_dm_failure_notice_lists_failed_logins_without_at(service):
    """查不到映射与发送失败的学号在 dm_notify_group 纯文本列出，不 @。"""
    patch_lookup(service, {"2553759": None, "2553760": "9000002"})
    event = comment_event(assignees=["2553760"])

    with (
        patch("src.Api.api.asyncPrivateService", new=AsyncMock()) as private,
        patch("src.Api.api.asyncGroupService", new=AsyncMock()) as group,
    ):
        private.send_private_msg.side_effect = Exception("cannot send")
        await service._send_comment_dm_notifications(event)

    group.send_group_msg.assert_awaited_once()
    assert group.send_group_msg.await_args.kwargs["group_id"] == 888
    message = group.send_group_msg.await_args.kwargs["message"]
    assert "[CQ:at" not in message
    assert "2553759" in message
    assert "2553760" in message
    assert "issues/1#comment-300" in message


@pytest.mark.asyncio
async def test_dm_skipped_for_non_created_action(service):
    patch_lookup(service, {"2553759": "9000001"})
    event = comment_event(action="edited")

    with patch("src.Api.api.asyncPrivateService", new=AsyncMock()) as private:
        await service._send_comment_dm_notifications(event)

    private.send_private_msg.assert_not_awaited()


@pytest.mark.asyncio
async def test_dm_skips_assistant_group_members(service):
    """assistant_list（Bot 启动时从助教群加载）中的 QQ 不私聊，也不触发失败提醒。"""
    service.assistant_list = {9000002}
    patch_lookup(service, {"2553759": "9000001", "2553760": "9000002"})
    event = comment_event(assignees=["2553760"])

    with (
        patch("src.Api.api.asyncPrivateService", new=AsyncMock()) as private,
        patch("src.Api.api.asyncGroupService", new=AsyncMock()) as group,
    ):
        await service._send_comment_dm_notifications(event)

    assert private.send_private_msg.await_count == 1
    assert private.send_private_msg.await_args.args[0] == 9000001
    assert private.send_private_msg.await_args.kwargs == {"group_id": 123}
    group.send_group_msg.assert_not_awaited()


@pytest.mark.asyncio
async def test_dm_failure_notice_only_when_configured():
    """未配置 dm_notify_group 时不做失败提醒；配置了则发到该群。"""
    event = comment_event()

    unconfigured = NotificationService(123, "https://gitea.example.com", "token", dm_notify=True)
    unconfigured._lookup_qq = AsyncMock(return_value=None)
    assert unconfigured.dm_notify_group == 0
    with patch("src.Api.api.asyncGroupService", new=AsyncMock()) as group:
        await unconfigured._send_comment_dm_notifications(event)
    group.send_group_msg.assert_not_awaited()

    configured = NotificationService(
        123,
        "https://gitea.example.com",
        "token",
        dm_notify=True,
        dm_notify_group=888,
    )
    configured._lookup_qq = AsyncMock(return_value=None)
    with patch("src.Api.api.asyncGroupService", new=AsyncMock()) as group:
        await configured._send_comment_dm_notifications(event)
    assert group.send_group_msg.await_args.kwargs["group_id"] == 888


@pytest.mark.asyncio
async def test_dm_disabled_by_default():
    """默认不开 dm_notify 时，send() 不产生私聊调用。"""
    service = NotificationService(123, "https://gitea.example.com", "token")
    service._send_issue_comment_notification = AsyncMock()

    with patch("src.Api.api.asyncPrivateService", new=AsyncMock()) as private:
        await service.send(comment_event(), "issue_comment", EVENT_CONFIG["issue_comment"])

    service._send_issue_comment_notification.assert_awaited_once()
    private.send_private_msg.assert_not_awaited()


@pytest.mark.asyncio
async def test_lookup_qq_without_database_or_non_digit_login():
    service = NotificationService(123, "https://gitea.example.com", "token")
    assert await service._lookup_qq("2553759") is None

    service.session_factory = lambda: FakeSession("9000001")
    assert await service._lookup_qq("not-a-number") is None
    assert await service._lookup_qq("2553759") == "9000001"

    service.session_factory = lambda: FakeSession(None)
    assert await service._lookup_qq("2553759") is None
