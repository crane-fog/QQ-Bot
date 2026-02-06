from Logging.PrintLog import Log
from Plugins import Plugins, plugin_main

log = Log()

"""
这是一个插件的模板，开发一个新的插件至少应该包含以下部分
注意：
    插件的 类名、self.name 必须完全一致（为减少心智负担起见，建议它们与文件名、文件夹名也一致）
"""


class ExamplePlugin(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "ExamplePlugin"  # 插件的名字
        self.type = "Group"  # 插件的类型（这个插件是在哪种消息类型中触发的）
        self.author = "somebody"  # 插件开发作者（不用留真名，但是当插件报错的时候需要根据这个名字找到对应的人来修）
        self.introduction = """
                                插件的介绍信息，会在 TheresaHelp 插件被调用时显示
                                usage: 插件触发方式的介绍
                            """
        self.init_status()

    @plugin_main(
        check_call_word=False, check_group=False
    )  # 通用检查装饰器，参数根据具体需求修改，详见注释
    async def main(self, event, debug):
        """
        :param event: 消息事件体
        :param debug: 是否输出 debug 信息
        函数的入口，每个插件都必须有一个主入口
        受到框架限制，所有插件的 main 函数的参数必须是这几个，不能多也不能少
        注意！所有的插件都需要写成异步的方法，防止某个插件出问题卡死时导致整个程序阻塞
        """

        self.set_status("error")
        log.debug("成功将该插件状态变为error", debug)
        log.error(f"这个错误是由测试插件：{self.name}主动产生的，Nothing goes wrong！")
        return
