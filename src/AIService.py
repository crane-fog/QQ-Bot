import base64
import io
import json
import os
import subprocess
from dataclasses import dataclass

import httpx
import tomlkit
from openai import AsyncOpenAI
from openai._types import NotGiven, Omit, not_given, omit
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolUnionParam
from PIL import Image

from src.Api import api
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

    def __init__(self, config_path: str, persona_path: str):
        with open(config_path, encoding="utf-8") as f:
            self._config = tomlkit.load(f)
        with open(persona_path, encoding="utf-8") as f:
            self.persona = f.read()
        self.funcs = {
            "send_private_msg": api.privateService.send_private_msg,
            "get_group_member_list": api.groupService.get_group_member_list,
            "get_group_member_info": api.groupService.get_group_member_info,
            "set_group_ban": api.groupService.set_group_ban,
            "set_group_kick": api.groupService.set_group_kick,
            "get_group_info": api.groupService.get_group_info,
            "send_group_poke": api.groupService.send_group_poke,
            "shell": self.restricted_shell,
        }
        self.async_funcs = {
            "travily_search": self.travily_search,
            "travily_extract": self.travily_extract,
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

        client = AsyncOpenAI(
            api_key=profile.provider.api_key,
            base_url=profile.provider.base_url,
            timeout=profile.provider.timeout_seconds,
        )
        try:
            for turn in range(profile.max_turns):
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
                tool_calls = response.choices[0].message.tool_calls
                if not tool_calls:
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
                    ):
                        Log.info(f"轮{turn + 1}调用工具：{tool_call.function.name}")
                        args = json.loads(tool_call.function.arguments)
                        if tool_call.function.name == "shell":
                            args["caller_is_owner"] = caller_is_owner
                        if tool_call.function.name in self.funcs:
                            result = self.funcs[tool_call.function.name](**args)
                        else:
                            result = await self.async_funcs[tool_call.function.name](**args)
                        Log.info(f"轮{turn + 1}工具调用结果：{result}")
                    else:
                        Log.warning(f"轮{turn + 1}尝试调用的工具 {tool_call.function.name} 不存在")
                        result = f"工具 {tool_call.function.name} 不存在"
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": f"{result}",
                        }
                    )
            Log.warning(
                f"AI profile '{profile_name}' exceeded max_turns={profile.max_turns} without a final answer"
            )
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
            if "tool" not in self._config or tool_name not in self._config["tool"]:
                raise AIConfigurationError(f"AI tool '{tool_name}' not found")
            tools.append({"type": "function", "function": self._config["tool"][tool_name]})
        return tools

    def restricted_shell(self, cmd: str, caller_is_owner: bool) -> str:
        if not caller_is_owner:
            return "The caller is not authorized to execute this command."
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        output = (
            f"return code: {result.returncode}\n"
            + (f"stdout:\n{result.stdout}\n" if result.stdout else "stdout: (None)\n")
            + (f"stderr:\n{result.stderr}\n" if result.stderr else "stderr: (None)\n")
        )
        return output

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
        async with httpx.AsyncClient() as client:
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
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                return response.text
            else:
                return f"Travily API Error: {response.status_code} - {response.text}"

    @staticmethod
    def _required_option(data: dict, option: str, section_name: str) -> str:
        value = data.get(option, "").strip()
        if not value:
            raise AIConfigurationError(f"AI configuration '{section_name}' requires '{option}'")
        return value

    @staticmethod
    def encode_image(image_path: str, max_kb: int | None = None, max_dimension: int = 4096) -> str:
        extension = os.path.splitext(image_path)[1].lower().replace(".", "")
        if extension in ["png", "webp", "gif"]:
            mime_type = f"image/{extension}"
        else:
            mime_type = "image/jpeg"

        image_size = os.path.getsize(image_path)
        target_bytes = int(max_kb * 1024) if (max_kb and max_kb > 0) else None

        img = Image.open(image_path)
        width, height = img.size
        need_resize = width > max_dimension or height > max_dimension

        if not need_resize and (target_bytes is None or image_size <= target_bytes):
            with open(image_path, "rb") as f:
                image_data = f.read()
            return f"data:{mime_type};base64,{base64.b64encode(image_data).decode('utf-8')}"

        if img.mode != "RGB":
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                img = bg
            else:
                img = img.convert("RGB")

        # 超过尺寸限制
        if need_resize:
            # 缩放逻辑
            scale = min(max_dimension / width, max_dimension / height)
            new_width = max(1, int(width * scale))
            new_height = max(1, int(height * scale))
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # 检查是否这时超过大小限制
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=100, optimize=True)
            if target_bytes is None or len(buf.getvalue()) <= target_bytes:
                return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"

        # 超过大小限制
        quality = 90
        scale = 1.0
        while True:
            buffer = io.BytesIO()
            if scale < 1.0:
                new_width = max(1, int(img.width * scale))
                new_height = max(1, int(img.height * scale))
                curr_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            else:
                curr_img = img

            curr_img.save(buffer, format="JPEG", quality=quality, optimize=True)
            compressed_data = buffer.getvalue()
            if len(compressed_data) <= target_bytes:
                image_data = compressed_data
                break

            if quality > 30:
                quality -= 10
            else:
                scale *= 0.8
                quality = 80

            if scale < 0.05:
                image_data = compressed_data
                break

        return f"data:image/jpeg;base64,{base64.b64encode(image_data).decode('utf-8')}"
