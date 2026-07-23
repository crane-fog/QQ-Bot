from collections.abc import Iterable
from dataclasses import dataclass

import tomlkit
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam


class AIConfigurationError(ValueError):
    """Raised when AI provider or profile configuration is invalid."""


class AIProviderError(RuntimeError):
    """Raised when an AI provider request fails."""


@dataclass(frozen=True)
class AIProvider:
    name: str
    base_url: str
    api_key: str
    timeout_seconds: float
    max_retries: int


@dataclass(frozen=True)
class AIProfile:
    name: str
    provider: AIProvider
    model: str


class AIService:
    """Loads OpenAI-compatible AI profiles and sends chat completion requests."""

    _SUPPORTED_PROTOCOL = "openai_chat_completions"

    def __init__(self, config_path: str):
        with open(config_path, encoding="utf-8") as f:
            self._config = tomlkit.load(f)

    def get_profile(self, profile_name: str) -> AIProfile:
        if profile_name not in self._config["profile"]:
            raise AIConfigurationError(f"AI profile '{profile_name}' not found")

        profile_dict = self._config["profile"][profile_name]

        return AIProfile(
            name=profile_name,
            provider=self._get_provider(
                self._required_option(profile_dict, "provider", profile_name)
            ),
            model=self._required_option(profile_dict, "model", profile_name),
        )

    async def generate(
        self, profile_name: str, messages: Iterable[ChatCompletionMessageParam]
    ) -> str:
        """Generate one text completion using a configured profile."""
        profile = self.get_profile(profile_name)
        client = AsyncOpenAI(
            api_key=profile.provider.api_key,
            base_url=profile.provider.base_url,
            timeout=profile.provider.timeout_seconds,
            max_retries=profile.provider.max_retries,
        )
        try:
            response = await client.chat.completions.create(
                model=profile.model,
                messages=messages,
            )
        except Exception as exc:
            raise AIProviderError(f"AI profile '{profile_name}' request failed: {exc}") from exc

        if not response.choices:
            return "[NO REPLY]"
        return response.choices[0].message.content or "[NO REPLY]"

    def _get_provider(self, provider_name: str) -> AIProvider:
        if provider_name not in self._config["provider"]:
            raise AIConfigurationError(f"AI provider '{provider_name}' not found")

        provider_dict = self._config["provider"][provider_name]
        protocol = self._required_option(provider_dict, "protocol", provider_name)

        if protocol != self._SUPPORTED_PROTOCOL:
            raise AIConfigurationError(
                f"AI provider '{provider_name}' has unsupported protocol '{protocol}'"
            )

        return AIProvider(
            name=provider_name,
            base_url=self._required_option(provider_dict, "base_url", provider_name),
            api_key=self._required_option(provider_dict, "api_key", provider_name),
            timeout_seconds=provider_dict.get("timeout_seconds", 45.0),
            max_retries=provider_dict.get("max_retries", 1),
        )

    @staticmethod
    def _required_option(data: dict, option: str, section_name: str) -> str:
        value = data.get(option, "").strip()
        if not value:
            raise AIConfigurationError(f"AI configuration '{section_name}' requires '{option}'")
        return value
