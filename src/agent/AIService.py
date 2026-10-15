import json
from dataclasses import dataclass

import httpx
import tomlkit
from openai import AsyncOpenAI
from openai._types import NotGiven, Omit, not_given, omit
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolUnionParam

import src.agent.Tools as Tool
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
        self.funcs = {
            "send_private_msg": api.privateService.send_private_msg,
            "get_group_member_list": api.groupService.get_group_member_list,
            "get_group_member_info": api.groupService.get_group_member_info,
            "set_group_ban": api.groupService.set_group_ban,
            "set_group_kick": api.groupService.set_group_kick,
            "delete_msg": api.groupService.delete_msg,
            "get_group_info": api.groupService.get_group_info,
            "set_msg_emoji_like": api.groupService.set_msg_emoji_like,
            "send_group_poke": api.groupService.send_group_poke,
            "get_msg": api.messageService.get_msg,
            "shell": Tool.restricted_shell,
            "set_notification": Tool.set_notification,
        }
        self.async_funcs = {
            "send_group_msg": api.asyncGroupService.send_group_msg,
            "travily_search": self.travily_search,
            "travily_extract": self.travily_extract,
        }
        self.not_text_funcs = {
            "read_img_file": Tool.read_img_file,
        }

    def set_configs(self, config_path: str, persona_path: str, tools_decl_path: str):
        with open(config_path, encoding="utf-8") as f:
            self._config = tomlkit.load(f)
        with open(persona_path, encoding="utf-8") as f:
            self.persona = f.read()
        with open(tools_decl_path, encoding="utf-8") as f:
            self._tools = tomlkit.load(f)

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
                    if (
                        tool_call.function.name in self.funcs
                        or tool_call.function.name in self.async_funcs
                        or tool_call.function.name in self.not_text_funcs
                    ):
                        LLM_TOOL_USAGE_COUNT.labels(
                            tool_name=tool_call.function.name,
                            provider=profile.provider.name,
                            model=profile.model,
                        ).inc()
                        Log.info(f"轮{turn + 1}调用工具：{tool_call.function.name}")
                        args = json.loads(tool_call.function.arguments)

                        if tool_call.function.name == "shell":
                            args["caller_is_owner"] = caller_is_owner

                        if tool_call.function.name in self.funcs:
                            result = str(self.funcs[tool_call.function.name](**args))
                        elif tool_call.function.name in self.async_funcs:
                            result = str(await self.async_funcs[tool_call.function.name](**args))
                        else:
                            result = self.not_text_funcs[tool_call.function.name](**args)
                        Log.info(f"轮{turn + 1}工具调用结果：{result}")
                    else:
                        LLM_TOOL_USAGE_COUNT.labels(
                            tool_name="Error",
                            provider=profile.provider.name,
                            model=profile.model,
                        ).inc()
                        Log.warning(f"轮{turn + 1}尝试调用的工具 {tool_call.function.name} 不存在")
                        result = f"工具 {tool_call.function.name} 不存在"
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result,
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
            if tool_name not in self._tools["tool"]:
                raise AIConfigurationError(f"AI tool '{tool_name}' not found")
            tools.append({"type": "function", "function": self._tools["tool"][tool_name]})
        return tools

    def _required_option(self, data: dict, option: str, section_name: str) -> str:
        value = data.get(option, "").strip()
        if not value:
            raise AIConfigurationError(f"AI configuration '{section_name}' requires '{option}'")
        return value

    async def travily_search(
        self,
        query: str,
        chunks_per_source: int = 3,
        max_results: int = 5,
        topic: str = "general",
        exact_match: bool = False,
    ) -> str:
        url = self._config["provider"]["tavily"]["search"]["url"]
        api_key = self._config["provider"]["tavily"]["api_key"]
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
        self, urls: str, query: str | None = None, chunks_per_source: int = 3
    ) -> str:
        url = self._config["provider"]["tavily"]["extract"]["url"]
        api_key = self._config["provider"]["tavily"]["api_key"]
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


ai: AIService = AIService()
