import base64
import json
import os
from dataclasses import dataclass

import tomlkit
from openai import AsyncOpenAI
from openai._types import NotGiven, Omit, not_given, omit
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolUnionParam

from src.Api import Api
from src.PrintLog import Log


class AIConfigurationError(ValueError):
    """Raised when AI provider or profile configuration is invalid."""


class AIProviderError(RuntimeError):
    """Raised when an AI provider request fails."""


@dataclass(frozen=True)
class AIProvider:
    name: str
    base_url: str
    api_key: str
    timeout_seconds: float | NotGiven


@dataclass(frozen=True)
class AIProfile:
    name: str
    provider: AIProvider
    model: str
    response_format: dict | Omit
    reasoning_effort: str | Omit
    extra_body: dict | None
    tools: list[ChatCompletionToolUnionParam] | Omit
    insert_persona: bool


class AIService:
    """Loads OpenAI-compatible AI profiles and sends chat completion requests."""

    def __init__(self, config_path: str, persona_path: str, api: Api):
        with open(config_path, encoding="utf-8") as f:
            self._config = tomlkit.load(f)
        with open(persona_path, encoding="utf-8") as f:
            self.persona = f.read()
        self.api = api

    async def generate(self, profile_name: str, messages: list[ChatCompletionMessageParam]) -> str:
        """Generate one text completion using a configured profile."""
        profile = self._get_profile(profile_name)

        if profile.insert_persona:
            messages.insert(0, {"role": "system", "content": self.persona})

        client = AsyncOpenAI(
            api_key=profile.provider.api_key,
            base_url=profile.provider.base_url,
            timeout=profile.provider.timeout_seconds,
        )
        try:
            response = await client.chat.completions.create(
                model=profile.model,
                messages=messages,
                response_format=profile.response_format,
                reasoning_effort=profile.reasoning_effort,
                tools=profile.tools,
                extra_body=profile.extra_body,
            )
            if response.choices:
                # 以下内容待重做
                Log.info(response)
                tools_used = response.choices[0].message.tool_calls
                if tools_used:
                    messages.append(response.choices[0].message)
                    for tool_call in tools_used:
                        if tool_call.function.name == "set_group_ban":
                            Log.info(f"{tool_call.function}")
                            args = json.loads(tool_call.function.arguments)
                            user_id = args["user_id"]
                            group_id = args["group_id"]
                            duration = args["duration"]
                            result = self.api.groupService.set_group_ban(
                                group_id=group_id, user_id=user_id, duration=duration
                            )
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "content": f"{result}",
                                }
                            )
                    if (
                        response.choices[0].message.content is None
                        or response.choices[0].message.content.strip() == ""
                    ):
                        response = await client.chat.completions.create(
                            model=profile.model,
                            messages=messages,
                            response_format=profile.response_format,
                            reasoning_effort=profile.reasoning_effort,
                            extra_body=profile.extra_body,
                        )
                        Log.info(response)
                    # 以上内容待重做
                return response.choices[0].message.content or "[NO REPLY]"
            else:
                return "[NO REPLY]"
        except Exception as exc:
            raise AIProviderError(f"AI profile '{profile_name}' request failed: {exc}") from exc

    def _get_profile(self, profile_name: str) -> AIProfile:
        if profile_name not in self._config["profile"]:
            raise AIConfigurationError(f"AI profile '{profile_name}' not found")

        profile_dict = self._config["profile"][profile_name]

        return AIProfile(
            name=profile_name,
            provider=self._get_provider(
                self._required_option(profile_dict, "provider", profile_name)
            ),
            model=self._required_option(profile_dict, "model", profile_name),
            response_format=profile_dict.get("response_format", omit),
            reasoning_effort=profile_dict.get("reasoning_effort", omit),
            extra_body=profile_dict.get("extra_body", None),
            tools=self._get_tool(profile_dict.get("tools", [])),
            insert_persona=profile_dict.get("insert_persona", False),
        )

    def _get_provider(self, provider_name: str) -> AIProvider:
        if provider_name not in self._config["provider"]:
            raise AIConfigurationError(f"AI provider '{provider_name}' not found")

        provider_dict = self._config["provider"][provider_name]

        return AIProvider(
            name=provider_name,
            base_url=self._required_option(provider_dict, "base_url", provider_name),
            api_key=self._required_option(provider_dict, "api_key", provider_name),
            timeout_seconds=provider_dict.get("timeout_seconds", not_given),
        )

    def _get_tool(self, tool_names: list[str]) -> list[ChatCompletionToolUnionParam] | Omit:
        if not tool_names:
            return omit

        tools: list[ChatCompletionToolUnionParam] = []
        for tool_name in tool_names:
            if "tool" not in self._config or tool_name not in self._config["tool"]:
                raise AIConfigurationError(f"AI tool '{tool_name}' not found")
            tools.append({"type": "function", "function": self._config["tool"][tool_name]})
        return tools

    @staticmethod
    def _required_option(data: dict, option: str, section_name: str) -> str:
        value = data.get(option, "").strip()
        if not value:
            raise AIConfigurationError(f"AI configuration '{section_name}' requires '{option}'")
        return value

    @staticmethod
    def encode_image(image_path: str) -> str:
        extension = os.path.splitext(image_path)[1].lower().replace(".", "")
        if extension in ["png", "webp", "gif"]:
            mime_type = f"image/{extension}"
        else:
            mime_type = "image/jpeg"
        with open(image_path, "rb") as f:
            return f"data:{mime_type};base64,{base64.b64encode(f.read()).decode('utf-8')}"
