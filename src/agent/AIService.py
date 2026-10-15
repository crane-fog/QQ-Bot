import json
from dataclasses import dataclass
from typing import Any

import tomlkit
from openai import AsyncOpenAI
from openai._types import NotGiven, Omit, not_given, omit
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolUnionParam

from src.agent.ToolDef import tool_defs
from src.Api import api
from src.Metrics import LLM_DURATION, LLM_SUCCESS_COUNT, LLM_TOKEN_COUNT, LLM_TOOL_USAGE_COUNT
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
    max_turns: int
    insert_persona: bool


class AIService:
    """Loads OpenAI-compatible AI profiles and sends chat completion requests."""

    def __init__(self):
        self._client = AsyncOpenAI(api_key="placeholder")

    def set_configs(self, config_path: str, persona_path: str, tool_def_path: str):
        with open(config_path, encoding="utf-8") as f:
            self._config = tomlkit.load(f)
        with open(persona_path, encoding="utf-8") as f:
            self.persona = f.read()
        with open(tool_def_path, encoding="utf-8") as f:
            self.tool_map = {
                tool_def["declaration"]["function"]["name"]: tool_def for tool_def in tool_defs
            }

    async def generate(
        self,
        profile_name: str,
        messages: list[ChatCompletionMessageParam],
        *,
        caller_is_owner: bool = False,
        group_id: int | None = None,
    ) -> str:
        """Generate one text completion using a configured profile."""
        profile = self._get_profile(profile_name)

        if profile.insert_persona:
            messages.insert(0, {"role": "system", "content": self.persona})

        client = self._client.with_options(
            api_key=profile.provider.api_key,
            base_url=profile.provider.base_url,
            timeout=profile.provider.timeout_seconds,
        )
        try:
            for turn in range(profile.max_turns):
                with LLM_DURATION.labels(
                    profile_name=profile.name,
                    provider=profile.provider.name,
                    model=profile.model,
                ).time():
                    response = await client.chat.completions.create(
                        model=profile.model,
                        messages=messages,
                        response_format=profile.response_format,
                        reasoning_effort=profile.reasoning_effort,
                        tools=profile.tools,
                        extra_body=profile.extra_body,
                    )
                messages.append(response.choices[0].message)
                Log.info(f"轮{turn + 1}：{response}")
                LLM_TOKEN_COUNT.labels(
                    profile_name=profile.name,
                    token_type="prompt",
                    provider=profile.provider.name,
                    model=profile.model,
                ).inc(response.usage.prompt_tokens)
                LLM_TOKEN_COUNT.labels(
                    profile_name=profile.name,
                    token_type="cached_prompt",
                    provider=profile.provider.name,
                    model=profile.model,
                ).inc(response.usage.prompt_tokens_details.cached_tokens)
                LLM_TOKEN_COUNT.labels(
                    profile_name=profile.name,
                    token_type="completion",
                    provider=profile.provider.name,
                    model=profile.model,
                ).inc(response.usage.completion_tokens)
                LLM_TOKEN_COUNT.labels(
                    profile_name=profile.name,
                    token_type="reasoning_completion",
                    provider=profile.provider.name,
                    model=profile.model,
                ).inc(response.usage.completion_tokens_details.reasoning_tokens)

                tool_calls = response.choices[0].message.tool_calls
                if not tool_calls:
                    LLM_SUCCESS_COUNT.labels(
                        type="success",
                        provider=profile.provider.name,
                        model=profile.model,
                    ).inc()
                    return response.choices[0].message.content or "[NO REPLY]"

                if group_id is None:
                    Log.warning("多轮对话调用工具时应提供 group_id")
                elif response.choices[0].message.content:
                    api.groupService.send_group_msg(
                        group_id=group_id,
                        message=response.choices[0].message.content,
                    )
                for tool_call in tool_calls:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": await self._call_tool(
                                tool_call.function.name,
                                profile,
                                turn,
                                caller_is_owner,
                                **json.loads(tool_call.function.arguments),
                            ),
                        }
                    )
            LLM_SUCCESS_COUNT.labels(
                type="turns_exceeded",
                provider=profile.provider.name,
                model=profile.model,
            ).inc()
            Log.warning(
                f"AI profile '{profile_name}' exceeded max_turns={profile.max_turns} without a final answer"
            )
            return "[NO REPLY]"

        except Exception as exc:
            LLM_SUCCESS_COUNT.labels(
                type="fail",
                provider=profile.provider.name,
                model=profile.model,
            ).inc()
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
            max_turns=profile_dict.get("max_turns", 5),
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
            if tool_name not in self.tool_map:
                raise AIConfigurationError(f"AI tool '{tool_name}' not found")
            tools.append(self.tool_map[tool_name]["declaration"])
        return tools

    async def _call_tool(
        self, tool_name: str, profile: AIProfile, turn: int, caller_is_owner: bool, **kwargs
    ) -> Any:
        if tool_name not in self.tool_map:
            LLM_TOOL_USAGE_COUNT.labels(
                tool_name="Error",
                provider=profile.provider.name,
                model=profile.model,
            ).inc()
            Log.warning(f"轮{turn + 1}尝试调用的工具 {tool_name} 不存在")
            return f"工具 {tool_name} 不存在"

        LLM_TOOL_USAGE_COUNT.labels(
            tool_name=tool_name,
            provider=profile.provider.name,
            model=profile.model,
        ).inc()
        Log.info(f"轮{turn + 1}调用工具：{tool_name}")
        match self.tool_map[tool_name]["type"]:
            case "default":
                result = str(self.tool_map[tool_name]["func"](**kwargs))
            case "async":
                result = str(await self.tool_map[tool_name]["func"](**kwargs))
            case "image":
                result = self.tool_map[tool_name]["func"](**kwargs)
            case "travily":
                result = str(
                    await self.tool_map[tool_name]["func"](
                        base_url=self._config["provider"]["tavily"]["base_url"],
                        api_key=self._config["provider"]["tavily"]["api_key"],
                        **kwargs,
                    )
                )
            case "restricted":
                result = str(
                    self.tool_map[tool_name]["func"](caller_is_owner=caller_is_owner, **kwargs)
                )
        Log.info(f"轮{turn + 1}工具调用结果：{result}")
        return result

    def _required_option(self, data: dict, option: str, section_name: str) -> str:
        value = data.get(option, "").strip()
        if not value:
            raise AIConfigurationError(f"AI configuration '{section_name}' requires '{option}'")
        return value


ai: AIService = AIService()
