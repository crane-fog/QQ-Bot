# plugins/__init__.py
import configparser
import os
from functools import wraps

from src.Api import Api


def plugin_main(check_call_word=True, call_word: list = None, check_group=True, require_db=False):
    """
    :param check_call_word: 是否检查触发词 (默认 True)
    :param call_word: 插件的触发词列表
    :param check_group: 是否检查群权限 (默认 True)
    :param require_db: 是否需要数据库 (默认 False)
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(self, event, debug):
            # 检查数据库依赖
            if require_db and not self.bot.database_enable:
                self.set_status("error")
                return

            # 检查群权限
            if check_group and hasattr(event, "group_id"):
                group_id = event.group_id
                if group_id not in self.effected_groups:
                    return

            # 检查触发词
            if check_call_word and call_word is not None:
                if not hasattr(event, "message"):
                    return
                message = event.message
                if not any(message.startswith(word) for word in call_word):
                    return

            # 更新运行状态
            if self.status != "error":
                self.set_status("running")

            return await func(self, event, debug)

        return wrapper

    return decorator


class Plugins:
    """
    插件的父类，所有编写的插件都继承这个类
    """

    def __init__(self, server_address: str, bot):
        self.server_address = server_address
        self.api: Api = Api(server_address)
        self.bot = bot
        self.name = "name"
        self.type = "type"
        self.author = "xxx"
        self.introduction = "xxx"
        self.status = None  # running/disable/error
        self.error_info = ""
        self.config: configparser.SectionProxy = None
        self.effected_groups: list[int] = []

    async def main(self, event, debug):
        raise NotImplementedError("方法还未实现")

    def set_status(self, status: str, error_info: str = ""):
        """
        自带方法，设置该插件的运行情况
        :param error_info: 如果状态为error，在此处写明报错原因
        :param status: 可选参数：running, disable, error
        :return:
        """
        self.status = status
        self.error_info = error_info

    def init_status(self):
        """
        在初始化插件对象的时候加载生效群聊列表，并设置状态为running
        """
        self.load_effected_groups()
        self.status = "running"

    def load_effected_groups(self):
        """
        用于从插件的配置文件中加载插件的生效群聊列表
        :return: 不返回值，直接赋值给self.effected_groups
        """
        g_config = configparser.ConfigParser()
        with open(os.path.join(self.bot.configs_path, "groups.ini"), encoding="utf-8") as f:
            g_config.read_file(f)

        self.effected_groups = []
        for section in g_config.sections():
            if section.isdigit():
                # 检查该插件在此群是否启用
                if g_config.has_option(section, self.name):
                    if g_config.getboolean(section, self.name):
                        # 提取群号
                        group_id = int(section)
                        self.effected_groups.append(group_id)
