import uvicorn
from fastapi import FastAPI, Request
from pydantic import ValidationError

from src.Api import Api
from src.gitea.GiteaEventFormatter import GiteaEventFormatter
from src.gitea.Models import (
    GiteaIssueCommentEvent,
    GiteaIssuesEvent,
    GiteaPushEvent,
    GiteaWebhookEvent,
)
from src.PrintLog import Log

app = FastAPI(title="Webhook Handler")

ISSUE_EVENT_TYPES = {"issues", "issue_assign", "issue_label", "issue_milestone"}


@app.post("/api/tjhlp")
async def receive_post(request: Request):
    handler: WebhookHandler = app.state.handler
    payload = await request.json()
    event_type = request.headers.get("X-Gitea-Event-Type") or request.headers.get(
        "X-Gogs-Event-Type", ""
    )

    try:
        event = parse_gitea_event(event_type, payload)
    except ValidationError as e:
        Log.warning(f"Invalid Gitea webhook payload for {event_type}: {e}")
        return {"ok": False, "message": f"Invalid Gitea webhook payload for {event_type}"}
    except ValueError as e:
        Log.warning(str(e))
        return {"ok": False, "message": str(e)}

    handler.resolve(event, event_type)
    return {"ok": True}


def parse_gitea_event(event_type: str, payload: dict) -> GiteaWebhookEvent:
    match event_type:
        case "push":
            return GiteaPushEvent.model_validate(payload)
        case "issue_comment":
            return GiteaIssueCommentEvent.model_validate(payload)
        case event_type if event_type in ISSUE_EVENT_TYPES:
            return GiteaIssuesEvent.model_validate(payload)
        case _:
            raise ValueError(f"Unsupported Gitea webhook event type: {event_type}")


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
        self.formatter = GiteaEventFormatter()
        self.server = None
        app.state.handler = self

    def resolve(self, data: GiteaWebhookEvent, event_type: str) -> None:
        log_recoverable_payload_anomalies(data, event_type)

        message = self.formatter.plain_text(data, event_type)
        if not message:
            Log.warning(f"Empty Gitea webhook message for {event_type}")
            return

        try:
            self.api.groupService.send_group_msg(
                group_id=self.response_group,
                message=message,
            )
        except Exception as e:
            Log.error(f"发送 Gitea webhook 通知失败：event_type={event_type}, error={e}")

    async def run(self, ip, port) -> None:
        config = uvicorn.Config(app=app, host=ip, port=port, log_level="warning", access_log=False)
        self.server = uvicorn.Server(config)
        await self.server.serve()

    async def stop(self) -> None:
        if self.server is not None:
            self.server.should_exit = True
