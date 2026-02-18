import os

from openai import OpenAI

DPSK_KEY = os.environ["DPSK_KEY"]
DMXAPI_KEY = os.environ["DMXAPI_KEY"]
DPSK_BASE_URL = "https://api.deepseek.com"
DMXAPI_BASE_URL = "https://www.dmxapi.cn/v1"


def get_dpsk_response(
    messages: list[dict],
    model: str = "deepseek-chat",
    temperature: float = 1.0,
    response_format: dict = None,
) -> str:
    client = OpenAI(api_key=DPSK_KEY, base_url=DPSK_BASE_URL)

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        response_format=response_format,
    )
    if response.choices:
        return response.choices[0].message.content
    else:
        return "[NO REPLY]"


def get_gemini_response(
    messages: list[dict],
    model: str = "gemini-3-flash-preview",
    temperature: float = 1.0,
    response_format: dict = None,
) -> str:
    client = OpenAI(api_key=DMXAPI_KEY, base_url=DMXAPI_BASE_URL)

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        response_format=response_format,
    )
    if response.choices:
        return response.choices[0].message.content
    else:
        return "[NO REPLY]"
