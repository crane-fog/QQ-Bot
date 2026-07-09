"""NotificationService 图片下载与发送编排的单元测试。"""

from pathlib import Path
from unittest.mock import MagicMock

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
