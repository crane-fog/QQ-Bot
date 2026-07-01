from dataclasses import dataclass

import uvicorn
from fastapi import FastAPI, Request
from pydantic import ValidationError

from src.Api import Api
from src.gitea.Models import (
    GiteaIssueCommentEvent,
    GiteaIssuesEvent,
    GiteaPushEvent,
    GiteaWebhookEvent,
)
from src.PrintLog import Log
from src.webhook_handler.NotificationService import NotificationService

app = FastAPI(title="Webhook Handler")


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
    "issue_comment": EventConfig(GiteaIssueCommentEvent),
}


@app.post("/api/tjhlp")
async def receive_post(request: Request):
    handler: WebhookHandler | None = app.state.handler
    if not isinstance(handler, WebhookHandler):
        Log.error("WebhookHandler 未初始化")
        return {"ok": False, "message": "WebhookHandler 未初始化"}

    payload = await request.json()
    event_type = request.headers.get("X-Gitea-Event-Type") or request.headers.get(
        "X-Gogs-Event-Type", ""
    )

    config = EVENT_CONFIG.get(event_type)
    if config is None:
        Log.warning(f"Unsupported Gitea webhook event type: {event_type}")
        return {"ok": False, "message": f"Unsupported Gitea webhook event type: {event_type}"}

    try:
        event = config.model.model_validate(payload)
    except ValidationError as e:
        Log.warning(f"Invalid Gitea webhook payload for {event_type}: {e}")
        return {"ok": False, "message": f"Invalid Gitea webhook payload for {event_type}"}

    handler.resolve(event, event_type, config)
    return {"ok": True}


def log_recoverable_payload_anomalies(data: GiteaWebhookEvent, event_type: str) -> None:
    if isinstance(data, GiteaPushEvent):
        if data.total_commits > 0 and data.head_commit is None and not data.commits:
            Log.warning(
                "Gitea push payload 缺少提交详情："
                f"event_type={event_type}, repo={data.repository.full_name}, "
                f"ref={data.ref}, total_commits={data.total_commits}, after={data.after}"
            )


class WebhookHandler:
    def __init__(self, api: Api, response_group: int):
        self.api: Api = api
        self.response_group: int = response_group
        self.notification_service = NotificationService(api, response_group)
        self.server = None
        app.state.handler = self

    def resolve(self, data: GiteaWebhookEvent, event_type: str, config: EventConfig) -> None:
        log_recoverable_payload_anomalies(data, event_type)
        self.notification_service.send(data, event_type, config)

    async def run(self, ip, port) -> None:
        config = uvicorn.Config(app=app, host=ip, port=port, log_level="warning", access_log=False)
        self.server = uvicorn.Server(config)
        await self.server.serve()

    async def stop(self) -> None:
        if self.server is not None:
            self.server.should_exit = True
