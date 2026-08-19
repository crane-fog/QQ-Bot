from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.Api import api


async def task(group_id: int, message: str):
    api.groupService.send_group_msg(group_id=group_id, message=message)


# 每个文件里的 main 函数会被执行，参数从 scheduler.toml 中读取
def main(scheduler: AsyncIOScheduler, group_id: int, message: str):
    scheduler.add_job(task, "interval", minutes=1, args=[group_id, message])
