import asyncio
import subprocess

from src.Api import api

_background_tasks = set()


def restricted_shell(cmd: str, caller_is_owner: bool) -> str:
    if not caller_is_owner:
        return "The caller is not authorized to execute this command."
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    output = (
        f"return code: {result.returncode}\n"
        + (f"stdout:\n{result.stdout}\n" if result.stdout else "stdout: (None)\n")
        + (f"stderr:\n{result.stderr}\n" if result.stderr else "stderr: (None)\n")
    )
    return output


# TODO: 复用已有的 Scheduler，并为 Scheduler 添加持久化；在持久化的前提下要以一定形式来告诉 agent 这个任务的存在性，并提供删除任务的工具
def set_notification(wait_time: int, msg: str, group_id: int) -> str:
    async def notify(msg: str, group_id: int) -> None:
        await asyncio.sleep(wait_time)
        await api.asyncGroupService.send_group_msg(group_id=group_id, message=msg)

    task = asyncio.create_task(notify(msg, group_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return f'Success. Notification msg "{msg}" set for {wait_time} seconds from now.'
