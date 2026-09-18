"""NotificationService 图片下载与发送编排的单元测试。"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.gitea.GiteaEventFormatter import (
    ContentNode,
    FileSegment,
    ImageSegment,
    TextSegment,
)
from src.webhook_handler.NotificationService import NotificationService


@pytest.fixture
def service():
    return NotificationService(123, "https://gitea.example.com", "token")


def test_notification_service_requires_non_empty_api_url():
    with pytest.raises(ValueError, match=r"\[Gitea\] api_url 不能为空"):
        NotificationService(123, "   ", "token")


def _make_response(content: bytes = b"data", status: int = 200):
    resp = MagicMock()
    resp.content = content
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = Exception("http error")
    return resp


class _FakeAsyncClient:
    """最小化 fake httpx.AsyncClient，按构造时给定的响应序列返回。"""

    def __init__(self, responses):
        self._responses = list(responses)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, *args, **kwargs):
        return self._responses.pop(0)


def _fake_client_class(responses):
    return lambda *args, **kwargs: _FakeAsyncClient(responses)


@pytest.mark.asyncio
async def test_download_images_writes_files_and_cleans_up(service, tmp_path, monkeypatch):
    """成功下载应写入临时目录。"""
    images = [ImageSegment(url="https://gitea.example.com/a.png", alt="a")]
    monkeypatch.setattr(
        "src.webhook_handler.NotificationService.AsyncClient",
        _fake_client_class([_make_response(b"png-bytes")]),
    )

    paths = await service._download_images(images, tmp_path)
    assert paths["https://gitea.example.com/a.png"] is not None
    assert Path(paths["https://gitea.example.com/a.png"]).read_bytes() == b"png-bytes"


@pytest.mark.asyncio
async def test_download_images_maps_failure_to_none(service, tmp_path, monkeypatch):
    """单张下载失败应映射为 None，不抛异常。"""
    images = [ImageSegment(url="https://gitea.example.com/bad.png", alt="b")]
    monkeypatch.setattr(
        "src.webhook_handler.NotificationService.AsyncClient",
        _fake_client_class([_make_response(status=404)]),
    )
    paths = await service._download_images(images, tmp_path)
    assert paths["https://gitea.example.com/bad.png"] is None


@pytest.mark.asyncio
async def test_download_empty_images_returns_empty(service):
    assert await service._download_images([], Path("/tmp")) == {}


def test_node_segments_replaces_failed_image_with_placeholder(service):
    """图片下载失败（path 为 None）时，应替换为 [图片下载失败] 文本占位。"""
    node = ContentNode(
        sender_name="u",
        segments=[
            TextSegment(text="hi"),
            ImageSegment(url="x", alt="x"),
            TextSegment(text="after"),
        ],
    )
    segs = service._node_segments(node, {"x": None})
    assert segs == [
        {"type": "text", "data": {"text": "hi"}},
        {"type": "text", "data": {"text": "[图片下载失败]"}},
        {"type": "text", "data": {"text": "after"}},
    ]


def test_node_segments_includes_image_when_downloaded(service):
    node = ContentNode(
        sender_name="u",
        segments=[TextSegment(text="hi"), ImageSegment(url="x", alt="x")],
    )
    segs = service._node_segments(node, {"x": "/tmp/p.png"})
    assert segs == [
        {"type": "text", "data": {"text": "hi"}},
        {"type": "image", "data": {"file": "file:///tmp/p.png"}},
    ]


def test_node_segments_renders_file_segment(service):
    node = ContentNode(
        sender_name="u",
        segments=[
            TextSegment(text="check this:"),
            FileSegment(
                name="report.pdf", size=2048, download_url="https://gitea.example.com/attachments/r"
            ),
        ],
    )
    segs = service._node_segments(node, {})
    assert segs[0] == {"type": "text", "data": {"text": "check this:"}}
    assert segs[1]["type"] == "text"
    assert "report.pdf" in segs[1]["data"]["text"]
    assert "2.0 KB" in segs[1]["data"]["text"]
    assert "https://gitea.example.com/attachments/r" in segs[1]["data"]["text"]


def _issues_event_with_inline_image():
    from src.gitea.Models import GiteaIssuesEvent

    return GiteaIssuesEvent.model_validate(
        {
            "action": "opened",
            "number": 1,
            "issue": {
                "id": 200,
                "url": "https://gitea.example.com/api/issues/1",
                "html_url": "https://gitea.example.com/org/repo/issues/1",
                "number": 1,
                "user": {"id": 1, "login": "alice"},
                "title": "Issue with image",
                "body": "before ![screen](/attachments/inline.png) after",
                "assets": [
                    {
                        "id": 1,
                        "name": "report.txt",
                        "size": 10,
                        "download_count": 0,
                        "created_at": "2026-04-29T12:00:00Z",
                        "uuid": "report",
                        "browser_download_url": "https://gitea.example.com/attachments/report",
                    }
                ],
                "labels": [{"id": 1, "name": "bug"}],
                "state": "open",
                "is_locked": False,
                "comments": 0,
                "created_at": "2026-04-29T12:00:00Z",
                "updated_at": "2026-04-29T12:00:00Z",
            },
            "repository": {
                "id": 100,
                "name": "repo",
                "owner": {"id": 1, "login": "org"},
                "full_name": "org/repo",
                "private": False,
                "fork": False,
                "html_url": "https://gitea.example.com/org/repo",
            },
            "sender": {"id": 1, "login": "alice"},
        }
    )


@pytest.mark.asyncio
async def test_issues_notification_sends_markdown_images_and_attachments(monkeypatch):
    """issues 事件应与 issue_comment 一样将正文 Markdown 图片下载后混合发送。"""
    service = NotificationService(123, "https://gitea.example.com", "token")
    event = _issues_event_with_inline_image()
    downloaded_images: list[ImageSegment] = []

    async def fake_download(images, temp_dir):
        downloaded_images.extend(images)
        return {"https://gitea.example.com/attachments/inline.png": "C:/tmp/inline.png"}

    monkeypatch.setattr(service, "_download_images", fake_download)

    with patch("src.Api.api.asyncGroupService", new=AsyncMock()) as async_service:
        await service._send_issues_notification(event, "issues")

        assert downloaded_images == [
            ImageSegment(url="https://gitea.example.com/attachments/inline.png", alt="screen")
        ]

        async_service.send_group_msg.assert_awaited_once()
        plain_message = async_service.send_group_msg.await_args.kwargs["message"]
        assert plain_message[0] == {
            "type": "text",
            "data": {
                "text": "[Gitea] issues #1 opened in org/repo\nIssue with image\n",
            },
        }
        # 正文内容前插入作者块：首行作者名、第二行按显示宽度画分隔线
        assert plain_message[1] == {"type": "text", "data": {"text": "alice\n-----\n"}}
        assert plain_message[2:5] == [
            {"type": "text", "data": {"text": "before "}},
            {"type": "image", "data": {"file": "file://C:/tmp/inline.png"}},
            {"type": "text", "data": {"text": " after\n\n"}},
        ]
        assert "report.txt" in plain_message[5]["data"]["text"]
        assert plain_message[6] == {
            "type": "text",
            "data": {"text": "\nurl: https://gitea.example.com/org/repo/issues/1"},
        }

        async_service.send_group_forward_msg.assert_awaited_once()
        forward_message = async_service.send_group_forward_msg.await_args.kwargs["forward_message"]
        assert forward_message[0]["data"]["content"][0]["data"]["text"] == (
            "[Gitea] issues #1 opened in org/repo\nTitle: Issue with image\nLabels: bug\nAuthor: alice"
        )
        # 合并转发正文节点带作者块，节点昵称为作者
        assert forward_message[1]["data"]["name"] == "alice"
        assert forward_message[1]["data"]["content"][0] == plain_message[1]
        assert forward_message[1]["data"]["content"][1:4] == plain_message[2:5]
        assert "report.txt" in forward_message[1]["data"]["content"][4]["data"]["text"]


@pytest.mark.asyncio
async def test_download_images_sends_token_only_to_configured_gitea_host(
    service, tmp_path, monkeypatch
):
    """Markdown 可引用外部图片，但不能将 Gitea Token 发送到外部站点。"""
    requests: list[tuple[str, dict]] = []

    class RecordingAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, **kwargs):
            requests.append((url, kwargs["headers"]))
            return _make_response()

    monkeypatch.setattr("src.webhook_handler.NotificationService.AsyncClient", RecordingAsyncClient)

    await service._download_images(
        [
            ImageSegment(url="https://gitea.example.com/attachments/inside.png"),
            ImageSegment(url="https://images.example.net/outside.png"),
        ],
        tmp_path,
    )

    assert dict(requests) == {
        "https://gitea.example.com/attachments/inside.png": {"Authorization": "token token"},
        "https://images.example.net/outside.png": {},
    }


# ---------- 作者块格式 ----------


def test_author_block_width_matches_display_width():
    from src.gitea.GiteaEventFormatter import author_block

    # ASCII 按字符数，CJK 按双宽计算
    assert author_block("alice") == "alice\n-----\n"
    assert author_block("张三") == "张三\n----\n"
    assert author_block("bin") == "bin\n---\n"


def test_author_block_caps_long_names():
    from src.gitea.GiteaEventFormatter import AUTHOR_LINE_MAX_WIDTH, author_block

    long_name = "a" * 60
    block = author_block(long_name)
    lines = block.splitlines()
    assert lines[0] == long_name  # 名字不截断
    assert len(lines[1]) == AUTHOR_LINE_MAX_WIDTH  # 分隔线封顶


def test_author_block_empty_author_falls_back_to_gitea():
    from src.gitea.GiteaEventFormatter import author_block

    assert author_block("") == "Gitea\n-----\n"
    assert author_block("  ") == "Gitea\n-----\n"


def test_forward_plan_comment_nodes_carry_author_block():
    """合并转发每个评论节点应有作者块首段，且节点昵称为作者。"""
    from src.gitea.GiteaEventFormatter import GiteaEventFormatter
    from src.gitea.Models import Comment, GiteaIssueCommentEvent

    payload = {
        "action": "created",
        "issue": {
            "id": 1,
            "url": "https://gitea.example.com/api/issues/1",
            "html_url": "https://gitea.example.com/org/repo/issues/1",
            "number": 1,
            "user": {"id": 1, "login": "alice"},
            "title": "T",
            "body": "body",
            "labels": [],
            "state": "open",
            "is_locked": False,
            "comments": 1,
            "created_at": "2026-09-01T00:00:00Z",
            "updated_at": "2026-09-01T00:00:00Z",
            "assets": [],
        },
        "comment": {
            "id": 2,
            "html_url": "https://gitea.example.com/org/repo/issues/1#comment-2",
            "issue_url": "https://gitea.example.com/api/issues/1",
            "user": {"id": 2, "login": "bob"},
            "body": "hi",
            "assets": [],
            "created_at": "2026-09-01T00:00:00Z",
            "updated_at": "2026-09-01T00:00:00Z",
        },
        "repository": {
            "id": 100,
            "name": "repo",
            "owner": {"id": 1, "login": "org"},
            "full_name": "org/repo",
            "private": False,
            "fork": False,
            "html_url": "https://gitea.example.com/org/repo",
        },
        "sender": {"id": 1, "login": "alice"},
        "is_pull": False,
    }
    event = GiteaIssueCommentEvent.model_validate(payload)
    comment = Comment.model_validate(payload["comment"] | {"user": {"id": 2, "login": "bob"}})

    plan = GiteaEventFormatter("https://gitea.example.com").issue_comment_forward(event, [comment])

    assert plan.nodes[0].sender_name == "alice"
    assert plan.nodes[0].segments[0].text == "alice\n-----\n"
    assert plan.nodes[1].sender_name == "bob"
    assert plan.nodes[1].segments[0].text == "bob\n---\n"
    assert plan.nodes[1].segments[1].text.startswith("hi")
