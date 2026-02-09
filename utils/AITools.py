import os

from openai import OpenAI

API_TOKEN = os.environ["DPSK_KEY"]
BASE_URL = "https://api.deepseek.com"


def get_api_response(
    messages: list[dict],
    model: str = "deepseek-chat",
    temperature: float = 1.0,
    response_format: dict = None,
) -> str:
    client = OpenAI(api_key=API_TOKEN, base_url=BASE_URL)

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
