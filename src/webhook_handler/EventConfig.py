from dataclasses import dataclass

from src.gitea.Models import (
    GiteaIssueCommentEvent,
    GiteaIssuesEvent,
    GiteaPushEvent,
    GiteaWebhookEvent,
)


@dataclass(frozen=True)
class EventConfig:
    model: type[GiteaWebhookEvent]
    forward: bool = False  # 是否额外发送合并转发消息


EVENT_CONFIG: dict[str, EventConfig] = {
    "push": EventConfig(GiteaPushEvent),
    "issues": EventConfig(GiteaIssuesEvent, forward=True),
    "issue_assign": EventConfig(GiteaIssuesEvent),
    "issue_label": EventConfig(GiteaIssuesEvent),
    "issue_milestone": EventConfig(GiteaIssuesEvent),
    "issue_comment": EventConfig(GiteaIssueCommentEvent, forward=True),
}
