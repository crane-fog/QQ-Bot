import re

import uvicorn
from fastapi import FastAPI, Request

from src.Api import Api

from .Models import GiteaIssueCommentEvent, GiteaIssueLabelEvent, GiteaIssuesEvent, GiteaPushEvent

app = FastAPI(title="Webhook Handler")


@app.post("/api/tjhlp")
async def receive_post(request: Request):
    handler: WebhookHandler = app.state.handler
    payload = await request.json()
    event_type = request.headers.get("X-Gogs-Event-Type", "")
    match event_type:
        case "push":
            await handler.resolve_push(GiteaPushEvent.model_validate(payload))
        case "issues":
            await handler.resolve_issues(GiteaIssuesEvent.model_validate(payload))
        case "issue_comment":
            await handler.resolve_issue_comment(GiteaIssueCommentEvent.model_validate(payload))
        case "issue_label":
            await handler.resolve_issue_label(GiteaIssueLabelEvent.model_validate(payload))
        case _:
            print(f"Unsupported X-Gogs-Event-Type: {event_type}")
            return {"ok": False, "message": f"Unsupported X-Gogs-Event-Type: {event_type}"}

    return {"ok": True}


def replace_markdown_images(text: str, replacement_list: list[str]) -> str:
    pattern = r"!\[.*?\]\(.*?\)"

    replacements = iter(replacement_list)

    def replacer(match):
        try:
            return next(replacements)
        except StopIteration:
            return match.group(0)

    result = re.sub(pattern, replacer, text)
    return result


class WebhookHandler:
    def __init__(self, api: Api, response_group: int):
        self.api: Api = api
        self.response_group: int = response_group
        self.server = None
        app.state.handler = self

    async def resolve_push(self, data: GiteaPushEvent) -> None:
        print("Received push event")

    async def resolve_issues(self, data: GiteaIssuesEvent) -> None:
        print("Received issues event")
        image_urls: list[str] = []
        for pic in data.issue.assets:
            image_urls.append(pic.browser_download_url)

        content = replace_markdown_images(data.issue.body, image_urls)

        self.api.groupService.send_group_msg(
            group_id=self.response_group,
            message=f"issue #{data.number} {data.action} in {data.repository.name}\n{data.issue.title}\n{content}\nurl: {data.issue.html_url}",
        )

    async def resolve_issue_comment(self, data: GiteaIssueCommentEvent) -> None:
        print("Received issue_comment event")

    async def resolve_issue_label(self, data: GiteaIssueLabelEvent) -> None:
        print("Received issue_label event")

    async def run(self, ip, port) -> None:
        config = uvicorn.Config(app=app, host=ip, port=port, log_level="warning", access_log=False)
        self.server = uvicorn.Server(config)
        await self.server.serve()

    async def stop(self) -> None:
        if self.server is not None:
            self.server.should_exit = True
