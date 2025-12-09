# Plugins/__init__.py
import configparser
import os
import inspect

from Interface.Api import Api

# 获取当前目录的路径
plugins_path = os.path.dirname(__file__)


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

        plugins_config_path = os.path.join(plugins_path, "plugins.ini")
        if os.path.exists(plugins_config_path):
            u_config = configparser.ConfigParser()
            u_config.read(plugins_config_path, encoding="utf-8")

            if u_config.has_section(self.name):
                for key, value in u_config.items(self.name):
                    config_dict[key] = convert_value(value)

        self.config = config_dict
