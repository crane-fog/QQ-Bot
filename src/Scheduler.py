import ast
import configparser
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.PrintLog import Log


class Scheduler:
    def __init__(self, api, configs_path: str):
        self.api = api
        self.configs_path = configs_path
        self._scheduler = AsyncIOScheduler()

    @staticmethod
    def _parse_list(raw: str) -> list:
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, list):
                return parsed
        except (ValueError, SyntaxError):
            pass
        return []

    def register_tasks(self) -> None:
        config = self._load_config()

        for section in config.sections():
            if not config.getboolean(section, "enabled", fallback=False):
                Log.info(f"定时任务 [{section}] 未启用，跳过")
                continue

            interval = config.getint(section, "interval", fallback=60)

            if section == "BanEmojiPost":
                from src.scheduled_tasks.BanEmojiPost import BanEmojiPostTask

                task = BanEmojiPostTask(self.api, config[section])
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

    def _load_config(self) -> configparser.ConfigParser:
        config = configparser.ConfigParser()
        config_path = os.path.join(self.configs_path, "scheduler.ini")
        if not os.path.isfile(config_path):
            Log.warning("scheduler.ini 不存在，跳过定时任务加载")
            return config
        config.read(config_path, encoding="utf-8")
        return config

    async def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
