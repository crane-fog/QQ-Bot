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
        record = dict(kwargs)
        if "files" in record:
            # httpx 发送时会读文件对象，这里在记录时做同样的事，避免断言时文件已关闭
            name, obj, mime = record["files"]["attachment"]
            record["files"] = {
                "attachment": (name, obj.read() if hasattr(obj, "read") else obj, mime)
            }
        self.calls.append({"method": method, "url": url, **record})
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
                database=None,
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
    assert uploaded[1] == b"fake png bytes"  # fake client 已读出快照：文件对象直传而非整体预读
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
    assert f"![image_0.png]({ATTACHMENT_PAYLOAD['browser_download_url']})" in patched_body
    assert "{{QQ_MEDIA_0}}" not in patched_body

    receipt = service.send_group_msg.await_args.kwargs["message"]
    assert COMMENT_PAYLOAD["html_url"] in receipt
    assert "上传失败" not in receipt


@pytest.mark.asyncio
async def test_reply_file_cq_code_is_ignored():
    """QQ 群文件走独立上传事件，[CQ:file] 不是消息段；仅剩不支持内容时不产生空评论。"""
    plugin, gitea, service = _make_media_plugin()

    with patch("src.Api.api.asyncService", service):
        await cast(Any, GiteaReply.main).__wrapped__(
            plugin, _make_event("#7 [CQ:file,name=报告.pdf,url=https://qq/f]"), debug=False
        )

    gitea.get_issue.assert_not_awaited()
    gitea.create_issue_comment.assert_not_awaited()
    gitea.update_issue_comment.assert_not_awaited()
    service.send_group_msg.assert_not_awaited()


@pytest.mark.asyncio
async def test_reply_file_code_dropped_when_text_present():
    """正文和 [CQ:file] 混合时，码被丢弃、文本正常发送且不触发附件流程。"""
    plugin, gitea, service = _make_media_plugin()

    with patch("src.Api.api.asyncService", service):
        await cast(Any, GiteaReply.main).__wrapped__(
            plugin, _make_event("#7 看日志[CQ:file,name=报告.pdf,url=https://qq/f]"), debug=False
        )

    assert gitea.create_issue_comment.await_args.args[2] == "**来自 QQ 群反馈**（张三）：\n\n看日志"
    gitea.create_comment_attachment.assert_not_awaited()
    gitea.update_issue_comment.assert_not_awaited()


@pytest.mark.asyncio
async def test_reply_prefers_local_path_from_message_recorder(tmp_path):
    """MessageRecorder 已把图片下到本地并改写 CQ 码（path 字段、删 url），应直接使用本地文件。"""
    plugin, gitea, service = _make_media_plugin()
    local_img = tmp_path / "recorder.png"
    Image.new("RGB", (1, 1)).save(local_img, "PNG")

    with (
        patch("src.Api.api.asyncService", service),
        patch.object(GiteaReply, "_download_media", new=AsyncMock()) as fake_download,
    ):
        await cast(Any, GiteaReply.main).__wrapped__(
            plugin,
            _make_event(f"#7 [CQ:image,file=a.image,path={local_img.as_posix()}]"),
            debug=False,
        )

    fake_download.assert_not_awaited()  # 有本地文件就不该再下载
    args = gitea.create_comment_attachment.await_args.args
    assert args[2] == str(local_img)
    assert args[3] == "image_0.png"
    patched_body = gitea.update_issue_comment.await_args.args[2]
    assert ATTACHMENT_PAYLOAD["browser_download_url"] in patched_body
    receipt = service.send_group_msg.await_args.kwargs["message"]
    assert "上传失败" not in receipt


@pytest.mark.asyncio
async def test_reply_local_path_missing_fails_without_fallback(tmp_path):
    """path 指向的本地文件不存在（如 OneBot 与 Bot 不同机）且 url 已被删时，无法回退只能失败。"""
    plugin, gitea, service = _make_media_plugin()
    missing = tmp_path / "missing.png"

    with (
        patch("src.Api.api.asyncService", service),
        patch.object(GiteaReply, "_download_media", new=AsyncMock()) as fake_download,
    ):
        await cast(Any, GiteaReply.main).__wrapped__(
            plugin,
            _make_event(f"#7 [CQ:image,file=a.image,path={missing.as_posix()}]"),
            debug=False,
        )

    fake_download.assert_not_awaited()
    patched_body = gitea.update_issue_comment.await_args.args[2]
    assert MEDIA_FAILED_TEXT in patched_body
    receipt = service.send_group_msg.await_args.kwargs["message"]
    assert "1 个图片/附件上传失败" in receipt


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


# ---------- 审查补充：多媒体、白名单、真实下载路径、装饰器层 ----------


@pytest.mark.asyncio
async def test_reply_multiple_media_upload_in_order():
    plugin, gitea, service = _make_media_plugin()
    gitea.create_comment_attachment.side_effect = [
        Attachment.model_validate(ATTACHMENT_PAYLOAD),
        Attachment.model_validate(
            {
                **ATTACHMENT_PAYLOAD,
                "uuid": "uuid-2",
                "browser_download_url": "https://gitea.example.com/attachments/uuid-2",
            }
        ),
    ]

    async def fake_download(url, dest):
        _download_saves_png(dest)
        return True

    message = "#7 图一[CQ:image,file=a.image,url=https://gchat.qpic.cn/a]图二[CQ:image,file=b.image,url=https://gchat.qpic.cn/b]"
    with (
        patch("src.Api.api.asyncService", service),
        patch.object(GiteaReply, "_download_media", staticmethod(fake_download)),
    ):
        await cast(Any, GiteaReply.main).__wrapped__(plugin, _make_event(message), debug=False)

    assert gitea.create_comment_attachment.await_count == 2
    patched_body = gitea.update_issue_comment.await_args.args[2]
    pos1 = patched_body.find(ATTACHMENT_PAYLOAD["browser_download_url"])
    pos2 = patched_body.find("uuid-2")
    assert 0 <= pos1 < pos2  # 链接按消息中的出现顺序回填
    assert "{{QQ_MEDIA" not in patched_body
    receipt = service.send_group_msg.await_args.kwargs["message"]
    assert "上传失败" not in receipt


@pytest.mark.asyncio
async def test_reply_partial_media_failure_keeps_successful_one():
    plugin, gitea, service = _make_media_plugin()
    gitea.create_comment_attachment.side_effect = [
        Attachment.model_validate(ATTACHMENT_PAYLOAD),
        GiteaApiError("Gitea API 返回 500", 500),
    ]

    async def fake_download(url, dest):
        _download_saves_png(dest)
        return True

    message = "#7[CQ:image,file=a.image,url=https://gchat.qpic.cn/a][CQ:image,file=b.image,url=https://gchat.qpic.cn/b]"
    with (
        patch("src.Api.api.asyncService", service),
        patch.object(GiteaReply, "_download_media", staticmethod(fake_download)),
    ):
        await cast(Any, GiteaReply.main).__wrapped__(plugin, _make_event(message), debug=False)

    patched_body = gitea.update_issue_comment.await_args.args[2]
    assert ATTACHMENT_PAYLOAD["browser_download_url"] in patched_body
    assert patched_body.count(MEDIA_FAILED_TEXT) == 1
    receipt = service.send_group_msg.await_args.kwargs["message"]
    assert "1 个图片/附件上传失败" in receipt


@pytest.mark.asyncio
async def test_reply_video_uploads_as_attachment_link():
    plugin, gitea, service = _make_media_plugin()

    async def fake_download(url, dest):
        dest.write_bytes(b"mp4 data")
        return True

    with (
        patch("src.Api.api.asyncService", service),
        patch.object(GiteaReply, "_download_media", staticmethod(fake_download)),
    ):
        await cast(Any, GiteaReply.main).__wrapped__(
            plugin,
            _make_event("#7[CQ:video,name=录屏.mp4,url=https://multimedia.nt.qq.com.cn/c]"),
            debug=False,
        )

    args = gitea.create_comment_attachment.await_args.args
    assert args[3] == "录屏.mp4"
    assert args[4] == "video/mp4"
    patched_body = gitea.update_issue_comment.await_args.args[2]
    assert f"[录屏.mp4]({ATTACHMENT_PAYLOAD['browser_download_url']})" in patched_body


def test_is_allowed_media_url_whitelist():
    from plugins.GiteaReply.GiteaReply import is_allowed_media_url

    assert is_allowed_media_url("https://gchat.qpic.cn/a.png")
    assert is_allowed_media_url("https://multimedia.nt.qq.com.cn/download?x=1")
    assert is_allowed_media_url("http://download.qq.com/f")
    # 相似域名伪装：必须完整后缀匹配
    assert not is_allowed_media_url("https://evilqq.com/a.png")
    assert not is_allowed_media_url("https://gchat.qpic.cn.evil.com/a.png")
    assert not is_allowed_media_url("http://169.254.169.254/latest/meta-data")
    assert not is_allowed_media_url("ftp://gchat.qpic.cn/a")
    assert not is_allowed_media_url("not-a-url")


class _FakeStreamResponse:
    def __init__(self, chunks, status_code=200):
        self._chunks = chunks
        self.status_code = status_code
        self.headers: dict[str, str] = {}

    @property
    def is_redirect(self) -> bool:
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class _FakeStreamClient:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def stream(self, method, url):
        self.method, self.url = method, url

        class _CM:
            async def __aenter__(self_inner):
                return self.response

            async def __aexit__(self_inner, *args):
                return False

        return _CM()


@pytest.mark.asyncio
async def test_download_media_streams_chunks_to_file(tmp_path, monkeypatch):
    import importlib

    gitea_reply_module = importlib.import_module("plugins.GiteaReply.GiteaReply")
    client = _FakeStreamClient(_FakeStreamResponse([b"hello ", b"world"]))
    monkeypatch.setattr(gitea_reply_module, "AsyncClient", lambda *a, **k: client)
    dest = tmp_path / "img.bin"

    ok = await GiteaReply._download_media("https://gchat.qpic.cn/a.png", dest)

    assert ok
    assert dest.read_bytes() == b"hello world"
    assert (client.method, client.url) == ("GET", "https://gchat.qpic.cn/a.png")


@pytest.mark.asyncio
async def test_download_media_http_error_returns_false(tmp_path, monkeypatch):
    import importlib

    gitea_reply_module = importlib.import_module("plugins.GiteaReply.GiteaReply")
    client = _FakeStreamClient(_FakeStreamResponse([b"x"], status_code=500))
    monkeypatch.setattr(gitea_reply_module, "AsyncClient", lambda *a, **k: client)

    ok = await GiteaReply._download_media("https://gchat.qpic.cn/a.png", tmp_path / "img.bin")

    assert not ok


@pytest.mark.asyncio
async def test_request_json_wraps_json_parse_failure():
    class _BadJsonClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def request(self, method, url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.text = "<html>"
            resp.json.side_effect = ValueError("not json")
            return resp

    api = GiteaApi("https://gitea.example.com", "token")
    with patch("src.gitea.GiteaApi.AsyncClient", lambda *a, **k: _BadJsonClient()):
        with pytest.raises(GiteaApiError, match="响应解析失败"):
            await api.get_issue("owner/repo", 7)


@pytest.mark.asyncio
async def test_wrapper_ignores_group_not_in_whitelist():
    gitea = _mock_gitea(issue=ISSUE_PAYLOAD, comment=COMMENT_PAYLOAD)
    plugin = _make_plugin(gitea=gitea)
    plugin.effected_groups = []  # 装饰器层的群白名单为空
    service = SimpleNamespace(send_group_msg=AsyncMock())

    with patch("src.Api.api.asyncService", service):
        await cast(Any, GiteaReply.main)(plugin, _make_event("#7 内容"), debug=False)

    gitea.get_issue.assert_not_awaited()
    service.send_group_msg.assert_not_awaited()


@pytest.mark.asyncio
async def test_wrapper_ignores_message_without_call_word():
    gitea = _mock_gitea(issue=ISSUE_PAYLOAD, comment=COMMENT_PAYLOAD)
    plugin = _make_plugin(gitea=gitea)
    plugin.effected_groups = [20001]
    service = SimpleNamespace(send_group_msg=AsyncMock())

    with patch("src.Api.api.asyncService", service):
        await cast(Any, GiteaReply.main)(plugin, _make_event("hello #7"), debug=False)

    gitea.get_issue.assert_not_awaited()
    service.send_group_msg.assert_not_awaited()


class _RedirectResponse:
    def __init__(self, location: str, status_code: int = 302):
        self.status_code = status_code
        self.headers = {"location": location}

    @property
    def is_redirect(self) -> bool:
        return self.status_code in (301, 302, 303, 307, 308) and "location" in self.headers

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")


class _QueueStreamClient:
    """按请求顺序返回响应的 fake client，记录每次请求的 URL 供断言。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.urls: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def stream(self, method, url):
        self.urls.append(url)
        response = self.responses.pop(0)

        class _CM:
            async def __aenter__(self_inner):
                return response

            async def __aexit__(self_inner, *args):
                return False

        return _CM()


def _import_reply_module():
    import importlib

    return importlib.import_module("plugins.GiteaReply.GiteaReply")


@pytest.mark.asyncio
async def test_download_media_follows_whitelisted_redirect(tmp_path, monkeypatch):
    module = _import_reply_module()
    client = _QueueStreamClient(
        [
            _RedirectResponse("https://multimedia.nt.qq.com.cn/real"),
            _FakeStreamResponse([b"data"]),
        ]
    )
    monkeypatch.setattr(module, "AsyncClient", lambda *a, **k: client)
    dest = tmp_path / "img.bin"

    ok = await GiteaReply._download_media("https://gchat.qpic.cn/a", dest)

    assert ok
    assert dest.read_bytes() == b"data"
    assert client.urls == ["https://gchat.qpic.cn/a", "https://multimedia.nt.qq.com.cn/real"]


@pytest.mark.asyncio
async def test_download_media_rejects_redirect_off_whitelist(tmp_path, monkeypatch):
    module = _import_reply_module()
    client = _QueueStreamClient(
        [_RedirectResponse("https://evil.example.com/x"), _FakeStreamResponse([b"secret"])]
    )
    monkeypatch.setattr(module, "AsyncClient", lambda *a, **k: client)
    dest = tmp_path / "img.bin"

    ok = await GiteaReply._download_media("https://gchat.qpic.cn/a", dest)

    assert not ok
    # 重定向目标在校验阶段就被拒绝，不会真正请求
    assert client.urls == ["https://gchat.qpic.cn/a"]
    assert not dest.exists()


@pytest.mark.asyncio
async def test_download_media_aborts_on_oversize(tmp_path, monkeypatch):
    module = _import_reply_module()
    client = _QueueStreamClient([_FakeStreamResponse([b"x" * 30])])
    monkeypatch.setattr(module, "AsyncClient", lambda *a, **k: client)
    monkeypatch.setattr(module, "MAX_MEDIA_BYTES", 10)
    dest = tmp_path / "img.bin"

    ok = await GiteaReply._download_media("https://gchat.qpic.cn/a", dest)

    assert not ok
    assert not dest.exists()  # 半截文件被清理


@pytest.mark.asyncio
async def test_download_media_gives_up_after_max_redirects(tmp_path, monkeypatch):
    module = _import_reply_module()
    client = _QueueStreamClient(
        [_RedirectResponse(f"https://gchat.qpic.cn/hop{i}") for i in range(6)]
    )
    monkeypatch.setattr(module, "AsyncClient", lambda *a, **k: client)
    dest = tmp_path / "img.bin"

    ok = await GiteaReply._download_media("https://gchat.qpic.cn/a", dest)

    assert not ok
    # 首跳 + 3 次重定向复检，第 5 次请求前超限中止
    assert len(client.urls) == 4


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    def __init__(self, value):
        self._value = value

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, query):
        return _FakeResult(self._value)


@pytest.mark.asyncio
async def test_reply_uses_recorded_message_from_db(tmp_path):
    """MessageRecorder 的改写副本只入库：应按 sql_id 查库取本地 path，而不是从 event.message 下载。"""
    plugin, gitea, service = _make_media_plugin()
    local_img = tmp_path / "recorder.png"
    Image.new("RGB", (1, 1)).save(local_img, "PNG")
    recorded = f"#7 [CQ:image,file=a.image,path={local_img.as_posix()}]"
    plugin.session_factory = lambda: _FakeSession(recorded)

    event = _make_event("#7 [CQ:image,file=a.image,url=https://gchat.qpic.cn/a]")
    event.sql_id = 42  # event.message 是原始码，path 只在数据库副本里

    with (
        patch("src.Api.api.asyncService", service),
        patch.object(GiteaReply, "_download_media", new=AsyncMock()) as fake_download,
    ):
        await cast(Any, GiteaReply.main).__wrapped__(plugin, event, debug=False)

    fake_download.assert_not_awaited()
    args = gitea.create_comment_attachment.await_args.args
    assert args[2] == str(local_img)
    receipt = service.send_group_msg.await_args.kwargs["message"]
    assert "上传失败" not in receipt


@pytest.mark.asyncio
async def test_reply_falls_back_to_event_message_when_db_has_no_record(tmp_path):
    """查无记录（MessageRecorder 未启用/写库失败）时回退按 url 下载。"""
    plugin, gitea, service = _make_media_plugin()
    plugin.session_factory = lambda: _FakeSession(None)

    async def fake_download(url, dest):
        _download_saves_png(dest)
        return True

    event = _make_event("#7 [CQ:image,file=a.image,url=https://gchat.qpic.cn/a]")
    event.sql_id = 42

    with (
        patch("src.Api.api.asyncService", service),
        patch.object(GiteaReply, "_download_media", staticmethod(fake_download)),
    ):
        await cast(Any, GiteaReply.main).__wrapped__(plugin, event, debug=False)

    gitea.create_comment_attachment.assert_awaited_once()
    receipt = service.send_group_msg.await_args.kwargs["message"]
    assert "上传失败" not in receipt
