import os
from typing import TYPE_CHECKING

import tomlkit
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.PrintLog import Log

if TYPE_CHECKING:
    from src.Bot import Bot


class Scheduler:
    def __init__(self, configs_path: str, bot: "Bot"):
        self.configs_path = configs_path
        self._scheduler = AsyncIOScheduler()
        self.bot = bot

    def register_tasks(self) -> bool:
        config = self._load_config()

        for section, section_config in config.items():
            enabled = section_config.get("enable", False)
            if not enabled:
                Log.info(f"定时任务 [{section}] 未启用，跳过")
                continue

            kwargs = section_config.get("kwargs", {})
            module_name = f"scheduled_tasks.{section}"
            try:
                module = __import__(module_name, fromlist=["main"])
                module.main(self._scheduler, self.bot, **kwargs)
                Log.info(f"已注册定时任务：[{section}]")
            except Exception as e:
                Log.error(f"加载定时任务 [{section}] 时出错: {e}")

        if self._scheduler.get_jobs():
            self._scheduler.start()
            Log.info("定时任务调度器已启动")
            return True
        else:
            Log.info("没有启用的定时任务，调度器未启动")
            return False

    def _load_config(self) -> dict:
        config_path = os.path.join(self.configs_path, "scheduler.toml")
        if not os.path.isfile(config_path):
            Log.warning("scheduler.toml 不存在，跳过定时任务加载")
            return {}
        with open(config_path, encoding="utf-8") as f:
            return tomlkit.load(f).unwrap()

    async def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
