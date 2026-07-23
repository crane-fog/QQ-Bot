import os
from importlib import import_module
from pkgutil import iter_modules
from unittest.mock import patch

import pytest
import tomlkit

from src.Bot import Bot

base_path = os.path.dirname(os.path.abspath(__file__))
configs_path = os.path.join(base_path, "configs")
plugins_path = os.path.join(base_path, "plugins")
plugins_config_path = os.path.join(configs_path, "plugins.toml")
plugins_template_config_path = os.path.join(configs_path, "plugins.toml.template")
groups_config_path = os.path.join(configs_path, "groups.toml")


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return tomlkit.load(f).unwrap()


def get_plugin_names():
    return [name for _, name, ispkg in iter_modules([plugins_path]) if ispkg]


@pytest.fixture
def bot():
    with patch("src.Bot.Api"):
        bot = Bot(configs_path=configs_path, plugins_path=plugins_path)
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
        """所有插件包都应在 plugins.toml.template 中声明 section"""
        template_config = load_config(plugins_template_config_path)

        plugin_packages = [name for _, name, ispkg in iter_modules([plugins_path]) if ispkg]
        missing_sections = [name for name in plugin_packages if name not in template_config]

        assert plugin_packages, "未找到任何插件包"
        assert not missing_sections, (
            f"以下插件未在 plugins.toml.template 中声明: {missing_sections}"
        )

    @pytest.mark.parametrize("plugin_name", get_plugin_names())
    def test_plugin_importable(self, bot, plugin_name):
        """所有插件包（含未启用）应能被正常导入和实例化"""

        plugins_config = load_config(plugins_config_path)

        plugin_module = import_module(f".{plugin_name}", "plugins")
        PluginClass = getattr(plugin_module, plugin_name)
        plugin_instance = PluginClass(bot.server_address, bot)
        if plugin_name in plugins_config:
            plugin_instance.config = plugins_config[plugin_name]

        assert plugin_instance is not None
