from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.gitea.GiteaEventFormatter import GiteaEventFormatter
from src.gitea.Models import GiteaIssueCommentEvent, GiteaIssuesEvent, GiteaPushEvent
from src.webhook_handler.EventConfig import EVENT_CONFIG
from src.webhook_handler.WebhookHandler import WebhookHandler, parse_gitea_event

NOW = "2026-04-29T12:00:00Z"
GITEA_API_URL = "https://gitea.example.com"
GITEA_API_TOKEN = "test-token"


def user_payload(login: str = "alice") -> dict:
    return {
        "id": 1,
        "login": login,
        "username": login,
        "full_name": login,
        "email": f"{login}@example.com",
        "avatar_url": "https://gitea.example.com/avatar.png",
    }


def repository_payload() -> dict:
    return {
        "id": 100,
        "owner": user_payload(),
        "name": "repo",
        "full_name": "org/repo",
        "description": "demo",
        "private": False,
        "fork": False,
        "html_url": "https://gitea.example.com/org/repo",
        "ssh_url": "git@gitea.example.com:org/repo.git",
        "clone_url": "https://gitea.example.com/org/repo.git",
        "website": "",
        "stars_count": 0,
        "forks_count": 0,
        "watchers_count": 0,
        "open_issues_count": 1,
        "default_branch": "main",
        "created_at": NOW,
        "updated_at": NOW,
        "unknown_new_field": "ignored",
    }


def issue_payload() -> dict:
    return {
        "id": 200,
        "url": "https://gitea.example.com/api/issues/1",
        "html_url": "https://gitea.example.com/org/repo/issues/1",
        "number": 1,
        "user": user_payload(),
        "title": "Fix webhook",
        # Gitea 正文可能包含附件的 markdown 引用，附件本身同时出现在 assets 列表里。
        "body": "body ![img](/attachments/uuid)",
        "assets": [
            {
                "id": 1,
                "name": "pic.png",
                "size": 10,
                "download_count": 0,
                "created_at": NOW,
                "uuid": "uuid",
                "browser_download_url": "https://gitea.example.com/attachments/uuid",
            }
        ],
        "labels": [{"id": 1, "name": "bug", "color": "ff0000", "description": "", "url": ""}],
        "state": "open",
        "is_locked": False,
        "comments": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "repository": {"id": 100, "name": "repo", "owner": "org", "full_name": "org/repo"},
    }


def push_payload() -> dict:
    commit = {
        "id": "abcdef1234567890",
        "message": "Implement webhook\n\nDetails",
        "url": "https://gitea.example.com/org/repo/commit/abcdef",
        "author": {"name": "Alice", "email": "alice@example.com", "username": "alice"},
        "committer": {"name": "Alice", "email": "alice@example.com", "username": "alice"},
        "timestamp": NOW,
        "added": ["a.py"],
        "removed": [],
        "modified": ["b.py"],
    }
    return {
        "ref": "refs/heads/main",
        "before": "000000",
        "after": "abcdef",
        "compare_url": "https://gitea.example.com/org/repo/compare/000...abc",
        "commits": [commit],
        "total_commits": 1,
        "head_commit": commit,
        "repository": repository_payload(),
        "pusher": user_payload(),
        "sender": user_payload(),
    }


def issues_payload() -> dict:
    return {
        "action": "opened",
        "number": 1,
        "issue": issue_payload(),
        "repository": repository_payload(),
        "sender": user_payload(),
    }


def issue_comment_payload() -> dict:
    return {
        "action": "created",
        "issue": issue_payload(),
        "comment": {
            "id": 300,
            "html_url": "https://gitea.example.com/org/repo/issues/1#comment-300",
            "issue_url": "https://gitea.example.com/api/issues/1",
            "user": user_payload(),
            "body": "comment body",
            "assets": [],
            "created_at": NOW,
            "updated_at": NOW,
        },
        "repository": repository_payload(),
        "sender": user_payload(),
        "is_pull": False,
    }


def test_parse_push_event_and_format_message():
    """
    push 事件应能按 Gitea payload 解析，并生成包含最新提交摘要的通知。
    """
    event = parse_gitea_event("push", push_payload())

    assert isinstance(event, GiteaPushEvent)
    message = GiteaEventFormatter().plain_text(event, "push")
    assert "push in org/repo" in message
    assert "latest: abcdef12 Implement webhook by alice" in message


@pytest.mark.asyncio
async def test_push_formatter_falls_back_to_last_commit_without_warning():
    """
    head_commit 缺失但 commits 存在时属于可降级场景，不应污染日志。
    """
    payload = push_payload()
    payload["head_commit"] = None
    event = GiteaPushEvent.model_validate(payload)
    api = Mock()
    api.asyncService = AsyncMock()

    with patch("src.webhook_handler.WebhookHandler.Log.warning") as warning:
        await WebhookHandler(api, 123, GITEA_API_URL, GITEA_API_TOKEN).resolve(
            event, "push", EVENT_CONFIG["push"]
        )

    warning.assert_not_called()
    api.asyncService.send_group_msg.assert_called_once()
    assert (
        "latest: abcdef12 Implement webhook by alice"
        in api.asyncService.send_group_msg.call_args.kwargs["message"]
    )


@pytest.mark.asyncio
async def test_push_payload_missing_commit_details_logs_warning():
    """
    push 声称有提交但没有任何提交详情时，需要记录 warning 方便排查。
    """
    payload = push_payload()
    payload["head_commit"] = None
    payload["commits"] = []
    payload["total_commits"] = 1
    event = GiteaPushEvent.model_validate(payload)
    api = Mock()
    api.asyncService = AsyncMock()

    with patch("src.webhook_handler.WebhookHandler.Log.warning") as warning:
        await WebhookHandler(api, 123, GITEA_API_URL, GITEA_API_TOKEN).resolve(
            event, "push", EVENT_CONFIG["push"]
        )

    warning.assert_called_once()
    assert "缺少提交详情" in warning.call_args.args[0]
    api.asyncService.send_group_msg.assert_called_once()


@pytest.mark.asyncio
async def test_send_plain_text_failure_logs_error():
    """
    QQ 消息发送失败应被记录，但不应让 webhook handler 继续向外抛异常。
    """
    event = GiteaIssueCommentEvent.model_validate(issue_comment_payload())
    api = Mock()
    api.asyncService = AsyncMock()
    api.asyncService.send_group_msg.side_effect = RuntimeError("network down")

    with patch("src.webhook_handler.NotificationService.Log.error") as error:
        await WebhookHandler(api, 123, GITEA_API_URL, GITEA_API_TOKEN).resolve(
            event, "issue_comment", EVENT_CONFIG["issue_comment"]
        )

    error.assert_called_once()
    assert "发送 Gitea webhook 通知失败" in error.call_args.args[0]


@pytest.mark.asyncio
async def test_issues_event_sends_three_node_forward_message():
    """
    issues 类事件应先发送一条摘要，再发送三条节点的合并转发消息。
    """
    payload = issues_payload()
    payload["issue"]["body"] = "long body\n" + ("x" * 600)
    event = GiteaIssuesEvent.model_validate(payload)
    api = Mock()
    api.asyncService = AsyncMock()

    await WebhookHandler(api, 123, GITEA_API_URL, GITEA_API_TOKEN).resolve(
        event, "issues", EVENT_CONFIG["issues"]
    )

    api.asyncService.send_group_msg.assert_called_once_with(
        group_id=123,
        message="[Gitea] issues #1 opened in org/repo",
    )
    api.asyncService.send_group_forward_msg.assert_called_once()
    forward_message = api.asyncService.send_group_forward_msg.call_args.kwargs["forward_message"]

    assert len(forward_message) == 3
    assert forward_message[0]["type"] == "node"
    assert forward_message[0]["data"]["name"] == "Gitea"
    assert (
        "issues #1 opened in org/repo" in forward_message[0]["data"]["content"][0]["data"]["text"]
    )
    assert "Title: Fix webhook" in forward_message[0]["data"]["content"][0]["data"]["text"]
    assert "Labels: bug" in forward_message[0]["data"]["content"][0]["data"]["text"]
    assert "Author: None" in forward_message[0]["data"]["content"][0]["data"]["text"]
    assert "long body\n" + ("x" * 600) == forward_message[1]["data"]["content"][0]["data"]["text"]
    assert (
        "url: https://gitea.example.com/org/repo/issues/1"
        == forward_message[2]["data"]["content"][0]["data"]["text"]
    )


@pytest.mark.asyncio
async def test_issues_summary_failure_skips_forward_and_logs_error():
    """
    issues 摘要发送失败时应记录错误，并且不继续发送合并转发。
    """
    event = GiteaIssuesEvent.model_validate(issues_payload())
    api = Mock()
    api.asyncService = AsyncMock()
    api.asyncService.send_group_msg.side_effect = RuntimeError("network down")

    with patch("src.webhook_handler.NotificationService.Log.error") as error:
        await WebhookHandler(api, 123, GITEA_API_URL, GITEA_API_TOKEN).resolve(
            event, "issues", EVENT_CONFIG["issues"]
        )

    error.assert_called_once()
    assert "发送 Gitea webhook 通知失败" in error.call_args.args[0]
    api.asyncService.send_group_forward_msg.assert_not_called()


@pytest.mark.asyncio
async def test_issue_assign_sends_plain_text_without_forward_message():
    """
    只有 issues 事件发送合并转发；其他 IssuePayload 事件走普通文本。
    """
    payload = issues_payload()
    payload["action"] = "assigned"
    event = GiteaIssuesEvent.model_validate(payload)
    api = Mock()
    api.asyncService = AsyncMock()

    await WebhookHandler(api, 123, GITEA_API_URL, GITEA_API_TOKEN).resolve(
        event, "issue_assign", EVENT_CONFIG["issue_assign"]
    )

    api.asyncService.send_group_msg.assert_called_once()
    assert (
        "issue_assign #1 assigned in org/repo"
        in api.asyncService.send_group_msg.call_args.kwargs["message"]
    )
    api.asyncService.send_group_forward_msg.assert_not_called()


def test_issue_label_uses_issue_payload_model():
    """
    Gitea 的 issue_label 事件和 issues 事件共用同一套 IssuePayload 结构。
    """
    event = parse_gitea_event("issue_label", issues_payload())

    assert isinstance(event, GiteaIssuesEvent)
    message = GiteaEventFormatter().plain_text(event, "issue_label")
    assert "issue_label #1 opened in org/repo" in message


@pytest.mark.asyncio
async def test_issue_label_sends_summary_author_and_label_only():
    """
    issue_label 事件只需要一条包含摘要、作者和变更标签的普通消息。
    """
    payload = issues_payload()
    payload["action"] = "label_updated"
    payload["changes"] = {
        "added_labels": [{"id": 2, "name": "priority/high", "color": "00ff00"}],
        "removed_labels": [{"id": 1, "name": "bug", "color": "ff0000"}],
    }
    event = GiteaIssuesEvent.model_validate(payload)
    api = Mock()
    api.asyncService = AsyncMock()

    await WebhookHandler(api, 123, GITEA_API_URL, GITEA_API_TOKEN).resolve(
        event, "issue_label", EVENT_CONFIG["issue_label"]
    )

    api.asyncService.send_group_msg.assert_called_once_with(
        group_id=123,
        message=(
            "[Gitea] issue_label #1 label_updated in org/repo\n"
            "Author: alice\n"
            "Label: +priority/high, -bug"
        ),
    )
    api.asyncService.send_group_forward_msg.assert_not_called()


def test_parse_issue_comment_event():
    """
    issue_comment 事件应解析评论正文，并生成 issue 维度的评论通知。
    """
    event = parse_gitea_event("issue_comment", issue_comment_payload())

    assert isinstance(event, GiteaIssueCommentEvent)
    message = GiteaEventFormatter().plain_text(event, "issue_comment")
    assert "issue_comment on issue #1 created in org/repo" in message
    assert "comment body" in message


def test_issue_comment_null_list_fields_are_treated_as_empty_lists():
    """
    Gitea 未初始化的 Go slice 会被编码为 null，返回给 Webhook 客户端
    模型应将其按空列表处理。
    """
    payload = issue_comment_payload()
    payload["issue"]["assets"] = None
    payload["issue"]["labels"] = None
    payload["issue"]["assignees"] = None
    payload["comment"]["assets"] = None

    event = parse_gitea_event("issue_comment", payload)

    assert isinstance(event, GiteaIssueCommentEvent)
    assert event.issue.assets == []
    assert event.issue.labels == []
    assert event.issue.assignees == []
    assert event.comment.assets == []


def test_issue_formatter_keeps_body_and_lists_attachments_separately():
    """
    附件是独立 assets 列表，formatter 不改写正文，只额外列出附件 URL。
    """
    event = GiteaIssuesEvent.model_validate(issues_payload())
    message = GiteaEventFormatter().issue_detail(event, "issues")

    assert "body ![img](/attachments/uuid)" in message
    assert "pic.png: https://gitea.example.com/attachments/uuid" in message
