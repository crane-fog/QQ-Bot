import json
import os
from enum import Enum

from openai import AsyncOpenAI

from src.Api import Api

DPSK_KEY: str = os.environ["DPSK_KEY"]
DMXAPI_KEY: str = os.environ["DMXAPI_KEY"]
MNAPI_KEY: str = os.environ["MNAPI_KEY"]
DPSK_BASE_URL: str = "https://api.deepseek.com"
DMXAPI_BASE_URL: str = "https://www.dmxapi.cn/v1"
MNAPI_BASE_URL: str = "https://api.mnapi.com/v1"


class LlmModels(Enum):
    GEMINI_3_FLASH_PREVIEW = "gemini-3-flash-preview"
    DEEPSEEK_CHAT = "deepseek-chat"
    DEEPSEEK_REASONER = "deepseek-reasoner"


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


async def get_llm_response(
    messages: list[dict],
    model: LlmModels = None,
    temperature: float = 1.0,
    response_format: dict = None,
    use_tools: bool = False,
    api: Api = None,
) -> str:
    if model == LlmModels.GEMINI_3_FLASH_PREVIEW:
        client = AsyncOpenAI(api_key=MNAPI_KEY, base_url=MNAPI_BASE_URL)
    elif model == LlmModels.DEEPSEEK_CHAT or model == LlmModels.DEEPSEEK_REASONER:
        client = AsyncOpenAI(api_key=DPSK_KEY, base_url=DPSK_BASE_URL)
    else:
        raise ValueError("Unsupported model")

    response = await client.chat.completions.create(
        model=model.value,
        messages=messages,
        temperature=temperature,
        response_format=response_format,
        tools=tool_def if use_tools else None,
    )
    if response.choices:
        print(response.choices[0].message)
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
                model=model.value,
                messages=messages,
                temperature=temperature,
                response_format=response_format,
            )
        return response.choices[0].message.content
    else:
        return "[NO REPLY]"
