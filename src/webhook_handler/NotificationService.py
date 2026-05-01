from src.Api import Api
from src.gitea.GiteaEventFormatter import GiteaEventFormatter
from src.gitea.Models import GiteaIssuesEvent, GiteaWebhookEvent
from src.PrintLog import Log


class NotificationService:
    def __init__(self, api: Api, response_group: int):
        self.api = api
        self.response_group = response_group
        self.formatter = GiteaEventFormatter()

    def send(self, data: GiteaWebhookEvent, event_type: str) -> None:
        try:
            if isinstance(data, GiteaIssuesEvent) and event_type == "issues":
                self._send_issues_notification(data, event_type)
            else:
                self._send_plain_text(data, event_type)
        except Exception as e:
            Log.error(f"发送 Gitea webhook 通知失败：event_type={event_type}, error={e}")

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
            Log.warning(f"Empty Gitea webhook message for {event_type}")
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
