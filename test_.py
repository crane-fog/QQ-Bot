import os
from importlib import import_module
from pkgutil import iter_modules
from unittest.mock import patch

import pytest

from plugins import Plugins, groups_config_path, plugins_config_path, plugins_path
from src.Bot import Bot

os.environ.setdefault("DMXAPI_KEY", "testkey")
os.environ.setdefault("DPSK_KEY", "testkey")


@pytest.fixture
def bot():
    with patch("src.Bot.Api"):
        bot = Bot(config_file="configs/bot.ini")
    bot.database_enable = False
    return bot


class Test:
    def test_bot_created(self, bot):
        """Bot 实例正常创建"""
        assert bot is not None

    def test_config_exists(self):
        """配置文件应存在"""
        assert os.path.exists(plugins_config_path), f"插件配置文件不存在: {plugins_config_path}"
        assert os.path.exists(groups_config_path), f"群聊配置文件不存在: {groups_config_path}"

    def test_all_plugins_importable(self, bot):
        """所有插件包应能被正常导入和实例化"""

        imported = []
        failed = []

        for _, name, ispkg in iter_modules([plugins_path]):
            if not ispkg:
                continue
            try:
                plugin_module = import_module(f".{name}", "plugins")
                PluginClass = getattr(plugin_module, name)
                plugin_instance: Plugins = PluginClass(bot.server_address, bot)
                plugin_instance.load_config()
                imported.append(name)
            except Exception as e:
                failed.append((name, str(e)))

        assert imported, "未找到任何插件包"
        assert not failed, f"以下插件导入失败: {failed}"
