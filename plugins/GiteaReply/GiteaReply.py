import mimetypes
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from httpx import AsyncClient, Timeout
from PIL import Image

from plugins import Plugins, plugin_main
from src.Api import api
from src.event_handler.GroupMessageEventHandler import GroupMessageEvent
from src.gitea.GiteaApi import GiteaApi, GiteaApiError
from src.PrintLog import Log
from utils.CQHelper import CQHelper, CQTextSegment
from utils.TextUtils import sanitize_filename

# #<issue编号> + 内容，编号和内容间的空格可有可无；纯编号（无内容）不触发
REPLY_PATTERN = re.compile(r"^#(?P<number>\d+)\s*(?P<body>\S.*)$", re.DOTALL)

# 占位符需要足够怪异，避免和群友输入的普通文本撞车
MEDIA_FAILED_TEXT = "*[图片/附件上传失败]*"

# 作为附件上传的媒体类型；其余 CQ 码（表情、json 卡片等）不转发。
# 注意 file 不是消息段：QQ 群文件走独立的群文件上传事件，不会出现在消息文本里
MEDIA_CQ_TYPES = {"image", "video"}

# 媒体下载仅允许腾讯 CDN 域名（后缀匹配），防止伪造 CQ 码让 Bot 探测内网
# NTQQ 实现的媒体在 multimedia.nt.qq.com.cn（qq.com.cn 后缀），老版本图片在 gchat.qpic.cn
ALLOWED_MEDIA_HOST_SUFFIXES = ("qpic.cn", "qq.com", "qq.com.cn")

# 重定向需要逐跳复检白名单，因此手动跟随而不是交给 httpx
MAX_MEDIA_REDIRECTS = 3
# 流式下载的体积上限，防止异常响应写满磁盘
MAX_MEDIA_BYTES = 100 * 1024 * 1024


@dataclass
class ReplyText:
    text: str


@dataclass
class ReplyMedia:
    url: str | None
    name: str
    is_image: bool
    # MessageRecorder 会预先下载图片并把本地路径写进 CQ 码的 path 字段（同时删除 url）
    local_path: str | None = None
    placeholder: str = ""


def is_allowed_media_url(url: str) -> bool:
    """校验媒体 URL 的 scheme 与 host 是否在腾讯 CDN 白名单内。"""
    try:
        parts = urlsplit(url)
    except Exception:
        return False
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return False
    host = parts.hostname or ""
    return any(host == s or host.endswith("." + s) for s in ALLOWED_MEDIA_HOST_SUFFIXES)


def parse_reply_segments(body: str, debug: bool = False) -> list[ReplyText | ReplyMedia]:
    """把 OneBot 字符串消息按序拆成可转发的文本和媒体段。

    图片/视频提取为 ReplyMedia；@人 和表情转为可读文本；其余 CQ 码丢弃。
    保序拆分与 CQ 反转义由 CQHelper.parse_segments 提供，这里只做 Gitea 语义归类。
    """
    segments: list[ReplyText | ReplyMedia] = []
    media_count = 0
    for seg in CQHelper.parse_segments(body):
        if isinstance(seg, CQTextSegment):
            segments.append(ReplyText(seg.text))
            continue

        cq_type = seg.cq_type
        if cq_type in MEDIA_CQ_TYPES:
            media_count += 1
            segments.append(
                ReplyMedia(
                    url=seg.params.get("url"),
                    name=seg.params.get("name") or seg.params.get("file") or f"media_{media_count}",
                    is_image=cq_type == "image",
                    local_path=seg.params.get("path"),
                )
            )
        elif cq_type == "at":
            segments.append(ReplyText(f"@{seg.params.get('qq', '?')}"))
        elif cq_type in ("face", "mface"):
            segments.append(ReplyText("[表情]"))
        else:
            Log.debug(f"GiteaReply 忽略 CQ 码：{cq_type}", debug)
    return segments


def build_comment_markdown(sender: str, segments: list[ReplyText | ReplyMedia]) -> str:
    """组装评论正文：文本原样保留，媒体替换为独立成行的占位符，附件上传后回填。"""
    parts = [f"**来自 QQ 群反馈**（{sender}）：\n\n"]
    media_idx = 0
    for seg in segments:
        if isinstance(seg, ReplyText):
            parts.append(seg.text)
        else:
            # f-string 四花括号输出双花括号占位符，形如 {{QQ_MEDIA_0}}
            seg.placeholder = f"{{{{QQ_MEDIA_{media_idx}}}}}"
            media_idx += 1
            parts.append(f"\n\n{seg.placeholder}\n\n")
    return "".join(parts).strip()


def _sniff_image_info(path: Path, idx: int) -> tuple[str, str]:
    """按图片真实格式返回 (文件名, MIME)，识别失败按 PNG 兜底。"""
    fmt = "PNG"
    try:
        with Image.open(path) as img:
            fmt = (img.format or "PNG").upper()
    except Exception as e:
        Log.warning(f"GiteaReply 识别图片格式失败：{path}, error={e}")
    ext = "jpg" if fmt == "JPEG" else fmt.lower()
    mime = "image/jpeg" if fmt == "JPEG" else f"image/{ext}"
    return f"image_{idx}.{ext}", mime


class GiteaReply(Plugins):
    def __init__(self, bot):
        super().__init__(bot)
        self.name = "GiteaReply"
        self.type = "Group"
        self.author = "oierxjn"
        self.introduction = """
                                把 QQ 群消息回复到 Gitea issue
                                usage: #<issue编号><内容>
                            """
        # 框架在 __init__ 之后才注入 config，插件配置只能在 main 里读取
        self.gitea = GiteaApi(self.bot.gitea_api_url, self.bot.gitea_api_token)
        self.init_status()

    @plugin_main(call_word=["#"])
    async def main(self, event: GroupMessageEvent, debug: bool):
        match = REPLY_PATTERN.match(event.message.strip())
        if not match:
            return

        repo = str((self.config or {}).get("reply_repo", "")).strip()
        if not repo:
            Log.warning("GiteaReply 未配置 reply_repo（plugins.toml [GiteaReply]），忽略回帖请求")
            return

        segments = parse_reply_segments(match["body"], debug)
        media_list = [s for s in segments if isinstance(s, ReplyMedia)]
        text = "".join(s.text for s in segments if isinstance(s, ReplyText)).strip()
        # 只剩无法转发的内容（如纯表情刷屏）时不产生空评论
        if not text and not media_list:
            return

        number = int(match["number"])
        sender = event.card or event.nickname or str(event.user_id)
        comment_body = build_comment_markdown(sender, segments)

        try:
            issue = await self.gitea.get_issue(repo, number)
            comment = await self.gitea.create_issue_comment(repo, number, comment_body)
        except GiteaApiError as e:
            hint = (
                f"issue #{number} 不存在，请确认编号" if e.status_code == 404 else f"回复失败：{e}"
            )
            await api.asyncService.send_group_msg(
                group_id=event.group_id, message=f"[Gitea] {hint}"
            )
            return

        failed_count, patched = 0, True
        if media_list:
            failed_count, patched = await self._attach_media(
                repo, comment.id, media_list, comment_body
            )

        Log.info(f"GiteaReply 已回复 issue #{number}（群{event.group_id}，{sender}）")
        receipt = f"[Gitea] 已回复 issue #{number}「{issue.title}」\n{comment.html_url}"
        if failed_count:
            receipt += f"\n注意：有 {failed_count} 个图片/附件上传失败"
        elif media_list and not patched:
            receipt += "\n注意：评论正文更新失败，图片请到 Gitea 评论附件区查看"
        await api.asyncService.send_group_msg(group_id=event.group_id, message=receipt)

    async def _attach_media(
        self, repo: str, comment_id: int, media_list: list[ReplyMedia], body: str
    ) -> tuple[int, bool]:
        """把媒体上传为评论附件并回填占位符，返回 (失败数, 正文是否成功更新)。"""
        temp_dir = Path(tempfile.mkdtemp(prefix="gitea_reply_"))
        failed = 0
        try:
            for idx, media in enumerate(media_list):
                local = await self._resolve_media_file(temp_dir, idx, media)
                if local is None:
                    body = body.replace(media.placeholder, MEDIA_FAILED_TEXT)
                    failed += 1
                    continue
                filename, mime = self._upload_file_info(local, idx, media)
                try:
                    attachment = await self.gitea.create_comment_attachment(
                        repo, comment_id, str(local), filename, mime
                    )
                except GiteaApiError as e:
                    Log.warning(
                        f"GiteaReply 上传附件失败：{media.local_path or media.url}, error={e}"
                    )
                    body = body.replace(media.placeholder, MEDIA_FAILED_TEXT)
                    failed += 1
                    continue
                link = attachment.browser_download_url
                rendered = f"![{filename}]({link})" if media.is_image else f"[{filename}]({link})"
                body = body.replace(media.placeholder, rendered)
            try:
                await self.gitea.update_issue_comment(repo, comment_id, body)
            except GiteaApiError as e:
                Log.error(f"GiteaReply 更新评论正文失败：comment_id={comment_id}, error={e}")
                return failed, False
            return failed, True
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def _resolve_media_file(self, temp_dir: Path, idx: int, media: ReplyMedia) -> Path | None:
        """定位媒体文件：优先 CQ 码中的本地 path（MessageRecorder 预下载），否则从 url 下载。"""
        if media.local_path:
            path = Path(media.local_path)
            if path.is_file():
                return path
            # 码被 MessageRecorder 改写后 url 已删除，本地又读不到（如 OneBot 与 Bot 不同机）时无法回退
            Log.warning(f"GiteaReply 本地媒体文件不存在：{media.local_path}")
            return None
        if not media.url:
            return None
        local = temp_dir / f"{idx:02d}_{sanitize_filename(media.name) or 'media'}"
        if await self._download_media(media.url, local):
            return local
        return None

    def _upload_file_info(self, local: Path, idx: int, media: ReplyMedia) -> tuple[str, str]:
        if media.is_image:
            return _sniff_image_info(local, idx)
        name = sanitize_filename(media.name) or f"attachment_{idx}.bin"
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        return name, mime

    @staticmethod
    async def _download_media(url: str, dest: Path) -> bool:
        """流式下载 QQ 媒体到本地，失败返回 False。

        重定向手动跟随并逐跳复检白名单（follow_redirects=True 会绕过首跳校验），
        写入时限制最大体积，失败时清理半截文件。
        """
        ok = False
        try:
            async with AsyncClient(timeout=Timeout(30), follow_redirects=False) as client:
                target = url
                redirects = 0
                while True:
                    if not is_allowed_media_url(target):
                        Log.warning(f"GiteaReply 拒绝非白名单媒体 URL：{target}")
                        return False
                    async with client.stream("GET", target) as resp:
                        if resp.is_redirect:
                            redirects += 1
                            location = resp.headers.get("location", "")
                            if redirects > MAX_MEDIA_REDIRECTS or not location:
                                Log.warning(f"GiteaReply 媒体重定向异常，中止下载：{url}")
                                return False
                            target = urljoin(target, location)
                            continue
                        resp.raise_for_status()
                        received = 0
                        with open(dest, "wb") as f:
                            async for chunk in resp.aiter_bytes():
                                received += len(chunk)
                                if received > MAX_MEDIA_BYTES:
                                    Log.warning(f"GiteaReply 媒体超过大小上限，中止下载：{url}")
                                    return False
                                f.write(chunk)
                    ok = True
                    return True
        except Exception as e:
            Log.warning(f"GiteaReply 下载 QQ 媒体失败：url={url}, error={e}")
            return False
        finally:
            if not ok:
                dest.unlink(missing_ok=True)
