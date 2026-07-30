import os

import tomlkit
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.PrintLog import Log


class Scheduler:
    def __init__(self, api, configs_path: str):
        self.api = api
        self.configs_path = configs_path
        self._scheduler = AsyncIOScheduler()

    def register_tasks(self) -> None:
        config = self._load_config()

        for section, section_config in config.items():
            enabled = section_config.get("enabled", False)
            if not enabled:
                Log.info(f"定时任务 [{section}] 未启用，跳过")
                continue

            interval = section_config.get("interval", 60)

            if section == "BanEmojiPost":
                from src.scheduled_tasks.BanEmojiPost import BanEmojiPostTask

                task = BanEmojiPostTask(self.api, section_config)
                self._scheduler.add_job(
                    task.run,
                    IntervalTrigger(seconds=interval),
                    id=section,
                    name=section,
                )
                Log.info(f"已注册定时任务：[{section}]，间隔 {interval}s")

        if self._scheduler.get_jobs():
            self._scheduler.start()
            Log.info("定时任务调度器已启动")

    def _load_config(self) -> dict:
        config_path = os.path.join(self.configs_path, "scheduler.toml")
        if not os.path.isfile(config_path):
            Log.warning("scheduler.toml 不存在，跳过定时任务加载")
            return {}
        with open(config_path, encoding="utf-8") as f:
            return tomlkit.load(f).unwrap()

    async def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
