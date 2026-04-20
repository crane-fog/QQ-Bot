import json

import uvicorn
from fastapi import FastAPI, Request

from ..Api import Api
from .Models import GiteaIssueCommentEvent, GiteaIssueLabelEvent, GiteaIssuesEvent, GiteaPushEvent

app = FastAPI(title="Webhook Handler")


async def resolve_push(data: GiteaPushEvent) -> None:
    print("Received push event:")
    print(json.dumps(data.model_dump(), indent=2, ensure_ascii=False, default=str))


async def resolve_issues(data: GiteaIssuesEvent) -> None:
    print("Received issues event:")
    print(json.dumps(data.model_dump(), indent=2, ensure_ascii=False, default=str))


async def resolve_issue_comment(data: GiteaIssueCommentEvent) -> None:
    print("Received issue_comment event:")
    print(json.dumps(data.model_dump(), indent=2, ensure_ascii=False, default=str))


async def resolve_issue_label(data: GiteaIssueLabelEvent) -> None:
    print("Received issue_label event:")
    print(json.dumps(data.model_dump(), indent=2, ensure_ascii=False, default=str))


@app.post("/api/tjhlp")
async def receive_post(request: Request):
    payload = await request.json()
    event_type = request.headers.get("X-Gogs-Event-Type", "")
    match event_type:
        case "push":
            await resolve_push(GiteaPushEvent.model_validate(payload))
        case "issues":
            await resolve_issues(GiteaIssuesEvent.model_validate(payload))
        case "issue_comment":
            await resolve_issue_comment(GiteaIssueCommentEvent.model_validate(payload))
        case "issue_label":
            await resolve_issue_label(GiteaIssueLabelEvent.model_validate(payload))
        case _:
            print(f"Unsupported X-Gogs-Event-Type: {event_type}")
            return {"ok": False, "message": f"Unsupported X-Gogs-Event-Type: {event_type}"}

    return {"ok": True}


class WebhookHandler:
    def __init__(self, api: Api):
        self.api: Api = api
        self.server = None

    async def run(self, ip, port) -> None:
        config = uvicorn.Config(app=app, host=ip, port=port, log_level="warning", access_log=False)
        self.server = uvicorn.Server(config)
        await self.server.serve()

    async def stop(self) -> None:
        if self.server is not None:
            self.server.should_exit = True
