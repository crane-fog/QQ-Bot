"""NotificationService 图片下载与发送编排的单元测试。"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

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
    api = MagicMock()
    return NotificationService(api, 123, "https://gitea.example.com", "token")


def test_notification_service_requires_non_empty_api_url():
    with pytest.raises(ValueError, match=r"\[Gitea\] api_url 不能为空"):
        NotificationService(MagicMock(), 123, "   ", "token")


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
    api = MagicMock()
    api.asyncService = AsyncMock()
    service = NotificationService(api, 123, "https://gitea.example.com", "token")
    event = _issues_event_with_inline_image()
    downloaded_images: list[ImageSegment] = []

    async def fake_download(images, temp_dir):
        downloaded_images.extend(images)
        return {"https://gitea.example.com/attachments/inline.png": "C:/tmp/inline.png"}

    monkeypatch.setattr(service, "_download_images", fake_download)

    await service._send_issues_notification(event, "issues")

    assert downloaded_images == [
        ImageSegment(url="https://gitea.example.com/attachments/inline.png", alt="screen")
    ]

    api.asyncService.send_group_msg.assert_awaited_once()
    plain_message = api.asyncService.send_group_msg.await_args.kwargs["message"]
    assert plain_message[0] == {
        "type": "text",
        "data": {
            "text": "[Gitea] issues #1 opened in org/repo\nIssue with image",
        },
    }
    assert plain_message[1:4] == [
        {"type": "text", "data": {"text": "before "}},
        {"type": "image", "data": {"file": "file://C:/tmp/inline.png"}},
        {"type": "text", "data": {"text": " after\n\n"}},
    ]
    assert "report.txt" in plain_message[4]["data"]["text"]
    assert plain_message[5] == {
        "type": "text",
        "data": {"text": "\nurl: https://gitea.example.com/org/repo/issues/1"},
    }

    api.asyncService.send_group_forward_msg.assert_awaited_once()
    forward_message = api.asyncService.send_group_forward_msg.await_args.kwargs["forward_message"]
    assert forward_message[0]["data"]["content"][0]["data"]["text"] == (
        "[Gitea] issues #1 opened in org/repo\nTitle: Issue with image\nLabels: bug\nAuthor: alice"
    )
    assert forward_message[1]["data"]["content"][0:3] == plain_message[1:4]
    assert "report.txt" in forward_message[1]["data"]["content"][3]["data"]["text"]


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
