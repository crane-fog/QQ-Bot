# Plugins/__init__.py
import configparser
import os
import functools

from Interface.Api import Api

# 获取当前目录的路径
plugins_path = os.path.dirname(__file__)


def plugin_main(check_call_word=True, call_word: list = None, check_group=True, require_db=False):
    """
    :param check_call_word: 是否检查触发词 (默认 True)
    :param call_word: 插件的触发词列表
    :param check_group: 是否检查群权限 (默认 True)
    :param require_db: 是否需要数据库 (默认 False)
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, event, debug):
            # 检查数据库依赖
            if require_db and not self.bot.database_enable:
                self.set_status("error")
                return

            # 检查群权限
            if check_group and hasattr(event, "group_id"):
                group_id = event.group_id
                effected_group_id: list = self.config.get("effected_group")
                if group_id not in effected_group_id:
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
        self.api = Api(server_address)
        self.bot = bot
        self.name = "name"
        self.type = "type"
        self.author = "xxx"
        self.introduction = "xxx"
        self.status = None  # running/disable/error
        self.error_info = ""
        self.config = None

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
        在初始化插件对象的时候加载配置文件，并设置状态为running
        """
        self.load_config()
        self.status = "running"

    def load_config(self):
        """
        用于从插件的配置文件中加载插件的配置参数
        :return: 不返回值，加载完成的配置直接赋值给self.config
        """

        def convert_value(value):
            """
            自动的尝试将配置文件中的信息转化为合适的数据类型
            :param value:
            :return:
            """
            # 尝试将值转换为布尔值
            if value.lower() in ("true", "false"):
                return value.lower() == "true"
            # 尝试将值转换为逗号分隔的列表
            if "," in value:
                items = value.split(",")
                # 尝试将每个列表项转换为整数
                try:
                    return [int(item) for item in items]
                except ValueError:
                    return items
            # 否则将值作为字符串返回
            return value

        config_dict = {}

        # 读取插件自身的基础配置
        plugins_config_path = os.path.join(plugins_path, "plugins.ini")
        if os.path.exists(plugins_config_path):
            u_config = configparser.ConfigParser()
            u_config.read(plugins_config_path, encoding="utf-8")

            if u_config.has_section(self.name):
                for key, value in u_config.items(self.name):
                    config_dict[key] = convert_value(value)

        # 读取群组配置，构建 effected_group 列表
        groups_config_path = os.path.join(plugins_path, "groups.ini")
        if os.path.exists(groups_config_path):
            g_config = configparser.ConfigParser()
            g_config.read(groups_config_path, encoding="utf-8")

            effected_group = []
            for section in g_config.sections():
                # 检查 section 是否为纯数字（即群号）
                if section.isdigit():
                    # 检查该插件在此群是否启用
                    if g_config.has_option(section, self.name):
                        if g_config.getboolean(section, self.name):
                            # 提取群号
                            try:
                                group_id = int(section)
                                effected_group.append(group_id)
                            except ValueError:
                                pass

        # 将构建好的 effected_group 放入配置中
        config_dict["effected_group"] = effected_group
        self.config = config_dict
