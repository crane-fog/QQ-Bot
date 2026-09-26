import asyncio
import shutil
import tempfile
from collections.abc import Awaitable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from httpx import AsyncClient, Timeout
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.Api import api
from src.gitea.GiteaApi import GiteaApi
from src.gitea.GiteaEventFormatter import (
    ContentNode,
    FileSegment,
    ForwardPlan,
    GiteaEventFormatter,
    ImageSegment,
    TextSegment,
    _extract_images,
    _issue_author,
    _parse_comment_segments,
    prepend_author_block,
)
from src.gitea.Models import GiteaIssueCommentEvent, GiteaIssuesEvent, GiteaWebhookEvent
from src.Models import StuId
from src.PrintLog import Log
from src.webhook_handler.EventConfig import EventConfig
from utils.CQType import Forward
from utils.TextUtils import format_size, sanitize_filename


class NotificationService:
    response_group: int
    gitea_api_url: str
    gitea_api_token: str
    gitea: GiteaApi
    formatter: GiteaEventFormatter

    def __init__(
        self,
        response_group: int,
        gitea_api_url: str,
        gitea_api_token: str,
        database: AsyncEngine | None = None,
        dm_notify: bool = False,
        dm_notify_exclude: list[str] | None = None,
        assistant_list: set[int] | None = None,
        dm_notify_group: int | None = None,
        dm_notify_source_group: int | None = None,
        debug: bool = False,
    ):
        self.gitea = GiteaApi(gitea_api_url, gitea_api_token)
        self.response_group = response_group
        # GiteaApi 已校验非空并去除尾部 /
        self.gitea_api_url = self.gitea.api_url
        self.gitea_api_token = gitea_api_token
        self.formatter = GiteaEventFormatter(self.gitea_api_url)
        self.dm_notify = dm_notify
        self.dm_notify_exclude = list(dm_notify_exclude or [])
        # 复用 Bot 启动时从 assistant_group 加载的助教名单（运行期不刷新）
        self.assistant_list = assistant_list or set()
        # 配置了 dm_notify_group 时，私聊通知失败在该群做纯文本提醒；未配置则不做失败提醒
        self.dm_notify_group = dm_notify_group or 0
        # 私聊临时会话的来源群，缺省与 webhook 群通知同群
        self.dm_notify_source_group = dm_notify_source_group or response_group
        self.debug = debug
        # 学号→QQ 映射查询依赖数据库；未启用数据库时私聊通知整体降级为群内提示
        self.session_factory = (
            sessionmaker(bind=database, class_=AsyncSession, expire_on_commit=False)
            if database is not None
            else None
        )

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
            # 评论私聊提醒独立于群通知模式，仅对 issue_comment 的新评论触发
            if self.dm_notify and isinstance(data, GiteaIssueCommentEvent):
                await self._send_comment_dm_notifications(data)
        except Exception as e:
            Log.error(f"发送 Gitea webhook 通知失败：event_type={event_type}, error={e}")

    async def _download_images(
        self, images: list[ImageSegment], temp_dir: Path
    ) -> dict[str, str | None]:
        """
        并发下载图片到临时目录；仅向配置的 Gitea 站点发送鉴权头，单张失败映射 None。

        Args:
            images: 图片段列表
            temp_dir: 临时目录

        Returns:
            图片 URL 映射到本地路径的字典，失败时映射 None
        """
        if not images:
            return {}

        gitea_origin = urlsplit(self.gitea_api_url)
        result: dict[str, str | None] = {}

        async def _download_one(client: AsyncClient, idx: int, image: ImageSegment) -> None:
            # 用图片 alt 做文件名前缀，保证可识别
            name = sanitize_filename(image.alt) or f"{idx:02d}"
            # 强制 .png 扩展名，便于 OneBot 端识别图片类型
            path = temp_dir / f"{idx:02d}_{name}.png"
            try:
                image_origin = urlsplit(image.url)
                headers = (
                    {"Authorization": f"token {self.gitea_api_token}"}
                    if (image_origin.scheme, image_origin.netloc)
                    == (gitea_origin.scheme, gitea_origin.netloc)
                    else {}
                )
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
                data.comment.body or "",
                data.comment.assets,
                data.repository.html_url,
                self.gitea_api_url,
            )
            images = _extract_images(segments)
            path_map = await self._download_images(images, temp_dir) if images else {}

            event_name = event_type or "issue_comment"
            target = "pull request" if data.is_pull else "issue"
            msg: list[dict] = [
                {
                    "type": "text",
                    "data": {
                        "text": (
                            f"[Gitea] {event_name} on {target} #{data.issue.number}"
                            f" {data.action} in {data.repository.full_name}\n"
                            f"{data.issue.title}\n"
                        )
                    },
                },
            ]
            comment_author = data.comment.original_author or data.comment.user.login
            msg.extend(
                self._node_segments(
                    ContentNode(
                        sender_name="",
                        segments=prepend_author_block(comment_author, segments),
                    ),
                    path_map,
                )
            )
            msg.append({"type": "text", "data": {"text": f"\nurl: {data.comment.html_url}"}})
            await api.asyncGroupService.send_group_msg(group_id=self.response_group, message=msg)

            # 2. 拉取历史评论并发送合并转发
            comments = await self.gitea.list_issue_comments(
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
            await api.asyncGroupService.send_group_forward_msg(
                group_id=self.response_group, forward_message=forward.message
            )
        finally:
            # 确保临时目录被清理，防止磁盘泄漏
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def _send_issues_notification(self, data: GiteaIssuesEvent, event_type: str) -> None:
        """发送 Issue 事件通知，并渲染正文中的 Markdown 图片和附件。"""
        temp_dir = Path(tempfile.mkdtemp(prefix="gitea_img_"))
        try:
            segments = _parse_comment_segments(
                data.issue.body or "",
                data.issue.assets,
                data.repository.html_url,
                self.gitea_api_url,
            )
            images = _extract_images(segments)
            path_map = await self._download_images(images, temp_dir) if images else {}

            message: list[dict] = [
                {
                    "type": "text",
                    "data": {
                        "text": (
                            f"{self.formatter.issues_summary(data, event_type)}\n"
                            f"{data.issue.title}\n"
                        )
                    },
                }
            ]
            message.extend(
                self._node_segments(
                    ContentNode(
                        sender_name="",
                        segments=prepend_author_block(_issue_author(data), segments),
                    ),
                    path_map,
                )
            )
            message.append({"type": "text", "data": {"text": f"\nurl: {data.issue.html_url}"}})
            await api.asyncGroupService.send_group_msg(
                group_id=self.response_group,
                message=message,
            )

            plan = self.formatter.issues_forward_plan(data, event_type)
            forward: Forward = self._build_forward_from_plan(plan, path_map)
            await api.asyncGroupService.send_group_forward_msg(
                group_id=self.response_group,
                forward_message=forward.message,
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def _send_plain_text(self, data: GiteaWebhookEvent, event_type: str) -> None:
        message = self.formatter.plain_text(data, event_type)
        if not message:
            Log.warning(f"Empty Gitea webhook message for {event_type}")
            return

        await api.asyncGroupService.send_group_msg(
            group_id=self.response_group,
            message=message,
        )

    async def _send_comment_dm_notifications(self, data: GiteaIssueCommentEvent) -> None:
        """issue 新评论的临时会话提醒：私聊 issue 作者与被指派人。

        Gitea 用户名即学号，经 stu_qq_id_map 换算 QQ 号后以 dm_notify_source_group
        为临时会话来源群发送；评论者本人不发；assistant_list 助教名单与
        dm_notify_exclude 名单不发；失败名单在 dm_notify_group 纯文本提醒（未配置则不提醒）。
        """
        if data.action != "created":
            return
        commenter = data.comment.original_author or data.comment.user.login
        targets: list[str] = []
        for user in (data.issue.user, *data.issue.assignees):
            login = user.login
            if not login or login == commenter or login in self.dm_notify_exclude:
                continue
            if login not in targets:
                targets.append(login)
        if not targets:
            return

        if not targets:
            return
        Log.debug(f"issue #{data.issue.number} 私聊通知目标：{'、'.join(targets)}", self.debug)
        dm_text = f"高程答疑平台在你的 Issue 下有新评论：\n{data.comment.html_url}"

        failed: list[str] = []
        for login in targets:
            qq_id = await self._lookup_qq(login)
            if qq_id is None:
                failed.append(login)
                continue
            if int(qq_id) in self.assistant_list:
                # 助教：不私聊，也不视为失败
                Log.debug(f"助教跳过私聊：login={login}, qq={qq_id}", self.debug)
                continue
            try:
                await api.asyncPrivateService.send_private_msg(
                    int(qq_id), dm_text, group_id=self.dm_notify_source_group
                )
                Log.debug(f"私聊通知已发送：login={login}, qq={qq_id}", self.debug)
            except Exception as e:
                Log.warning(f"私聊通知发送失败：login={login}, qq={qq_id}, error={e}")
                failed.append(login)
        if not failed:
            return
        Log.warning(
            f"私聊通知存在失败：{data.repository.full_name} issue #{data.issue.number}，"
            f"未通知：{'、'.join(failed)}"
        )
        if self.dm_notify_group:
            await self._send_dm_failure_notice(data, failed)

    async def _send_dm_failure_notice(
        self, data: GiteaIssueCommentEvent, failed: list[str]
    ) -> None:
        """在 dm_notify_group 纯文本列出未能私聊通知到的学号；不 @，未配置该群则不提醒。"""
        message = (
            f"[Gitea] issue #{data.issue.number}「{data.issue.title}」有新评论，"
            f"以下用户未能私聊通知：{'、'.join(failed)}\n"
            f"{data.comment.html_url}"
        )
        await api.asyncGroupService.send_group_msg(group_id=self.dm_notify_group, message=message)

    async def _lookup_qq(self, login: str) -> str | None:
        """Gitea 用户名（学号）→ QQ 号；非数字学号、无数据库或无映射时返回 None。"""
        if self.session_factory is None or not login.isdigit():
            return None
        async with self.session_factory() as session:
            result = await session.execute(select(StuId.qq_id).where(StuId.stu_id == int(login)))
            return result.scalar_one_or_none()
