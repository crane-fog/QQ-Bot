from src.gitea.Models import (
    Attachment,
    GiteaIssueCommentEvent,
    GiteaIssuesEvent,
    GiteaPushEvent,
    GiteaWebhookEvent,
)


def _limit_text(text: str, limit: int = 500) -> str:
    """
    限制文本长度，默认为500字符
    """
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _branch_name(ref: str) -> str:
    return ref.removeprefix("refs/heads/").removeprefix("refs/tags/")


def _attachment_lines(attachments: list[Attachment]) -> list[str]:
    if not attachments:
        return []

    lines = ["attachments:"]
    for attachment in attachments:
        lines.append(f"{attachment.name}: {attachment.browser_download_url}")
    return lines


class GiteaEventFormatter:
    def plain_text(self, event: GiteaWebhookEvent, event_type: str = "") -> str:
        # case 的时候不会真正构造对象，只是判断是否匹配类型
        match event:
            case GiteaPushEvent():
                return self.push(event)
            case GiteaIssuesEvent():
                return self.issues(event, event_type)
            case GiteaIssueCommentEvent():
                return self.issue_comment(event, event_type)
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

    def issues(self, event: GiteaIssuesEvent, event_type: str = "") -> str:
        body = event.issue.body or ""
        content = _limit_text(body)

        event_name = event_type or "issues"
        lines = [
            f"[Gitea] {event_name} #{event.number} {event.action} in {event.repository.full_name}",
            event.issue.title,
        ]
        if content:
            lines.append(content)
        lines.extend(_attachment_lines(event.issue.assets))
        lines.append(f"url: {event.issue.html_url}")
        return "\n".join(lines)

    def issue_comment(self, event: GiteaIssueCommentEvent, event_type: str = "") -> str:
        body = event.comment.body or ""
        content = _limit_text(body)

        event_name = event_type or "issue_comment"
        target = "pull request" if event.is_pull else "issue"
        lines = [
            f"[Gitea] {event_name} on {target} #{event.issue.number} {event.action} in {event.repository.full_name}",
            event.issue.title,
        ]
        if content:
            lines.append(content)
        lines.extend(_attachment_lines(event.comment.assets))
        lines.append(f"url: {event.comment.html_url}")
        return "\n".join(lines)
