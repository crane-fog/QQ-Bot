import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

from src.gitea.Models import (
    Attachment,
    Comment,
    GiteaIssueCommentEvent,
    GiteaIssuesEvent,
    GiteaPushEvent,
    GiteaWebhookEvent,
    Issue,
)
from utils.TextUtils import format_size


@dataclass
class TextSegment:
    """评论正文中的一段纯文本。"""

    text: str


@dataclass
class ImageSegment:
    """评论中的一张图片。url 已规范化为绝对 URL，不含 token。"""

    url: str
    alt: str = ""


@dataclass
class FileSegment:
    """非图片附件，仅文本展示（文件名 + 大小 + 下载直链）。"""

    name: str
    size: int
    download_url: str


type ContentSegment = TextSegment | ImageSegment | FileSegment


@dataclass
class ContentNode:
    """合并转发中单个评论节点的渲染单元，segments 保留原文中文字与图片的交替顺序。"""

    sender_name: str
    segments: list[ContentSegment] = field(default_factory=list)


@dataclass
class ForwardPlan:
    """issue_comment_forward 的产物，把"下载什么/发什么"与发送逻辑解耦。"""

    header_text: str
    nodes: list[ContentNode]
    url_text: str


# markdown 图片语法 ![alt](url) 或 ![alt](url "title")
MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def _limit_text(text: str, limit: int = 500) -> str:
    """将文本截断到指定长度（默认 500 字符），超出部分用 ... 代替。"""
    # 先去除首尾空白再判断长度
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _branch_name(ref: str) -> str:
    """去掉 ref 中的 refs/heads/ 或 refs/tags/ 前缀，返回分支名或标签名。"""
    return ref.removeprefix("refs/heads/").removeprefix("refs/tags/")


def _attachment_lines(attachments: list[Attachment]) -> list[str]:
    """将附件列表格式化为文本行，供纯文本摘要使用。"""
    if not attachments:
        return []

    lines = ["attachments:"]
    for attachment in attachments:
        lines.append(f"{attachment.name}: {attachment.browser_download_url}")
    return lines


def _resolve_image_url(url: str, repo_html_url: str, gitea_base_url: str) -> str:
    """将 Markdown 图片 URL 规范化为绝对 URL，并保留 Gitea 的站点子路径。"""
    if url.startswith(("http://", "https://")):
        return url
    if url.startswith("/"):
        return urljoin(gitea_base_url + "/", url.lstrip("/"))
    return urljoin(repo_html_url, url)


def _parse_body_segments(
    body: str, repo_html_url: str, gitea_base_url: str
) -> list[ContentSegment]:
    """把 body 按 markdown 图片切分为 TextSegment / ImageSegment 交替序列。"""
    segments: list[ContentSegment] = []
    body = body or ""

    pos = 0
    for m in MD_IMAGE_RE.finditer(body):
        before = body[pos : m.start()]
        if before:
            segments.append(TextSegment(text=before))

        alt = m.group(1).strip()
        url = _resolve_image_url(m.group(2).strip(), repo_html_url, gitea_base_url)
        segments.append(ImageSegment(url=url, alt=alt))
        pos = m.end()

    tail = body[pos:]
    if tail:
        segments.append(TextSegment(text=tail + "\n\n"))

    return segments


def _append_asset_segments(segments: list[ContentSegment], assets: list[Attachment]) -> None:
    """所有附件统一以 FileSegment 追加（图片由 body markdown 解析处理）。"""
    for asset in assets:
        if not asset.browser_download_url:
            continue
        segments.append(
            FileSegment(
                name=asset.name,
                size=asset.size,
                download_url=asset.browser_download_url,
            )
        )


def _parse_comment_segments(
    body: str,
    assets: list[Attachment],
    repo_html_url: str,
    gitea_base_url: str,
) -> list[ContentSegment]:
    """解析评论正文与附件，生成有序段落列表。"""
    segments = _parse_body_segments(body, repo_html_url, gitea_base_url)
    _append_asset_segments(segments, assets)
    return segments


def _extract_images(segments: list[ContentSegment]) -> list[ImageSegment]:
    """从 segments 中提取所有图片段，供 plain_text 路径发图使用。"""
    return [s for s in segments if isinstance(s, ImageSegment)]


def _label_text(event_or_issue: GiteaIssuesEvent | Issue) -> str:
    """提取 issue 的标签，以逗号分隔；无标签返回 "none"。"""
    issue = event_or_issue.issue if isinstance(event_or_issue, GiteaIssuesEvent) else event_or_issue
    labels = [label.name for label in issue.labels if label.name]
    return ", ".join(labels) if labels else "none"


def _issue_author(event_or_issue: GiteaIssuesEvent | Issue) -> str:
    """获取 issue 的原始作者，若原作者为空则回退到当前用户 login。"""
    issue = event_or_issue.issue if isinstance(event_or_issue, GiteaIssuesEvent) else event_or_issue
    return issue.original_author or issue.user.login


def _issue_label_change_text(event: GiteaIssuesEvent) -> str:
    """生成标签变更描述文本，前置 +/- 区分新增/移除；无变更则返回当前标签列表。"""
    if event.changes is not None:
        added = [f"+{label.name}" for label in event.changes.added_labels if label.name]
        removed = [f"-{label.name}" for label in event.changes.removed_labels if label.name]
        changes = added + removed
        if changes:
            return ", ".join(changes)

    return _label_text(event)


class GiteaEventFormatter:
    def __init__(self, gitea_base_url: str):
        self.gitea_base_url = gitea_base_url.strip().rstrip("/")
        if not self.gitea_base_url:
            raise ValueError("Gitea 基础地址不能为空")

    def plain_text(self, event: GiteaWebhookEvent, event_type: str = "") -> str:
        # case 的时候不会真正构造对象，只是判断是否匹配类型
        match event:
            case GiteaPushEvent():
                return self.push(event)
            case GiteaIssuesEvent():
                if event_type == "issue_label":
                    return self.issue_label(event, event_type)
                return self.issue_detail(event, event_type)
            case GiteaIssueCommentEvent():
                text, _ = self.issue_comment_plain(event, event_type)
                return text
            case _:
                return ""

    def push(self, event: GiteaPushEvent) -> str:
        branch = _branch_name(event.ref)
        commit_count = event.total_commits or len(event.commits)
        lines = [
            f"[Gitea] push in {event.repository.full_name}",
            f"branch: {branch}",
            f"commits: {commit_count}",
        ]

        head_commit = event.head_commit or (event.commits[-1] if event.commits else None)
        if head_commit is not None:
            message = head_commit.message.splitlines()[0] if head_commit.message else ""
            short_id = head_commit.id[:8]
            author = head_commit.author.username if head_commit.author else event.pusher.login
            lines.append(f"latest: {short_id} {message} by {author}")

        if event.compare_url:
            lines.append(f"url: {event.compare_url}")
        return "\n".join(lines)

    def issue_detail(self, event: GiteaIssuesEvent, event_type: str = "") -> str:
        body = event.issue.body or ""
        content = _limit_text(body)

        lines = [
            self.issues_summary(event, event_type),
            f"[Author]: {_issue_author(event)}",
            f"[Title]: {event.issue.title}",
        ]
        if content:
            lines.append(content)
        lines.extend(_attachment_lines(event.issue.assets))
        lines.append(f"\nurl: {event.issue.html_url}")
        return "\n".join(lines)

    def issues_summary(self, event: GiteaIssuesEvent, event_type: str = "") -> str:
        event_name = event_type or "issues"
        return (
            f"[Gitea] {event_name} #{event.number} {event.action} in {event.repository.full_name}"
        )

    def issue_label(self, event: GiteaIssuesEvent, event_type: str = "") -> str:
        return "\n".join(
            [
                self.issues_summary(event, event_type),
                f"Author: {_issue_author(event)}",
                f"Label: {_issue_label_change_text(event)}",
            ]
        )

    def issues_forward_plan(self, event: GiteaIssuesEvent, event_type: str = "") -> ForwardPlan:
        """构建 issues 事件的合并转发计划，保留正文中的图片和附件顺序。"""
        event_name = event_type or "issues"
        header_text = "\n".join(
            [
                f"[Gitea] {event_name} #{event.number} {event.action} in {event.repository.full_name}",
                f"Title: {event.issue.title}",
                f"Labels: {_label_text(event)}",
                f"Author: {_issue_author(event)}",
            ]
        )
        body_segments = _parse_comment_segments(
            event.issue.body or "(empty body)",
            event.issue.assets,
            event.repository.html_url,
            self.gitea_base_url,
        )
        return ForwardPlan(
            header_text=header_text,
            nodes=[ContentNode(sender_name="Gitea", segments=body_segments)],
            url_text=f"url: {event.issue.html_url}",
        )

    def issue_comment_plain(
        self, event: GiteaIssueCommentEvent, event_type: str = ""
    ) -> tuple[str, list[ImageSegment]]:
        """
        issue_comment 的纯文本摘要 + 待发送图片列表。
        正文保留文字与 [图片] 占位的原始顺序；图片附件一并加入图片列表。
        """
        repo_html_url = event.repository.html_url
        segments = _parse_comment_segments(
            event.comment.body or "",
            event.comment.assets,
            repo_html_url,
            self.gitea_base_url,
        )

        # 生成纯文本摘要：将 segments 转为单一文本
        text_parts: list[str] = []
        for seg in segments:
            if isinstance(seg, TextSegment):
                text_parts.append(_limit_text(seg.text))
            elif isinstance(seg, ImageSegment):
                label = f"[图片: {seg.alt}]" if seg.alt else "[图片]"
                text_parts.append(label)
            elif isinstance(seg, FileSegment):
                text_parts.append(f"附件: {seg.name} ({format_size(seg.size)}) {seg.download_url}")

        event_name = event_type or "issue_comment"
        target = "pull request" if event.is_pull else "issue"
        lines = [
            f"[Gitea] {event_name} on {target} #{event.issue.number} {event.action}"
            f" in {event.repository.full_name}",
            event.issue.title,
        ]
        if text_parts:
            lines.append(_limit_text("".join(text_parts)))
        lines.append(f"\nurl: {event.comment.html_url}")
        return "\n".join(lines), _extract_images(segments)

    def issue_comment_forward(
        self, event: GiteaIssueCommentEvent, comments: list[Comment]
    ) -> ForwardPlan:
        repo_html_url = event.repository.html_url
        target = "pull request" if event.is_pull else "issue"

        header_text = "\n".join(
            [
                f"[Gitea] issue_comment on {target} #{event.issue.number}"
                f" in {event.repository.full_name}",
                f"Title: {event.issue.title}",
                f"Author: {_issue_author(event.issue)}",
                f"Labels: {_label_text(event.issue)}",
            ]
        )

        nodes: list[ContentNode] = []

        # 节点1: issue 正文（也解析其内联图片）
        issue_segments = _parse_comment_segments(
            event.issue.body or "(empty body)", [], repo_html_url, self.gitea_base_url
        )
        nodes.append(ContentNode(sender_name="Gitea", segments=issue_segments))

        # 节点2~N: 每条评论（正序）
        for comment in comments:
            author = comment.original_author or comment.user.login
            segments = _parse_comment_segments(
                comment.body or "(empty)", comment.assets, repo_html_url, self.gitea_base_url
            )
            nodes.append(ContentNode(sender_name=author, segments=segments))

        url_text = f"url: {event.issue.html_url}"
        return ForwardPlan(header_text=header_text, nodes=nodes, url_text=url_text)
