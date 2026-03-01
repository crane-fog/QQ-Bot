import configparser
import os
from importlib import import_module
from pkgutil import iter_modules
from unittest.mock import patch

import pytest

from plugins import Plugins
from src.Bot import Bot

base_path = os.path.dirname(os.path.abspath(__file__))
configs_path = os.path.join(base_path, "configs")
plugins_path = os.path.join(base_path, "plugins")
plugins_config_path = os.path.join(configs_path, "plugins.ini")
plugins_template_config_path = os.path.join(configs_path, "plugins.ini.template")
groups_config_path = os.path.join(configs_path, "groups.ini")

os.environ.setdefault("DMXAPI_KEY", "testkey")
os.environ.setdefault("DPSK_KEY", "testkey")


@pytest.fixture
def bot():
    with patch("src.Bot.Api"):
        bot = Bot(configs_path="configs", plugins_path=plugins_path)
    bot.database_enable = False
    return bot


class Test:
    def test_bot_created(self, bot):
        """Bot 实例正常创建"""
        assert bot is not None

    def test_config_exists(self):
        """配置文件应存在"""
        assert os.path.exists(plugins_config_path), f"插件配置文件不存在: {plugins_config_path}"
        assert os.path.exists(plugins_template_config_path), (
            f"插件模板配置文件不存在: {plugins_template_config_path}"
        )
        assert os.path.exists(groups_config_path), f"群聊配置文件不存在: {groups_config_path}"

    def test_all_plugins_have_template_section(self):
        """所有插件包都应在 plugins.ini.template 中声明 section"""
        template_config = configparser.ConfigParser()
        with open(plugins_template_config_path, encoding="utf-8") as f:
            template_config.read_file(f)

        plugin_packages = [name for _, name, ispkg in iter_modules([plugins_path]) if ispkg]
        missing_sections = [
            name for name in plugin_packages if not template_config.has_section(name)
        ]

        assert plugin_packages, "未找到任何插件包"
        assert not missing_sections, f"以下插件未在 plugins.ini.template 中声明: {missing_sections}"

    def test_all_plugins_importable(self, bot):
        """所有插件包（含未启用）应能被正常导入和实例化"""

        plugins_config = configparser.ConfigParser()
        with open(plugins_config_path, encoding="utf-8") as f:
            plugins_config.read_file(f)

        imported = []
        failed = []

        for _, name, ispkg in iter_modules([plugins_path]):
            if not ispkg:
                continue

            try:
                plugin_module = import_module(f".{name}", "plugins")
                PluginClass = getattr(plugin_module, name)
                plugin_instance: Plugins = PluginClass(bot.server_address, bot)
                if plugins_config.has_section(name):
                    plugin_instance.config = plugins_config[name]
                imported.append(name)
            except Exception as e:
                failed.append((name, str(e)))

        assert imported, "未找到任何插件包"
        assert not failed, f"以下插件导入失败: {failed}"
