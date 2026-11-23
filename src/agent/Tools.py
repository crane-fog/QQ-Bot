import asyncio
import os
import subprocess

import httpx

from src.Api import api
from utils.AIUtils import encode_image

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


def read_img_file(path: str | None = None, url: str | None = None) -> list[dict]:
    if url is not None:
        return [{"type": "image_url", "image_url": {"url": url}}]
    if path is None:
        return [{"type": "text", "text": "Either path or url must be provided."}]
    parts = os.path.normpath(path).split(os.sep)
    if parts[-4:-1] != ["llbot", "data", "temp"]:
        return [{"type": "text", "text": f"File path not allowed: {path}"}]
    if not os.path.isfile(path):
        return [{"type": "text", "text": f"File not found: {path}"}]
    if not path.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
        return [{"type": "text", "text": f"Unsupported file type: {path}"}]
    return [{"type": "image_url", "image_url": {"url": encode_image(path, 1024)}}]


async def travily_search(
    base_url: str,
    api_key: str,
    query: str,
    chunks_per_source: int = 3,
    max_results: int = 5,
    topic: str = "general",
    exact_match: bool = False,
) -> str:
    url = base_url + "/search"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    payload = {
        "query": query,
        "search_depth": "advanced",
        "chunks_per_source": chunks_per_source,
        "max_results": max_results,
        "topic": topic,
        "exact_match": exact_match,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            return response.text
        else:
            return f"Travily API Error: {response.status_code} - {response.text}"


async def travily_extract(
    base_url: str, api_key: str, urls: str, query: str | None = None, chunks_per_source: int = 3
) -> str:
    url = base_url + "/extract"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    payload = {
        "urls": urls,
        "query": query,
        "extract_depth": "advanced",
        "chunks_per_source": chunks_per_source,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            return response.text
        else:
            return f"Travily API Error: {response.status_code} - {response.text}"
