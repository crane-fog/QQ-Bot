"""GiteaReply 插件与 GiteaApi 客户端的单元测试。"""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from plugins.GiteaReply.GiteaReply import (
    MEDIA_FAILED_TEXT,
    GiteaReply,
    build_comment_markdown,
    parse_reply_segments,
)
from src.Bot import Bot
from src.event_handler.GroupMessageEventHandler import GroupMessageEvent
from src.gitea.GiteaApi import GiteaApi, GiteaApiError
from src.gitea.Models import Attachment, Comment, Issue

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

ATTACHMENT_PAYLOAD = {
    "id": 5,
    "name": "image_0.png",
    "size": 100,
    "download_count": 0,
    "created_at": "2026-09-14T00:00:00Z",
    "uuid": "uuid-1",
    "browser_download_url": "https://gitea.example.com/attachments/uuid-1",
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
    plugin.config = {"reply_repo": repo}
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


def _mock_gitea(
    issue=None,
    comment=None,
    attachment=None,
    error: Exception | None = None,
    upload_error: Exception | None = None,
    patch_error: Exception | None = None,
):
    get_issue = AsyncMock(return_value=issue)
    create_issue_comment = AsyncMock(return_value=comment)
    create_comment_attachment = AsyncMock(return_value=attachment)
    update_issue_comment = AsyncMock()
    if error is not None:
        get_issue.side_effect = error
    if upload_error is not None:
        create_comment_attachment.side_effect = upload_error
    if patch_error is not None:
        update_issue_comment.side_effect = patch_error
    return SimpleNamespace(
        get_issue=get_issue,
        create_issue_comment=create_issue_comment,
        create_comment_attachment=create_comment_attachment,
        update_issue_comment=update_issue_comment,
    )


def _download_saves_png(dest):
    """生成一张真实 PNG，让图片格式嗅探走完整路径。"""
    Image.new("RGB", (1, 1)).save(dest, "PNG")


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
async def test_gitea_api_list_issue_comments_returns_models():
    client_class, client = _fake_client_factory(_FakeResponse(200, [COMMENT_PAYLOAD]))
    api = GiteaApi("https://gitea.example.com", "token")

    with patch("src.gitea.GiteaApi.AsyncClient", client_class):
        comments = await api.list_issue_comments("owner/repo", 7)

    call = client.calls[0]
    assert call["method"] == "GET"
    assert call["url"] == "https://gitea.example.com/api/v1/repos/owner/repo/issues/7/comments"
    assert [c.html_url for c in comments] == [COMMENT_PAYLOAD["html_url"]]


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
@pytest.mark.parametrize("message", ["#abc 内容", "#7", "#7 ", "# ", "随便聊聊 #7"])
async def test_reply_ignores_malformed_message(message):
    gitea = _mock_gitea(issue=ISSUE_PAYLOAD, comment=COMMENT_PAYLOAD)
    plugin = _make_plugin(gitea=gitea)
    service = SimpleNamespace(send_group_msg=AsyncMock())

    with patch("src.Api.api.asyncService", service):
        await cast(Any, GiteaReply.main).__wrapped__(plugin, _make_event(message), debug=False)

    gitea.get_issue.assert_not_awaited()
    service.send_group_msg.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("message", ["#7内容不能有空格", "#7    多个空格也行", "#7\t制表符分隔"])
async def test_reply_accepts_optional_space_after_number(message):
    gitea = _mock_gitea(
        issue=Issue.model_validate(ISSUE_PAYLOAD), comment=Comment.model_validate(COMMENT_PAYLOAD)
    )
    plugin = _make_plugin(gitea=gitea)
    service = SimpleNamespace(send_group_msg=AsyncMock())

    with patch("src.Api.api.asyncService", service):
        await cast(Any, GiteaReply.main).__wrapped__(plugin, _make_event(message), debug=False)

    args = gitea.create_issue_comment.await_args.args
    assert args[1] == 7
    assert "来自 QQ 群反馈" in args[2]
    service.send_group_msg.assert_awaited_once()


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


def test_plugin_construction_builds_gitea_client_from_bot_config():
    bot = cast(
        Bot,
        cast(
            object,
            SimpleNamespace(
                bot_config={"Gitea": {}},
                gitea_api_url="https://gitea.example.com",
                gitea_api_token="token",
            ),
        ),
    )
    with patch("plugins.GiteaReply.GiteaReply.Plugins.init_status", MagicMock()):
        plugin = GiteaReply(bot)

    assert plugin.gitea.api_url == "https://gitea.example.com"
    assert plugin.gitea.api_token == "token"


# ---------- 消息解析 ----------


def test_parse_reply_segments_mixed_content_in_order():
    message = (
        "登录报500[CQ:image,file=shot.image,url=https://qq/img?a=1&amp;b=2]"
        "[CQ:at,qq=10001][CQ:face,id=21]看下[CQ:json,data={...}]"
    )
    segments = parse_reply_segments(message)

    kinds = [type(s).__name__ for s in segments]
    assert kinds == ["ReplyText", "ReplyMedia", "ReplyText", "ReplyText", "ReplyText"]

    assert segments[0].text == "登录报500"
    media = segments[1]
    assert media.url == "https://qq/img?a=1&b=2"  # CQ 转义已还原
    assert media.is_image
    assert segments[2].text == "@10001"
    assert segments[3].text == "[表情]"
    assert segments[4].text == "看下"  # 未支持的 CQ 码被丢弃


def test_parse_reply_segments_media_without_url_is_kept_as_failure():
    segments = parse_reply_segments("[CQ:image,file=abc.image]")
    assert len(segments) == 1
    assert segments[0].url is None


def test_build_comment_markdown_places_media_on_own_line():
    segments = parse_reply_segments("看这个[CQ:image,file=a.image,url=https://qq/a]")
    body = build_comment_markdown("李四", segments)

    assert body.startswith("**来自 QQ 群反馈**（李四）：\n\n看这个")
    assert "{{QQ_MEDIA_0}}" in body
    # 占位符独立成行，保证 Gitea markdown 正确渲染
    assert body.splitlines()[-1].strip() == "{{QQ_MEDIA_0}}"


def test_build_comment_markdown_pure_text_unchanged():
    body = build_comment_markdown("张三", parse_reply_segments("登录一直报 500"))
    assert body == "**来自 QQ 群反馈**（张三）：\n\n登录一直报 500"


# ---------- GiteaApi 附件与编辑评论 ----------


@pytest.mark.asyncio
async def test_gitea_api_create_comment_attachment_builds_multipart(tmp_path):
    file = tmp_path / "x.png"
    file.write_bytes(b"fake png bytes")
    client_class, client = _fake_client_factory(_FakeResponse(201, ATTACHMENT_PAYLOAD))
    api = GiteaApi("https://gitea.example.com", "token")

    with patch("src.gitea.GiteaApi.AsyncClient", client_class):
        attachment = await api.create_comment_attachment(
            "owner/repo", 10, str(file), "image_0.png", "image/png"
        )

    call = client.calls[0]
    assert call["method"] == "POST"
    assert (
        call["url"] == "https://gitea.example.com/api/v1/repos/owner/repo/issues/comments/10/assets"
    )
    uploaded = call["files"]["attachment"]
    assert uploaded[0] == "image_0.png"
    assert uploaded[1] == b"fake png bytes"
    assert uploaded[2] == "image/png"
    assert attachment.uuid == "uuid-1"


@pytest.mark.asyncio
async def test_gitea_api_update_issue_comment_patches_body():
    client_class, client = _fake_client_factory(_FakeResponse(200, COMMENT_PAYLOAD))
    api = GiteaApi("https://gitea.example.com", "token")

    with patch("src.gitea.GiteaApi.AsyncClient", client_class):
        await api.update_issue_comment("owner/repo", 10, "更新后的正文")

    call = client.calls[0]
    assert call["method"] == "PATCH"
    assert call["url"] == "https://gitea.example.com/api/v1/repos/owner/repo/issues/comments/10"
    assert call["json"] == {"body": "更新后的正文"}


# ---------- 插件媒体流程 ----------


def _make_media_plugin():
    gitea = _mock_gitea(
        issue=Issue.model_validate(ISSUE_PAYLOAD),
        comment=Comment.model_validate(COMMENT_PAYLOAD),
        attachment=Attachment.model_validate(ATTACHMENT_PAYLOAD),
    )
    plugin = _make_plugin(gitea=gitea)
    service = SimpleNamespace(send_group_msg=AsyncMock())
    return plugin, gitea, service


@pytest.mark.asyncio
async def test_reply_with_image_uploads_attachment_and_patches_body():
    plugin, gitea, service = _make_media_plugin()

    async def fake_download(url, dest):
        _download_saves_png(dest)
        return True

    with (
        patch("src.Api.api.asyncService", service),
        patch.object(GiteaReply, "_download_media", staticmethod(fake_download)),
    ):
        await cast(Any, GiteaReply.main).__wrapped__(
            plugin,
            _make_event("#7 看这个[CQ:image,file=shot.image,url=https://qq/img]"),
            debug=False,
        )

    gitea.create_comment_attachment.assert_awaited_once()
    args = gitea.create_comment_attachment.await_args.args
    assert args[:2] == ("owner/repo", 10)
    assert args[3] == "image_0.png"  # 按真实图片格式命名
    assert args[4] == "image/png"

    patched_body = gitea.update_issue_comment.await_args.args[2]
    assert "![image_0.png](/attachments/uuid-1)" in patched_body
    assert "{{QQ_MEDIA_0}}" not in patched_body

    receipt = service.send_group_msg.await_args.kwargs["message"]
    assert COMMENT_PAYLOAD["html_url"] in receipt
    assert "上传失败" not in receipt


@pytest.mark.asyncio
async def test_reply_file_attachment_links_without_image_syntax():
    plugin, gitea, service = _make_media_plugin()

    async def fake_download(url, dest):
        dest.write_bytes(b"zip data")
        return True

    with (
        patch("src.Api.api.asyncService", service),
        patch.object(GiteaReply, "_download_media", staticmethod(fake_download)),
    ):
        await cast(Any, GiteaReply.main).__wrapped__(
            plugin, _make_event("#7 [CQ:file,name=报告.pdf,url=https://qq/f]"), debug=False
        )

    args = gitea.create_comment_attachment.await_args.args
    assert args[3] == "报告.pdf"
    assert args[4] == "application/pdf"
    patched_body = gitea.update_issue_comment.await_args.args[2]
    assert "[报告.pdf](/attachments/uuid-1)" in patched_body
    assert "![image" not in patched_body  # 非图片附件不用图片语法


@pytest.mark.asyncio
async def test_reply_download_failure_replaces_placeholder_and_notes_in_receipt():
    plugin, gitea, service = _make_media_plugin()

    async def fake_download(url, dest):
        return False

    with (
        patch("src.Api.api.asyncService", service),
        patch.object(GiteaReply, "_download_media", staticmethod(fake_download)),
    ):
        await cast(Any, GiteaReply.main).__wrapped__(
            plugin, _make_event("#7 [CQ:image,file=a.image,url=https://qq/a]"), debug=False
        )

    gitea.create_comment_attachment.assert_not_awaited()
    patched_body = gitea.update_issue_comment.await_args.args[2]
    assert MEDIA_FAILED_TEXT in patched_body

    receipt = service.send_group_msg.await_args.kwargs["message"]
    assert "1 个图片/附件上传失败" in receipt


@pytest.mark.asyncio
async def test_reply_upload_api_error_marks_placeholder_and_notes_in_receipt():
    plugin, gitea, service = _make_media_plugin()
    gitea.create_comment_attachment.side_effect = GiteaApiError("Gitea API 返回 413", 413)

    async def fake_download(url, dest):
        _download_saves_png(dest)
        return True

    with (
        patch("src.Api.api.asyncService", service),
        patch.object(GiteaReply, "_download_media", staticmethod(fake_download)),
    ):
        await cast(Any, GiteaReply.main).__wrapped__(
            plugin, _make_event("#7 [CQ:image,file=a.image,url=https://qq/a]"), debug=False
        )

    patched_body = gitea.update_issue_comment.await_args.args[2]
    assert MEDIA_FAILED_TEXT in patched_body
    receipt = service.send_group_msg.await_args.kwargs["message"]
    assert "1 个图片/附件上传失败" in receipt


@pytest.mark.asyncio
async def test_reply_patch_failure_notes_attachment_area_in_receipt():
    plugin, gitea, service = _make_media_plugin()
    gitea.update_issue_comment.side_effect = GiteaApiError("Gitea API 请求失败：timeout")

    async def fake_download(url, dest):
        _download_saves_png(dest)
        return True

    with (
        patch("src.Api.api.asyncService", service),
        patch.object(GiteaReply, "_download_media", staticmethod(fake_download)),
    ):
        await cast(Any, GiteaReply.main).__wrapped__(
            plugin, _make_event("#7 [CQ:image,file=a.image,url=https://qq/a]"), debug=False
        )

    receipt = service.send_group_msg.await_args.kwargs["message"]
    assert "评论正文更新失败" in receipt


@pytest.mark.asyncio
async def test_reply_without_media_skips_attachment_flow():
    plugin, gitea, service = _make_media_plugin()

    with patch("src.Api.api.asyncService", service):
        await cast(Any, GiteaReply.main).__wrapped__(
            plugin, _make_event("#7 纯文本反馈"), debug=False
        )

    gitea.create_comment_attachment.assert_not_awaited()
    gitea.update_issue_comment.assert_not_awaited()
