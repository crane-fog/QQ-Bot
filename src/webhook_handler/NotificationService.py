import asyncio
import shutil
import tempfile
from collections.abc import Awaitable
from pathlib import Path
from typing import Any

from httpx import AsyncClient, Timeout

from src.Api import Api
from src.gitea.GiteaEventFormatter import (
    ContentNode,
    FileSegment,
    ForwardPlan,
    GiteaEventFormatter,
    ImageSegment,
    TextSegment,
    _extract_images,
    _parse_comment_segments,
)
from src.gitea.Models import Comment, GiteaIssueCommentEvent, GiteaIssuesEvent, GiteaWebhookEvent
from src.PrintLog import Log
from src.webhook_handler.EventConfig import EventConfig
from utils.CQType import Forward
from utils.TextUtils import format_size, sanitize_filename


class NotificationService:
    api: Api
    response_group: int
    gitea_api_url: str
    gitea_api_token: str
    formatter: GiteaEventFormatter

    def __init__(self, api: Api, response_group: int, gitea_api_url: str, gitea_api_token: str):
        self.api = api
        self.response_group = response_group
        self.gitea_api_url = gitea_api_url.rstrip("/")
        self.gitea_api_token = gitea_api_token
        self.formatter = GiteaEventFormatter()

    async def send(self, data: GiteaWebhookEvent, event_type: str, config: EventConfig) -> None:
        try:
            if config.forward:
                if isinstance(data, GiteaIssueCommentEvent):
                    await self._send_issue_comment_notification(data, event_type)
                elif isinstance(data, GiteaIssuesEvent):
                    await self._send_issues_notification(data, event_type)
                else:
                    raise TypeError(f"forward=True 不支持 {type(data).__name__} 类型")
            else:
                await self._send_plain_text(data, event_type)
        except Exception as e:
            Log.error(f"发送 Gitea webhook 通知失败：event_type={event_type}, error={e}")

    async def _fetch_issue_comments(self, full_name: str, issue_number: int) -> list[Comment]:
        url = f"{self.gitea_api_url}/api/v1/repos/{full_name}/issues/{issue_number}/comments"
        async with AsyncClient(timeout=Timeout(10)) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"token {self.gitea_api_token}"},
            )
            resp.raise_for_status()
            return [Comment.model_validate(c) for c in resp.json()]

    async def _download_images(
        self, images: list[ImageSegment], temp_dir: Path
    ) -> dict[str, str | None]:
        """
        带鉴权并发下载图片到临时目录，返回 {url: 本地路径}；单张失败映射 None。

        Args:
            images: 图片段列表
            temp_dir: 临时目录

        Returns:
            图片 URL 映射到本地路径的字典，失败时映射 None
        """
        if not images:
            return {}

        headers = {"Authorization": f"token {self.gitea_api_token}"}
        result: dict[str, str | None] = {}

        async def _download_one(client: AsyncClient, idx: int, image: ImageSegment) -> None:
            # 用图片 alt 做文件名前缀，保证可识别
            name = sanitize_filename(image.alt) or f"{idx:02d}"
            # 强制 .png 扩展名，便于 OneBot 端识别图片类型
            path = temp_dir / f"{idx:02d}_{name}.png"
            try:
                resp = await client.get(image.url, headers=headers, timeout=Timeout(30))
                resp.raise_for_status()
                path.write_bytes(resp.content)
                result[image.url] = str(path)
            except Exception as e:
                Log.warning(f"下载 Gitea 图片失败：url={image.url}, error={e}")
                result[image.url] = None

        seen: set[str] = set()
        # 收集所有下载任务，URL 去重后并发执行
        tasks: list[Awaitable[None]] = []
        async with AsyncClient() as client:
            for idx, image in enumerate(images):
                if image.url in seen:
                    continue
                seen.add(image.url)
                tasks.append(_download_one(client, idx, image))
            await asyncio.gather(*tasks)
        return result

    def _build_forward_from_plan(
        self, plan: ForwardPlan, image_paths: dict[str, str | None]
    ) -> Forward:
        """把 ForwardPlan 组装成合并转发消息，图片用本地路径，下载失败的标记占位。"""
        forward = Forward()
        # 头部节点：issue 摘要信息
        forward.add_node(type="text", sender_name="Gitea", msg=plan.header_text)

        for node in plan.nodes:
            # 每个评论节点按原始 segments 顺序渲染
            segments = self._node_segments(node, image_paths)
            forward.add_mixed_node(segments=segments, sender_name=node.sender_name)

        # 尾部节点：issue 链接
        forward.add_node(type="text", sender_name="Gitea", msg=plan.url_text)
        return forward

    @staticmethod
    def _node_segments(
        node: ContentNode, image_paths: dict[str, str | None]
    ) -> list[dict[str, Any]]:
        """单个评论节点的内容段：按 segments 原始顺序生成，下载失败的图片替换为文本占位。"""
        result: list[dict[str, Any]] = []
        for seg in node.segments:
            if isinstance(seg, TextSegment):
                # 纯文本：直接透传
                result.append({"type": "text", "data": {"text": seg.text}})
            elif isinstance(seg, ImageSegment):
                # 图片：用本地 file:// 路径发送；下载失败则用文本占位兜底
                path = image_paths.get(seg.url)
                if path is None:
                    result.append({"type": "text", "data": {"text": "[图片下载失败]"}})
                else:
                    result.append({"type": "image", "data": {"file": f"file://{path}"}})
            elif isinstance(seg, FileSegment):
                # 非图片附件：纯文本展示（文件名 + 大小 + 链接）
                result.append(
                    {
                        "type": "text",
                        "data": {
                            "text": (
                                f"附件: {seg.name} ({format_size(seg.size)}) {seg.download_url}"
                            )
                        },
                    }
                )
            else:
                Log.warning(f"未知内容段类型：{type(seg)} : {str(seg)}")
        return result

    async def _send_issue_comment_notification(
        self, data: GiteaIssueCommentEvent, event_type: str
    ) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="gitea_img_"))
        try:
            # 1. 构建混合消息 文本 + 图片 + 附件
            segments = _parse_comment_segments(
                data.comment.body or "", data.comment.assets, data.repository.html_url
            )
            images = _extract_images(segments)
            path_map = await self._download_images(images, temp_dir) if images else {}

            event_name = event_type or "issue_comment"
            target = "pull request" if data.is_pull else "issue"
            msg: list[dict] = [
                {
                    "type": "text",
                    "data": {
                        "text": f"[Gitea] {event_name} on {target} #{data.issue.number} {data.action} in {data.repository.full_name}\n{data.issue.title}"
                    },
                },
            ]
            msg.extend(
                self._node_segments(ContentNode(sender_name="", segments=segments), path_map)
            )
            msg.append({"type": "text", "data": {"text": f"\nurl: {data.comment.html_url}"}})
            await self.api.asyncService.send_group_msg(group_id=self.response_group, message=msg)

            # 2. 拉取历史评论并发送合并转发
            comments = await self._fetch_issue_comments(
                data.repository.full_name, data.issue.number
            )
            plan = self.formatter.issue_comment_forward(data, comments)

            # 收集合并转发计划中所有图片 URL，并发下载
            plan_images: list[ImageSegment] = [
                seg for node in plan.nodes for seg in node.segments if isinstance(seg, ImageSegment)
            ]
            if plan_images:
                plan_path_map: dict[str, str | None] = await self._download_images(
                    plan_images, temp_dir
                )
            else:
                plan_path_map = {}

            forward: Forward = self._build_forward_from_plan(plan, plan_path_map)
            await self.api.asyncService.send_group_forward_msg(
                group_id=self.response_group, forward_message=forward.message
            )
        finally:
            # 确保临时目录被清理，防止磁盘泄漏
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def _send_issues_notification(self, data: GiteaIssuesEvent, event_type: str) -> None:
        message = self.formatter.issues_summary(data, event_type)
        if not message:
            Log.warning(f"Empty Gitea webhook message for {event_type}")
            return

        await self.api.asyncService.send_group_msg(
            group_id=self.response_group,
            message=message,
        )

        forward_message = self.formatter.issues_forward(data, event_type)
        if not forward_message:
            Log.warning(f"Empty Gitea webhook forward message for {event_type}")
            return

        await self.api.asyncService.send_group_forward_msg(
            group_id=self.response_group,
            forward_message=forward_message,
        )

    async def _send_plain_text(self, data: GiteaWebhookEvent, event_type: str) -> None:
        message = self.formatter.plain_text(data, event_type)
        if not message:
            Log.warning(f"Empty Gitea webhook message for {event_type}")
            return

        await self.api.asyncService.send_group_msg(
            group_id=self.response_group,
            message=message,
        )
