from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import pytest

from plugins.AI.AI import AI
from src.AIService import AIConfigurationError, AIProviderError
from src.Api import Api
from src.Bot import Bot
from src.event_handler.GroupMessageEventHandler import GroupMessageEvent


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_message"),
    [
        (AIConfigurationError("profile is invalid"), "AI 服务配置有误，请联系管理员。"),
        (AIProviderError("provider request failed"), "AI 服务暂时不可用，请稍后再试。"),
    ],
)
async def test_ai_plugin_returns_friendly_message_for_ai_service_errors(error, expected_message):
    group_service = SimpleNamespace(send_group_msg=Mock())
    plugin = object.__new__(AI)
    plugin.name = "AI"
    # The handler only needs these attributes; avoid constructing real Bot/Api objects in this unit test.
    plugin.bot = cast(
        Bot,
        cast(
            object,
            SimpleNamespace(
                bot_name="monika",
                ai=SimpleNamespace(generate=AsyncMock(side_effect=error)),
            ),
        ),
    )
    plugin.api = cast(Api, cast(object, SimpleNamespace(groupService=group_service)))
    plugin.config = {"ai_profile": "default"}
    plugin.user_cooldown = {}
    plugin.cooldown_time = 1

    event = cast(
        GroupMessageEvent,
        cast(
            object,
            SimpleNamespace(
                message="monika ask hello",
                user_id=10001,
                group_id=20001,
                message_id=30001,
            ),
        ),
    )

    await cast(Any, AI.main).__wrapped__(plugin, event, debug=False)

    assert group_service.send_group_msg.call_count == 2
    fallback_message = group_service.send_group_msg.call_args_list[-1].kwargs["message"]
    assert expected_message in fallback_message
    assert str(error) not in fallback_message
