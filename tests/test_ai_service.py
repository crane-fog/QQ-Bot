from types import SimpleNamespace
from unittest.mock import patch

import pytest
from openai.types.chat import ChatCompletionMessageParam

from src.agent.AIService import AIConfigurationError, AIService
from src.Bot import check_config_files


def _make_service(api_key: str = "test-secret") -> AIService:
    service = AIService()
    service.set_configs("configs/ai.toml.template", "utils/persona.j2", "src/agent/ToolDef.py")
    provider_name = service._config["profile"]["default"]["provider"]
    service._config["provider"][provider_name]["api_key"] = api_key
    return service


class _FakeCompletions:
    def __init__(self, captured: dict):
        self.captured = captured

    async def create(self, **kwargs):
        self.captured["request"] = kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="configured reply", tool_calls=None)
                )
            ]
        )


class _FakeAsyncOpenAI:
    def __init__(self, captured: dict, **kwargs):
        captured.update(kwargs)
        self.chat = SimpleNamespace(completions=_FakeCompletions(captured))


def test_generate_rejects_unknown_profile():
    service = _make_service()

    with pytest.raises(AIConfigurationError, match="unknown"):
        service._get_profile("unknown")


@pytest.mark.asyncio
async def test_generate_rejects_missing_api_key():
    service = _make_service(api_key="")

    messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": "hello"}]

    with pytest.raises(AIConfigurationError, match="api_key"):
        await service.generate("default", messages)


def test_check_config_files_passes_when_all_configs_exist():
    with (
        patch("src.Bot.os.path.isdir", return_value=True),
        patch("src.Bot.os.path.isfile", return_value=True),
    ):
        check_config_files("configs")


def test_check_config_files_raises_when_configs_missing():
    with (
        patch("src.Bot.os.path.isdir", return_value=True),
        patch("src.Bot.os.path.isfile", return_value=False),
    ):
        with pytest.raises(FileNotFoundError) as exc_info:
            check_config_files("configs")

    message = str(exc_info.value)
    for filename in ("ai.toml", "bot.toml", "groups.toml", "plugins.toml", "scheduler.toml"):
        assert filename in message


def test_check_config_files_reports_only_missing_configs():
    def fake_isfile(path):
        return path.endswith("bot.toml")

    with (
        patch("src.Bot.os.path.isdir", return_value=True),
        patch("src.Bot.os.path.isfile", side_effect=fake_isfile),
    ):
        with pytest.raises(FileNotFoundError) as exc_info:
            check_config_files("configs")

    message = str(exc_info.value)
    assert "bot.toml" not in message
    for filename in ("ai.toml", "groups.toml", "plugins.toml", "scheduler.toml"):
        assert filename in message


def test_check_config_files_rejects_invalid_directory():
    with patch("src.Bot.os.path.isdir", return_value=False):
        with pytest.raises(NotADirectoryError, match="配置文件目录无效"):
            check_config_files("configs")
