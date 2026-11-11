import asyncio
import os
import sys
from importlib import import_module
from pkgutil import iter_modules

import tomlkit
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from plugins import Plugins
from utils.Database import build_database_url

from .agent.AIService import ai
from .Api import api
from .config_schema import BOT_SCHEMA, CONFIG_FILES, atomic_write, load_toml
from .EventController import Event
from .PrintLog import Log
from .Scheduler import Scheduler
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
        self.bot_config = load_toml(
            os.path.join(self.configs_path, "bot.toml")
        ).unwrap()  # bot 配置

        Log.info(f"开始加载Bot配置文件，文件路径：{os.path.join(self.configs_path, 'bot.toml')}")
        # 需要检查的关键配置项
        required_configs = {}
        for section, fields in BOT_SCHEMA.items():
            table = self.bot_config.get(section, {})
            for key, (_, required) in fields.items():
                if required:
                    required_configs[key] = table.get(key)

        # 检查哪些关键配置项是空的
        missing_configs = [key for key, value in required_configs.items() if value is None]
        if missing_configs:
            raise ValueError(f"参数不全，以下配置项未成功加载：{', '.join(missing_configs)}")

        # 将配置值分配给实例变量
        self.server_address: str = required_configs["server_address"]
        self.client_address: str = required_configs["client_address"]
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
        self.gitea_api_url: str = required_configs["api_url"]
        self.gitea_api_token: str = required_configs["api_token"]
        Log.info("成功加载配置文件")
        Log.info("加载的bot初始化配置信息如下：")
        for item in required_configs.items():
            Log.info(str(item))

        api.set_server_address(self.server_address)
        ai.set_configs(
            os.path.join(self.configs_path, "ai.toml"),
            os.path.join(os.path.dirname(__file__), "../utils/persona.j2"),
            os.path.join(os.path.dirname(__file__), "agent/ToolDef.py"),
        )  # ai 辅助工具对象

    def initialize(self) -> None:
        try:
            api.botSelfInfo.get_login()
        except Exception as e:
            raise ConnectionError(f"无法连接到Bot服务端，请确认监听端配置：{e}") from None
        self.bot_id: int = api.botSelfInfo.get_login_info().get("data", {}).get("user_id")
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

        assistants: list = api.groupService.get_group_member_list(
            group_id=self.assistant_group
        ).get("data")
        for member in assistants:
            self.assistant_list.add(member["user_id"])

    def init_plugins(self) -> None:
        Log.info("开始加载插件")

        # 读取统一的插件配置文件
        plugins_config = load_toml(os.path.join(self.configs_path, "plugins.toml")).unwrap()

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

        groups_config = load_toml(os.path.join(self.configs_path, "groups.toml"))

        for gid in group_ids:
            if not gid.isdigit():
                Log.error(f"无效的群号：{gid}")
                return False
        for gid in group_ids:
            if gid not in groups_config:
                groups_config[gid] = tomlkit.table()
            groups_config[gid][plugin_name] = True if enable else False
        atomic_write(os.path.join(self.configs_path, "groups.toml"), tomlkit.dumps(groups_config))

        return self.reload_plugin(plugin_name)

    def reload_plugin(self, name: str) -> bool:
        """
        热重载指定插件
        """
        Log.info(f"开始插件{name}的热重载")

        plugins_config = load_toml(os.path.join(self.configs_path, "plugins.toml")).unwrap()
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
        plugin_instance: Plugins = PluginClass(self)
        # 传递插件配置
        plugin_instance.config = plugin_config
        return plugin_instance

    async def run(self) -> None:
        event = Event(self.plugins_list, self.debug)
        event_ip, event_port = self.client_address.split(":")
        Log.info(f"启动监听服务 {self.client_address}")
        event_server = asyncio.create_task(event.run(event_ip, int(event_port)))

        webhook_handler = None
        scheduler = Scheduler(self.configs_path)
        scheduler_started = scheduler.register_tasks()
        if self.enable_webhook_handler:
            webhook_handler = WebhookHandler(
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
            await api.aclose()
            if webhook_handler is not None:
                await webhook_handler.stop()
            if scheduler_started:
                await scheduler.stop()


def check_config_files(configs_path: str) -> None:
    """
    检查配置文件目录下每个以 .template 结尾的文件是否有对应的正式配置文件
    """
    if not os.path.isdir(configs_path):
        raise NotADirectoryError(f"配置文件目录无效：{configs_path}")

    missing_files = [
        file for file in CONFIG_FILES if not os.path.isfile(os.path.join(configs_path, file))
    ]

    if missing_files:
        raise FileNotFoundError(f"以下配置文件缺失：\n{'\n'.join(missing_files)}")
