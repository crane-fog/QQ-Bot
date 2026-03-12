import asyncio
import traceback

import uvicorn
from fastapi import FastAPI, Request

from plugins import Plugins

from .event_handler.GroupMessageEventHandler import GroupMessageEvent
from .event_handler.NoticeEventHandler import GroupPokeEvent, GroupRecallEvent
from .event_handler.PrivateMessageEventHandler import PrivateMessageEvent
from .event_handler.RequestEventHandler import GroupRequestEvent
from .event_handler.SendEventHandler import SendEvent
from .PrintLog import Log


def create_event_app(event_controller: "Event"):
    app = FastAPI(title="Event Controller")

    @app.api_route("/onebot", methods=["POST", "GET"])
    async def post_data(request: Request):
        data = await request.json()
        post_type = data.get("post_type")

        if post_type == "message":
            message_type = data.get("message_type")
            if message_type == "private":
                event = PrivateMessageEvent(data)
                event.post_event(event_controller.debug)
                event_controller.schedule_task(event_controller.run_private_plugins(event))
            elif message_type == "group":
                event = GroupMessageEvent(data)
                event.post_event(event_controller.debug)
                event_controller.schedule_task(event_controller.run_group_plugins(event))
        elif post_type == "notice":
            notice_type = data.get("notice_type")
            if notice_type == "group_recall":
                event = GroupRecallEvent(data)
                event.post_event(event_controller.debug)
                event_controller.schedule_task(event_controller.run_group_recall(event))
            elif notice_type == "notify":
                sub_type = data.get("sub_type")
                if sub_type == "poke":
                    event = GroupPokeEvent(data)
                    event.poke_event(event_controller.debug)
                    event_controller.schedule_task(event_controller.run_group_poke(event))
        elif post_type == "request":
            request_type = data.get("request_type")
            if request_type == "group":
                event = GroupRequestEvent(data)
                event.post_event(event_controller.debug)
                event_controller.schedule_task(event_controller.run_group_request(event))
        elif post_type == "message_sent":
            event = SendEvent(data)
            event.post_event(event_controller.debug)
            event_controller.schedule_task(event_controller.run_send_event(event))

        return {}, 200

    return app


class Event:
    def __init__(self, plugins_list: list[Plugins], debug: bool):
        self.debug = debug
        self.plugins_list = plugins_list
        self.tasks: set[asyncio.Task] = set()
        self.server = None

    def schedule_task(self, coro):
        task = asyncio.create_task(coro)
        self.tasks.add(task)

        def on_done(done_task: asyncio.Task):
            self.tasks.discard(done_task)
            try:
                done_task.result()
            except Exception as e:
                Log.error(f"事件任务执行失败：{e}")

        task.add_done_callback(on_done)

    async def run(self, ip, port):
        app = create_event_app(self)
        config = uvicorn.Config(app=app, host=ip, port=port, log_level="warning", access_log=False)
        self.server = uvicorn.Server(config)
        await self.server.serve()

    async def stop(self):
        if self.server is not None:
            self.server.should_exit = True

        tasks = list(self.tasks)
        if tasks:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def run_plugins_by_types(self, event, allowed_types: set[str]):
        for plugin in self.plugins_list:
            plugin_type = plugin.type
            if plugin_type in allowed_types:
                try:
                    plugin.load_effected_groups()
                    await plugin.main(event, self.debug)
                except Exception as e:
                    traceback_info = traceback.format_exc()
                    error_info = f"插件：{plugin.name}运行时出错：{e}，请联系该插件的作者：{plugin.author}\n详细信息：\n{traceback_info}"
                    plugin.set_status("error", error_info)
                    Log.error(error_info)

    async def run_private_plugins(self, event):
        await self.run_plugins_by_types(event, {"Private"})

    async def run_group_plugins(self, event):
        await self.run_plugins_by_types(event, {"Group", "GroupRecall", "Record"})

    async def run_group_recall(self, event):
        await self.run_plugins_by_types(event, {"GroupRecall"})

    async def run_group_request(self, event):
        await self.run_plugins_by_types(event, {"GroupRequest"})

    async def run_group_poke(self, event):
        await self.run_plugins_by_types(event, {"Poke"})

    async def run_send_event(self, event):
        await self.run_plugins_by_types(event, {"Send", "Record"})
