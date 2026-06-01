import base64
import json
import os
from typing import Literal

from openai import AsyncOpenAI

from src.Api import Api

tool_def: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "set_group_ban",
            "strict": False,
            "description": "Ban a user in a group, the user will not be able to send messages in the group for a certain period of time. You can unset the ban by use duration 0. You should prudently use this tool.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "The user ID of the person to ban.",
                    },
                    "group_id": {
                        "type": "integer",
                        "description": "The group ID where the ban will be applied.",
                    },
                    "duration": {
                        "type": "integer",
                        "description": "The duration of the ban in seconds. Must be in the range of 0 to 2592000.",
                    },
                },
                "required": ["user_id", "group_id", "duration"],
                "additionalProperties": False,
            },
        },
    }
]

# 角色设定原作者：zaqa_07352@Discord
with open(os.path.join(os.path.dirname(__file__), "persona.j2"), encoding="utf-8") as f:
    persona = f.read()


async def get_llm_response(
    messages: list[dict],
    *,
    model: Literal["gemini-3-flash-preview", "deepseek-v4-pro", "deepseek-v4-flash"] = None,
    temperature: float = 1.0,
    response_format: dict = None,
    reasoning_effort: Literal["low", "medium", "high", "xhigh", "max"] = "xhigh",
    thinking_enabled: bool = True,
    use_tools: bool = False,
    api: Api = None,
    insert_persona: bool = False,
) -> str:
    if model == "gemini-3-flash-preview":
        client = AsyncOpenAI(api_key=os.environ["MNAPI_KEY"], base_url="https://api.mnapi.com/v1")
    elif model == "deepseek-v4-pro" or model == "deepseek-v4-flash":
        client = AsyncOpenAI(api_key=os.environ["DPSK_KEY"], base_url="https://api.deepseek.com")
    else:
        raise ValueError("Unsupported model")

    if insert_persona:
        messages.insert(0, {"role": "system", "content": persona})

    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        response_format=response_format,
        reasoning_effort=reasoning_effort,
        tools=tool_def if use_tools else None,
        extra_body={"thinking": {"type": "enabled" if thinking_enabled else "disabled"}},
    )
    if response.choices:
        tools_used = response.choices[0].message.tool_calls if use_tools else None
        if tools_used:
            messages.append(response.choices[0].message)
            for tool_call in tools_used:
                if tool_call.function.name == "set_group_ban":
                    print(f"{tool_call.function}")
                    args = json.loads(tool_call.function.arguments)
                    user_id = args["user_id"]
                    group_id = args["group_id"]
                    duration = args["duration"]
                    result = api.groupService.set_group_ban(
                        group_id=group_id, user_id=user_id, duration=duration
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": f"{result}",
                        }
                    )
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                response_format=response_format,
                reasoning_effort=reasoning_effort,
                extra_body={"thinking": {"type": "enabled" if thinking_enabled else "disabled"}},
            )
        return response.choices[0].message.content
    else:
        return "[NO REPLY]"


def encode_image(image_path: str) -> str:
    extension = os.path.splitext(image_path)[1].lower().replace(".", "")
    if extension in ["png", "webp", "gif"]:
        mime_type = f"image/{extension}"
    else:
        mime_type = "image/jpeg"
    with open(image_path, "rb") as f:
        return f"data:{mime_type};base64,{base64.b64encode(f.read()).decode('utf-8')}"
