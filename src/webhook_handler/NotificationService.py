from httpx import AsyncClient, Timeout

from src.Api import Api
from src.gitea.GiteaEventFormatter import GiteaEventFormatter
from src.gitea.Models import Comment, GiteaIssueCommentEvent, GiteaIssuesEvent, GiteaWebhookEvent
from src.PrintLog import Log
from src.webhook_handler.WebhookHandler import EventConfig


class NotificationService:
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
                    self._send_issues_notification(data, event_type)
                else:
                    raise TypeError(
                        f"forward=True 不支持 {type(data).__name__} 类型"
                    )
            else:
                self._send_plain_text(data, event_type)
        except Exception as e:
            Log.error(f"发送 Gitea webhook 通知失败：event_type={event_type}, error={e}")

    async def _fetch_issue_comments(self, full_name: str, issue_number: int) -> list[Comment]:
        url = (
            f"{self.gitea_api_url}/api/v1/repos/{full_name}"
            f"/issues/{issue_number}/comments"
        )
        async with AsyncClient(timeout=Timeout(10)) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"token {self.gitea_api_token}"},
            )
            resp.raise_for_status()
            return [Comment.model_validate(c) for c in resp.json()]

    async def _send_issue_comment_notification(
        self, data: GiteaIssueCommentEvent, event_type: str
    ) -> None:
        # 1. 发送纯文本摘要
        plain = self.formatter.plain_text(data, event_type)
        if plain:
            self.api.groupService.send_group_msg(
                group_id=self.response_group,
                message=plain,
            )

        # 2. 拉取历史评论
        comments = await self._fetch_issue_comments(
            data.repository.full_name, data.issue.number
        )

        # 3. 发送合并转发消息
        forward_message = self.formatter.issue_comment_forward(data, comments)
        if not forward_message:
            Log.warning(f"Empty Gitea webhook forward message for {event_type}")
            return

        self.api.groupService.send_group_forward_msg(
            group_id=self.response_group,
            forward_message=forward_message,
        )

    def _send_issues_notification(self, data: GiteaIssuesEvent, event_type: str) -> None:
        message = self.formatter.issues_summary(data, event_type)
        if not message:
            Log.warning(f"Empty Gitea webhook message for {event_type}")
            return

        self.api.groupService.send_group_msg(
            group_id=self.response_group,
            message=message,
        )

        forward_message = self.formatter.issues_forward(data, event_type)
        if not forward_message:
            Log.warning(f"Empty Gitea webhook forward message for {event_type}")
            return

        self.api.groupService.send_group_forward_msg(
            group_id=self.response_group,
            forward_message=forward_message,
        )

    def _send_plain_text(self, data: GiteaWebhookEvent, event_type: str) -> None:
        message = self.formatter.plain_text(data, event_type)
        if not message:
            Log.warning(f"Empty Gitea webhook message for {event_type}")
            return

        self.api.groupService.send_group_msg(
            group_id=self.response_group,
            message=message,
        )
