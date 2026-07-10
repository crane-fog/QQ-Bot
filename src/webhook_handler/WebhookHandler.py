import uvicorn
from fastapi import FastAPI, Request
from pydantic import ValidationError

from src.Api import Api
from src.gitea.Models import GiteaPushEvent, GiteaWebhookEvent
from src.PrintLog import Log
from src.webhook_handler.EventConfig import EVENT_CONFIG, EventConfig
from src.webhook_handler.NotificationService import NotificationService

app = FastAPI(title="Webhook Handler")


@app.post("/api/tjhlp")
async def receive_post(request: Request):
    handler: WebhookHandler | None = getattr(app.state, "handler", None)
    if not isinstance(handler, WebhookHandler):
        Log.error("WebhookHandler 未初始化")
        return {"ok": False, "message": "WebhookHandler 未初始化"}

    payload = await request.json()
    event_type = request.headers.get("X-Gitea-Event-Type") or request.headers.get(
        "X-Gogs-Event-Type", ""
    )

    try:
        event = parse_gitea_event(event_type, payload)
        config = EVENT_CONFIG[event_type]
    except (ValueError, ValidationError) as e:
        Log.warning(f"Gitea webhook {event_type} 解析失败: {e}")
        return {"ok": False, "message": str(e)}

    await handler.resolve(event, event_type, config)
    return {"ok": True}


def log_recoverable_payload_anomalies(data: GiteaWebhookEvent, event_type: str) -> None:
    if isinstance(data, GiteaPushEvent):
        if data.total_commits > 0 and data.head_commit is None and not data.commits:
            Log.warning(
                "Gitea push payload 缺少提交详情："
                f"event_type={event_type}, repo={data.repository.full_name}, "
                f"ref={data.ref}, total_commits={data.total_commits}, after={data.after}"
            )


def parse_gitea_event(event_type: str, payload: dict) -> GiteaWebhookEvent:
    """将 webhook 原始 payload 解析为对应的事件模型。"""
    config = EVENT_CONFIG.get(event_type)
    if config is None:
        raise ValueError(f"Unsupported Gitea webhook event type: {event_type}")
    return config.model.model_validate(payload)


class WebhookHandler:
    def __init__(self, api: Api, response_group: int, gitea_api_url: str, gitea_api_token: str):
        self.api: Api = api
        self.response_group: int = response_group
        self.notification_service = NotificationService(
            api, response_group, gitea_api_url, gitea_api_token
        )
        self.server = None
        app.state.handler = self

    async def resolve(self, data: GiteaWebhookEvent, event_type: str, config: EventConfig) -> None:
        log_recoverable_payload_anomalies(data, event_type)
        await self.notification_service.send(data, event_type, config)

    async def run(self, ip, port) -> None:
        config = uvicorn.Config(app=app, host=ip, port=port, log_level="warning", access_log=False)
        self.server = uvicorn.Server(config)
        await self.server.serve()

    async def stop(self) -> None:
        if self.server is not None:
            self.server.should_exit = True
