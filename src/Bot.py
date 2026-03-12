import asyncio
import configparser
import logging
import os
from importlib import import_module
from pkgutil import iter_modules
from shutil import copyfile

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from plugins import Plugins
from web.WebController import WebController

from .Api import Api
from .EventController import Event
from .PrintLog import Log

# 设置 SQLAlchemy 相关的所有日志为 CRITICAL
logging.getLogger("sqlalchemy").setLevel(logging.CRITICAL)
logging.getLogger("sqlalchemy.engine").setLevel(logging.CRITICAL)
logging.getLogger("sqlalchemy.orm").setLevel(logging.CRITICAL)

log = Log()


class Bot:
    def __init__(self, configs_path: str, plugins_path: str):
        """
        初始化bot对象
        :param configs_path: 配置文件目录的路径
        :param plugins_path: 插件文件目录的路径
        """
        log.start_logging()
        # 成员变量初始化
        self.configs_path: str = configs_path
        self.plugins_path: str = plugins_path

        # 检查配置文件
        check_config_files(self.configs_path)

        # 初始化配置加载器
        self.config: configparser.ConfigParser = configparser.ConfigParser()
        with open(os.path.join(self.configs_path, "bot.ini"), encoding="utf-8") as f:
            self.config.read_file(f)

        # 初始化插件列表
        self.plugins_list: list[Plugins] = []

        # 初始化数据库连接对象
        self.database = None

        # 通过 ConfigParser 加载其他初始化参数
        log.info(f"开始加载Bot配置文件，文件路径：{os.path.join(self.configs_path, 'bot.ini')}")

        # 需要检查的关键配置项
        required_configs = {
            "server_address": self.config.get("Init", "server_address", fallback=None),
            "client_address": self.config.get("Init", "client_address", fallback=None),
            "web_controller_address": self.config.get(
                "Init", "web_controller_address", fallback=None
            ),
            "bot_name": self.config.get("Init", "bot_name", fallback=None),
            "debug": self.config.getboolean("Init", "debug", fallback=None),
            "database_enable": self.config.getboolean("Init", "database_enable", fallback=None),
            "database_username": self.config.get("Init", "database_username", fallback=None),
            "database_address": self.config.get("Init", "database_address", fallback=None),
            "database_passwd": self.config.get("Init", "database_passwd", fallback=None),
            "database_name": self.config.get("Init", "database_name", fallback=None),
            "owner_id": self.config.getint("Init", "owner_id", fallback=None),
            "assistant_group": self.config.getint("Init", "assistant_group", fallback=None),
        }

        # 检查哪些关键配置项是空的
        missing_configs = [key for key, value in required_configs.items() if value is None]
        if missing_configs:
            raise ValueError(f"参数不全，以下配置项未成功加载：{', '.join(missing_configs)}")

        # 将配置值分配给实例变量
        self.server_address = required_configs["server_address"]
        self.client_address = required_configs["client_address"]
        self.web_controller_address = required_configs["web_controller_address"]
        self.bot_name = required_configs["bot_name"]
        self.debug = required_configs["debug"]
        self.database_enable = required_configs["database_enable"]
        self.database_username = required_configs["database_username"]
        self.database_address = required_configs["database_address"]
        self.database_passwd = required_configs["database_passwd"]
        self.database_name = required_configs["database_name"]
        self.owner_id = required_configs["owner_id"]
        self.assistant_group = required_configs["assistant_group"]

        log.info("成功加载配置文件")
        log.info("加载的bot初始化配置信息如下：")
        for item in required_configs.items():
            log.info(str(item))

        # 初始化api接口对象
        self.api = Api(self.server_address)

        self.assistant_list: set[int] = set()

        try:
            self.api.botSelfInfo.get_login()
        except Exception as e:
            raise ConnectionError(f"无法连接到Bot服务端，请确认监听端配置：{e}") from None
        self.bot_id = self.api.botSelfInfo.get_login_info().get("data", {}).get("user_id", None)
        if self.bot_id is None:
            raise ValueError("无法获取Bot登录信息")
        log.info(f"获取到Bot的登录信息：{self.bot_id}")
        self.init_database()
        self.init_assistant_list()
        self.init_plugins()
        log.info("Bot初始化成功！")

    def init_database(self):
        if not self.database_enable:
            log.info("初始化配置{database_enable}项为：False，将不尝试连接数据库")
            self.database = None
            return
        log.info("开始创建与数据库之间的连接")
        try:
            self.database = create_async_engine(
                f"postgresql+asyncpg://"
                f"{self.database_username}:{self.database_passwd}@{self.database_address}/{self.database_name}",
                poolclass=NullPool,
            )
            log.info("成功连接到bot数据库")
        except Exception as e:
            log.error(f"连接到数据库时失败：{e}")
            raise e

    def init_assistant_list(self):
        if self.assistant_group == 123456789:
            log.warning("未设置助教群ID，跳过加载助教列表")
            return

        assistants = self.api.groupService.get_group_member_list(group_id=self.assistant_group).get(
            "data"
        )
        for member in assistants:
            self.assistant_list.add(member["user_id"])

    def init_plugins(self):
        log.info("开始加载插件")

        # 读取统一的插件配置文件
        plugins_config = configparser.ConfigParser()
        plugins_config_path = os.path.join(self.configs_path, "plugins.ini")
        with open(plugins_config_path, encoding="utf-8") as f:
            plugins_config.read_file(f)

        for _, name, ispkg in iter_modules([self.plugins_path]):
            if not ispkg:
                continue  # 如果不是插件包就跳过

            # 检查插件是否启用
            enable = False
            if plugins_config.has_section(name):
                if plugins_config.has_option(name, "enable"):
                    enable = plugins_config.getboolean(name, "enable")

            if not enable:
                log.info(f"插件 {name} 未启用，跳过加载")
                continue

            try:
                # 从plugins包动态导入子包
                plugin_module = import_module(f".{name}", "plugins")
                # 获取子包中的插件类，假设类名与模块名相同
                PluginClass = getattr(plugin_module, name)
                # 实例化插件
                plugin_instance: Plugins = PluginClass(self.server_address, self)
                # 传递插件配置
                plugin_instance.config = plugins_config[name]
                # 添加到插件列表
                self.plugins_list.append(plugin_instance)
                log.info(
                    f"成功加载插件：{plugin_instance.name}，插件类型：{plugin_instance.type}，插件作者{plugin_instance.author}"
                )
            except Exception as e:
                log.error(f"加载插件{name}失败：{e}")
                raise e

    async def run(self):
        event = Event(self.plugins_list, self.debug)
        event_ip, event_port = self.client_address.split(":")
        log.info(f"启动监听服务 {event_ip}:{event_port}")
        event_server = asyncio.create_task(event.run(event_ip, int(event_port)))
        log.info("监听服务启动成功！")

        web_controller = WebController(self)
        web_ip, web_port = self.web_controller_address.split(":")
        log.info(f"启动 web controller 服务 {web_ip}:{web_port}")
        web_server = asyncio.create_task(web_controller.run(web_ip, int(web_port)))
        log.info("web controller 服务启动成功！")

        try:
            await asyncio.gather(event_server, web_server)
        finally:
            await event.stop()
            await web_controller.stop()


def check_config_files(configs_path: str) -> None:
    """
    如配置文件不存在，复制默认配置文件模板
    """
    if not os.path.isfile(os.path.join(configs_path, "bot.ini")):
        log.warning("配置文件bot.ini不存在，正在复制默认配置文件模板")
        copyfile(
            os.path.join(configs_path, "bot.ini.template"),
            os.path.join(configs_path, "bot.ini"),
        )
    if not os.path.isfile(os.path.join(configs_path, "groups.ini")):
        log.warning("配置文件groups.ini不存在，正在复制默认配置文件模板")
        copyfile(
            os.path.join(configs_path, "groups.ini.template"),
            os.path.join(configs_path, "groups.ini"),
        )
    if not os.path.isfile(os.path.join(configs_path, "plugins.ini")):
        log.warning("配置文件plugins.ini不存在，正在复制默认配置文件模板")
        copyfile(
            os.path.join(configs_path, "plugins.ini.template"),
            os.path.join(configs_path, "plugins.ini"),
        )
