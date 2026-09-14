import mimetypes
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from httpx import AsyncClient, Timeout
from PIL import Image

from plugins import Plugins, plugin_main
from src.Api import api
from src.event_handler.GroupMessageEventHandler import GroupMessageEvent
from src.gitea.GiteaApi import GiteaApi, GiteaApiError
from src.PrintLog import Log
from utils.TextUtils import sanitize_filename

# #<issue编号> <内容>，要求编号后有空格且内容非空，避免群里的 #话题# 式闲聊误触
REPLY_PATTERN = re.compile(r"^#(?P<number>\d+)\s+(?P<body>\S.*)$", re.DOTALL)

# CQ 码参数值按 CQ 转义规则编码（逗号转义为 &#44;），所以按裸逗号切分参数是安全的
CQ_CODE_PATTERN = re.compile(r"\[CQ:(?P<type>\w+)(?:,(?P<params>[^\]]*))?\]")

# 占位符需要足够怪异，避免和群友输入的普通文本撞车
MEDIA_FAILED_TEXT = "*[图片/附件上传失败]*"

# 作为附件上传的媒体类型；其余 CQ 码（表情、json 卡片等）不转发
MEDIA_CQ_TYPES = {"image", "file", "video"}


@dataclass
class ReplyText:
    text: str


@dataclass
class ReplyMedia:
    url: str | None
    name: str
    is_image: bool
    placeholder: str = ""


def cq_unescape(text: str) -> str:
    """按 CQ 码转义规则还原文本；&amp; 必须最后处理，避免二次反转义。"""
    return (
        text.replace("&#44;", ",").replace("&#91;", "[").replace("&#93;", "]").replace("&amp;", "&")
    )


def parse_cq_params(raw: str) -> dict[str, str]:
    params: dict[str, str] = {}
    for item in raw.split(","):
        key, _, value = item.partition("=")
        if key:
            params[key] = cq_unescape(value)
    return params


def parse_reply_segments(body: str) -> list[ReplyText | ReplyMedia]:
    """把 OneBot 字符串消息按序拆成文本和媒体段。

    图片/文件/视频提取为 ReplyMedia；@人 和表情转为可读文本；其余 CQ 码丢弃。
    """
    segments: list[ReplyText | ReplyMedia] = []
    media_count = 0
    pos = 0
    for m in CQ_CODE_PATTERN.finditer(body):
        if m.start() > pos:
            segments.append(ReplyText(cq_unescape(body[pos : m.start()])))
        pos = m.end()

        cq_type = m["type"]
        params = parse_cq_params(m["params"] or "")
        if cq_type in MEDIA_CQ_TYPES:
            media_count += 1
            segments.append(
                ReplyMedia(
                    url=params.get("url"),
                    name=params.get("name") or params.get("file") or f"media_{media_count}",
                    is_image=cq_type == "image",
                )
            )
        elif cq_type == "at":
            segments.append(ReplyText(f"@{params.get('qq', '?')}"))
        elif cq_type in ("face", "mface"):
            segments.append(ReplyText("[表情]"))
        else:
            Log.debug(f"GiteaReply 忽略 CQ 码：{cq_type}")
    if pos < len(body):
        segments.append(ReplyText(cq_unescape(body[pos:])))
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
                                usage: #<issue编号> <内容>（支持图片和文件附件）
                            """
        self.repo = str(self.bot.bot_config.get("Gitea", {}).get("reply_repo", "")).strip()
        if not self.repo:
            Log.error("GiteaReply 插件未配置 [Gitea] reply_repo，收到回帖请求时将被忽略")
        self.gitea = GiteaApi(self.bot.gitea_api_url, self.bot.gitea_api_token)
        self.init_status()

    @plugin_main(call_word=["#"])
    async def main(self, event: GroupMessageEvent, debug: bool):
        match = REPLY_PATTERN.match(event.message.strip())
        if not match or not self.repo:
            return

        segments = parse_reply_segments(match["body"])
        media_list = [s for s in segments if isinstance(s, ReplyMedia)]
        text = "".join(s.text for s in segments if isinstance(s, ReplyText)).strip()
        # 只剩无法转发的内容（如纯表情刷屏）时不产生空评论
        if not text and not media_list:
            return

        number = int(match["number"])
        sender = event.card or event.nickname or str(event.user_id)
        comment_body = build_comment_markdown(sender, segments)

        try:
            issue = await self.gitea.get_issue(self.repo, number)
            comment = await self.gitea.create_issue_comment(self.repo, number, comment_body)
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
                self.repo, comment.id, media_list, comment_body
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
                local = temp_dir / f"{idx:02d}_{sanitize_filename(media.name) or 'media'}"
                if not media.url or not await self._download_media(media.url, local):
                    body = body.replace(media.placeholder, MEDIA_FAILED_TEXT)
                    failed += 1
                    continue
                filename, mime = self._upload_file_info(local, idx, media)
                try:
                    attachment = await self.gitea.create_comment_attachment(
                        repo, comment_id, str(local), filename, mime
                    )
                except GiteaApiError as e:
                    Log.warning(f"GiteaReply 上传附件失败：{media.url}, error={e}")
                    body = body.replace(media.placeholder, MEDIA_FAILED_TEXT)
                    failed += 1
                    continue
                link = f"/attachments/{attachment.uuid}"
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

    def _upload_file_info(self, local: Path, idx: int, media: ReplyMedia) -> tuple[str, str]:
        if media.is_image:
            return _sniff_image_info(local, idx)
        name = sanitize_filename(media.name) or f"attachment_{idx}.bin"
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        return name, mime

    @staticmethod
    async def _download_media(url: str, dest: Path) -> bool:
        """下载 QQ 媒体到本地；QQ CDN 无需鉴权，单张失败返回 False。"""
        try:
            async with AsyncClient(timeout=Timeout(30)) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                dest.write_bytes(resp.content)
            return True
        except Exception as e:
            Log.warning(f"GiteaReply 下载 QQ 媒体失败：url={url}, error={e}")
            return False
