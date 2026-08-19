import asyncio
import os
import sys
from importlib import import_module
from pkgutil import iter_modules
from shutil import copyfile

import tomlkit
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from plugins import Plugins
from utils.Database import build_database_url

from .AIService import AIService
from .Api import Api
from .EventController import Event
from .PrintLog import Log
from .webhook_handler.WebhookHandler import WebhookHandler


class Bot:
    def __init__(self, configs_path: str, plugins_path: str):
        """
        初始化bot对象
        :param configs_path: 配置文件目录的路径
        :param plugins_path: 插件文件目录的路径
        """
        Log.start_logging()

        # 成员变量初始化
        self.plugins_list: list[Plugins] = []  # 插件实例列表
        self.database: None | AsyncEngine = None  # 数据库连接对象
        self.assistant_list: set[int] = set()  # 助教列表
        self.configs_path: str = configs_path
        self.plugins_path: str = plugins_path

        check_config_files(self.configs_path)
        with open(os.path.join(self.configs_path, "bot.toml"), encoding="utf-8") as f:
            self.bot_config = tomlkit.load(f).unwrap()  # bot 配置

        Log.info(f"开始加载Bot配置文件，文件路径：{os.path.join(self.configs_path, 'bot.toml')}")
        # 需要检查的关键配置项
        required_configs = {
            "server_address": self.bot_config.get("Init", {}).get("server_address"),
            "client_address": self.bot_config.get("Init", {}).get("client_address"),
            "web_controller_address": self.bot_config.get("Init", {}).get("web_controller_address"),
            "bot_name": self.bot_config.get("Init", {}).get("bot_name"),
            "debug": self.bot_config.get("Init", {}).get("debug"),
            "database_enable": self.bot_config.get("Init", {}).get("database_enable"),
            "database_username": self.bot_config.get("Init", {}).get("database_username"),
            "database_address": self.bot_config.get("Init", {}).get("database_address"),
            "database_passwd": self.bot_config.get("Init", {}).get("database_passwd"),
            "database_name": self.bot_config.get("Init", {}).get("database_name"),
            "owner_id": self.bot_config.get("Init", {}).get("owner_id"),
            "assistant_group": self.bot_config.get("Init", {}).get("assistant_group"),
            "enable_webhook_handler": self.bot_config.get("Init", {}).get("enable_webhook_handler"),
            "webhook_handler_address": self.bot_config.get("Gitea", {}).get(
                "webhook_handler_address"
            ),
            "webhook_response_group": self.bot_config.get("Gitea", {}).get(
                "webhook_response_group"
            ),
            "gitea_api_url": self.bot_config.get("Gitea", {}).get("api_url"),
            "gitea_api_token": self.bot_config.get("Gitea", {}).get("api_token"),
        }

        # 检查哪些关键配置项是空的
        missing_configs = [key for key, value in required_configs.items() if value is None]
        if missing_configs:
            raise ValueError(f"参数不全，以下配置项未成功加载：{', '.join(missing_configs)}")

        # 将配置值分配给实例变量
        self.server_address: str = required_configs["server_address"]
        self.client_address: str = required_configs["client_address"]
        self.web_controller_address: str = required_configs["web_controller_address"]
        self.bot_name: str = required_configs["bot_name"]
        self.debug: bool = required_configs["debug"]
        self.database_enable: bool = required_configs["database_enable"]
        self.database_username: str = required_configs["database_username"]
        self.database_address: str = required_configs["database_address"]
        self.database_passwd: str = required_configs["database_passwd"]
        self.database_name: str = required_configs["database_name"]
        self.owner_id: int = required_configs["owner_id"]
        self.assistant_group: int = required_configs["assistant_group"]
        self.enable_webhook_handler: bool = required_configs["enable_webhook_handler"]
        self.webhook_handler_address: str = required_configs["webhook_handler_address"]
        self.webhook_response_group: int = required_configs["webhook_response_group"]
        self.gitea_api_url: str = required_configs["gitea_api_url"]
        self.gitea_api_token: str = required_configs["gitea_api_token"]
        Log.info("成功加载配置文件")
        Log.info("加载的bot初始化配置信息如下：")
        for item in required_configs.items():
            Log.info(str(item))

        self.api: Api = Api(self.server_address)  # api接口对象
        self.ai = AIService(
            os.path.join(self.configs_path, "ai.toml"),
            os.path.join(os.path.dirname(__file__), "../utils/persona.j2"),
            self.api,
        )  # ai 辅助工具对象

    def initialize(self) -> None:
        try:
            self.api.botSelfInfo.get_login()
        except Exception as e:
            raise ConnectionError(f"无法连接到Bot服务端，请确认监听端配置：{e}") from None
        self.bot_id: int = self.api.botSelfInfo.get_login_info().get("data", {}).get("user_id")
        if self.bot_id is None:
            raise ValueError("无法获取Bot登录信息")
        Log.info(f"获取到Bot的登录信息：{self.bot_id}")

        self.init_database()
        self.init_assistant_list()
        self.init_plugins()
        Log.info("Bot初始化成功！")

    def init_database(self) -> None:
        if not self.database_enable:
            Log.info("初始化配置{database_enable}项为：False，将不尝试连接数据库")
            self.database: None | AsyncEngine = None
            return
        Log.info("开始创建与数据库之间的连接")
        try:
            self.database: AsyncEngine = create_async_engine(
                build_database_url(
                    self.database_username,
                    self.database_passwd,
                    self.database_address,
                    self.database_name,
                )
            )
            Log.info("成功连接到bot数据库")
        except Exception as e:
            Log.error(f"连接到数据库时失败：{e}")
            raise e

    def init_assistant_list(self) -> None:
        if self.assistant_group == 123456789:
            Log.warning("未设置助教群ID，跳过加载助教列表")
            return

        assistants: list = self.api.groupService.get_group_member_list(
            group_id=self.assistant_group
        ).get("data")
        for member in assistants:
            self.assistant_list.add(member["user_id"])

    def init_plugins(self) -> None:
        Log.info("开始加载插件")

        # 读取统一的插件配置文件
        with open(os.path.join(self.configs_path, "plugins.toml"), encoding="utf-8") as f:
            plugins_config = tomlkit.load(f).unwrap()

        for _, name, ispkg in iter_modules([self.plugins_path]):
            if not ispkg:
                continue  # 如果不是插件包就跳过

            # 检查插件是否启用
            enable = False
            if name in plugins_config:
                enable = plugins_config[name].get("enable", False)

            if not enable:
                Log.info(f"插件 {name} 未启用，跳过加载")
                continue

            try:
                plugin_instance = self.create_plugin_instance(name, plugins_config[name])
                self.plugins_list.append(plugin_instance)
                Log.info(
                    f"成功加载插件：{plugin_instance.name}，插件类型：{plugin_instance.type}，插件作者{plugin_instance.author}"
                )
            except (ModuleNotFoundError, ImportError) as e:
                Log.warning(
                    f"插件 {name} 已启用但缺少依赖 '{getattr(e, 'name', None) or e}'，已跳过加载。"
                    f"请运行：uv sync --extra {name}"
                )
                continue
            except Exception as e:
                Log.error(f"加载插件{name}失败：{e}")
                raise e

    def modify_plugin(self, plugin_name: str, group_ids: list[str], enable: bool) -> bool:
        """
        调整指定插件在多群聊的启动状态，并热重载。

        :param plugin_name: 插件名称
        :param group_ids: 群号列表
        :param enable: 在群聊中启用还是禁用
        :return: 是否成功
        """
        for _, name, ispkg in iter_modules([self.plugins_path]):
            if name == plugin_name and ispkg:
                break
        else:
            Log.error(f"没有找到插件{plugin_name}")
            return False

        with open(os.path.join(self.configs_path, "groups.toml"), encoding="utf-8") as f:
            groups_config = tomlkit.load(f)

        for gid in group_ids:
            if not gid.isdigit():
                Log.error(f"无效的群号：{gid}")
                return False
        for gid in group_ids:
            if gid not in groups_config:
                groups_config[gid] = tomlkit.table()
            groups_config[gid][plugin_name] = True if enable else False
        with open(os.path.join(self.configs_path, "groups.toml"), "w", encoding="utf-8") as f:
            tomlkit.dump(groups_config, f)

        return self.reload_plugin(plugin_name)

    def reload_plugin(self, name: str) -> bool:
        """
        热重载指定插件
        """
        Log.info(f"开始插件{name}的热重载")

        with open(os.path.join(self.configs_path, "plugins.toml"), encoding="utf-8") as f:
            plugins_config = tomlkit.load(f).unwrap()
        if name not in plugins_config:
            Log.error(f"插件{name}的配置不存在，无法热重载")
            return False
        elif not plugins_config[name].get("enable", False):
            Log.info(f"插件{name}未启用，无法热重载")
            return False

        keys_to_remove = [
            k for k in sys.modules if k == f"plugins.{name}" or k.startswith(f"plugins.{name}.")
        ]

        old_modules = {k: sys.modules[k] for k in keys_to_remove}

        try:
            for k in keys_to_remove:
                del sys.modules[k]
            plugin_instance = self.create_plugin_instance(name, plugins_config[name])
        except Exception as e:
            keys_to_remove = [
                k for k in sys.modules if k == f"plugins.{name}" or k.startswith(f"plugins.{name}.")
            ]
            for k in keys_to_remove:
                del sys.modules[k]
            sys.modules.update(old_modules)
            Log.error(f"热重载插件{name}失败：{e}")
            return False

        self.plugins_list[:] = [p for p in self.plugins_list if p.name != name]
        self.plugins_list.append(plugin_instance)
        Log.info(
            f"成功热重载插件：{plugin_instance.name}，插件类型：{plugin_instance.type}，插件作者{plugin_instance.author}"
        )
        return True

    def create_plugin_instance(self, name: str, plugin_config: dict) -> Plugins:
        # 从plugins包动态导入子包
        plugin_module = import_module(f".{name}", "plugins")
        # 获取子包中的插件类，假设类名与模块名相同
        PluginClass = getattr(plugin_module, name)
        # 实例化插件
        plugin_instance: Plugins = PluginClass(self.server_address, self)
        # 传递插件配置
        plugin_instance.config = plugin_config
        return plugin_instance

    async def run(self) -> None:
        event = Event(self.plugins_list, self.debug)
        event_ip, event_port = self.client_address.split(":")
        Log.info(f"启动监听服务 {self.client_address}")
        event_server = asyncio.create_task(event.run(event_ip, int(event_port)))
        ## web controller 暂时弃用
        # web_controller = WebController(self)
        # web_ip, web_port = self.web_controller_address.split(":")
        # Log.info(f"启动 web controller 服务 {web_ip}:{web_port}")
        # web_server = asyncio.create_task(web_controller.run(web_ip, int(web_port)))
        # Log.info("web controller 服务启动成功！")

        webhook_handler = None
        if self.enable_webhook_handler:
            webhook_handler = WebhookHandler(
                self.api,
                self.webhook_response_group,
                self.gitea_api_url,
                self.gitea_api_token,
            )
            webhook_ip, webhook_port = self.webhook_handler_address.split(":")
            Log.info(f"启动 Webhook Handler 服务 {self.webhook_handler_address}")
            webhook_server = asyncio.create_task(webhook_handler.run(webhook_ip, int(webhook_port)))

            def _on_webhook_done(task: asyncio.Task) -> None:
                try:
                    exc = task.exception()
                except asyncio.CancelledError:
                    return
                if exc is not None:
                    Log.error(f"Webhook Handler 服务异常退出: {exc}")

            webhook_server.add_done_callback(_on_webhook_done)

        try:
            await event_server
        finally:
            await event.stop()
            if webhook_handler is not None:
                await webhook_handler.stop()


def check_config_files(configs_path: str) -> None:
    """
    如配置文件不存在，复制默认配置文件模板
    """
    if not os.path.isfile(os.path.join(configs_path, "bot.toml")):
        Log.warning("配置文件bot.toml不存在，正在复制默认配置文件模板")
        copyfile(
            os.path.join(configs_path, "bot.toml.template"),
            os.path.join(configs_path, "bot.toml"),
        )
    if not os.path.isfile(os.path.join(configs_path, "ai.toml")):
        Log.warning("配置文件ai.toml不存在，正在复制默认配置文件模板")
        copyfile(
            os.path.join(configs_path, "ai.toml.template"),
            os.path.join(configs_path, "ai.toml"),
        )
    if not os.path.isfile(os.path.join(configs_path, "groups.toml")):
        Log.warning("配置文件groups.toml不存在，正在复制默认配置文件模板")
        copyfile(
            os.path.join(configs_path, "groups.toml.template"),
            os.path.join(configs_path, "groups.toml"),
        )
    if not os.path.isfile(os.path.join(configs_path, "plugins.toml")):
        Log.warning("配置文件plugins.toml不存在，正在复制默认配置文件模板")
        copyfile(
            os.path.join(configs_path, "plugins.toml.template"),
            os.path.join(configs_path, "plugins.toml"),
        )
