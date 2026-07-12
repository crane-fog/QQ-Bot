import configparser
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

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
    temperature: float


class AIService:
    """Loads OpenAI-compatible AI profiles and sends chat completion requests."""

    _PROVIDER_PREFIX = "provider:"
    _PROFILE_PREFIX = "profile:"
    _SUPPORTED_PROTOCOL = "openai_chat_completions"

    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path)
        self._config = configparser.ConfigParser()
        if not self._config.read(self.config_path, encoding="utf-8"):
            raise AIConfigurationError(f"AI configuration file not found: {self.config_path}")

    def get_profile(self, profile_name: str) -> AIProfile:
        section_name = f"{self._PROFILE_PREFIX}{profile_name}"
        if not self._config.has_section(section_name):
            raise AIConfigurationError(f"AI profile '{profile_name}' not found")

        profile_section = self._config[section_name]
        provider_name = self._required_option(profile_section, "provider", section_name)
        provider = self._get_provider(provider_name)
        model = self._required_option(profile_section, "model", section_name)
        temperature = self._get_float(profile_section, "temperature", section_name, default=1.0)

        return AIProfile(
            name=profile_name,
            provider=provider,
            model=model,
            temperature=temperature,
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
                temperature=profile.temperature,
            )
        except Exception as exc:
            raise AIProviderError(f"AI profile '{profile_name}' request failed: {exc}") from exc

        if not response.choices:
            return "[NO REPLY]"
        return response.choices[0].message.content or "[NO REPLY]"

    def _get_provider(self, provider_name: str) -> AIProvider:
        section_name = f"{self._PROVIDER_PREFIX}{provider_name}"
        if not self._config.has_section(section_name):
            raise AIConfigurationError(f"AI provider '{provider_name}' not found")

        provider_section = self._config[section_name]
        protocol = self._required_option(provider_section, "protocol", section_name)
        if protocol != self._SUPPORTED_PROTOCOL:
            raise AIConfigurationError(
                f"AI provider '{provider_name}' has unsupported protocol '{protocol}'"
            )

        return AIProvider(
            name=provider_name,
            base_url=self._required_option(provider_section, "base_url", section_name),
            api_key=self._required_option(provider_section, "api_key", section_name),
            timeout_seconds=self._get_float(
                provider_section, "timeout_seconds", section_name, default=45.0
            ),
            max_retries=self._get_int(provider_section, "max_retries", section_name, default=1),
        )

    @staticmethod
    def _required_option(section: configparser.SectionProxy, option: str, section_name: str) -> str:
        value = section.get(option, fallback="").strip()
        if not value:
            raise AIConfigurationError(f"AI configuration '{section_name}' requires '{option}'")
        return value

    @staticmethod
    def _get_float(
        section: configparser.SectionProxy, option: str, section_name: str, default: float
    ) -> float:
        try:
            return section.getfloat(option, fallback=default)
        except ValueError as exc:
            raise AIConfigurationError(
                f"AI configuration '{section_name}.{option}' must be a number"
            ) from exc

    @staticmethod
    def _get_int(
        section: configparser.SectionProxy, option: str, section_name: str, default: int
    ) -> int:
        try:
            return section.getint(option, fallback=default)
        except ValueError as exc:
            raise AIConfigurationError(
                f"AI configuration '{section_name}.{option}' must be an integer"
            ) from exc
