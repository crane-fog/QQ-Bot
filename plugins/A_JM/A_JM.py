import os
from pathlib import Path

import jmcomic
import pyzipper

from plugins import Plugins, plugin_main
from src.event_handler import GroupMessageEventHandler
from src.PrintLog import Log
from utils.CQType import Reply

option_path = str(Path.cwd()) + "\plugins\A_JM\option.yml"

log = Log()
option = jmcomic.create_option_by_file(option_path)


class A_JM(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "A_JM"
        self.type = "Group"
        self.author = "cojitaZ"
        self.introduction = """
                                简单的群聊下载JM本子用具
                                usage: JM+数字，我没有加判断，输入别的可能导致不存在
                            """
        self.init_status()

    @plugin_main(call_word="JM")
    async def main(self, event: GroupMessageEventHandler, debug):
        message = event.message
        if "JM" in message[0:2]:
            JMid = message[2:]
            reply_message = f"尝试下载{JMid},请稍等..."
            try:
                self.api.groupService.send_group_msg(group_id=event.group_id, message=reply_message)
                file_path = str(Path.cwd()) + f"\plugins\A_JM\comic\{JMid}.zip"
                txt_path = str(Path.cwd()) + f"\plugins\A_JM\comic\{JMid}.txt"
                if not os.path.exists(file_path):
                    option.download_album(JMid)
                    log.debug("执行简单压缩...")
                    os.rename(file_path, txt_path)
                    pwd = bytes(JMid, encoding="utf-8")
                    with pyzipper.AESZipFile(
                        file_path, "w", compression=pyzipper.ZIP_STORED, encryption=pyzipper.WZ_AES
                    ) as zp:
                        zp.setpassword(pwd)
                        zp.write(txt_path, f"{JMid}.txt")

                    if os.path.exists(txt_path):
                        os.remove(txt_path)
                else:
                    log.debug(f"本子{JMid}已存在，无需重复下载")
                self.api.groupService.send_group_file(
                    group_id=event.group_id, file_path=file_path, name=f"{JMid}.zip"
                )
                reply_message = Reply(id=event.message_id) + f"{JMid}下载已完成"
                self.api.groupService.send_group_msg(group_id=event.group_id, message=reply_message)
            except Exception as e:
                log.debug(f"插件{self.name}运行时出错，作者{self.author}", debug)

                self.api.groupService.send_group_msg(group_id=event.group_id, message=f"{e}")
                self.api.groupService.send_group_msg(
                    group_id=event.group_id,
                    message="哎呀，看来报错了呢\n请检查是否输入了正确的种子号\n也有可能是网络不太稳定呢...",
                )
                if os.path.exists(file_path):
                    os.remove(file_path)
                if os.path.exists(txt_path):
                    os.remove(txt_path)
                log.debug(f"{e}", debug)
            else:
                log.debug(f"成功向{event.group_id}发送本子{JMid}", debug)

        return
