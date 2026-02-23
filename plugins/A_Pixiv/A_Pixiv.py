import os
import time
from pathlib import Path

import requests

from plugins import Plugins, plugin_main
from src.event_handler import GroupMessageEventHandler
from src.PrintLog import Log

log = Log()


class pixiv_img_get:
    def __init__(self, pid):
        "一个简单的获取数据的类"
        self.pid = str(pid)
        self.illust_url = f"https://www.pixiv.net/touch/ajax/illust/details?illust_id={pid}"

        # 1. 添加必要的请求头，避免403
        self.headers = {
            "Host": "www.pixiv.net",
            "referer": "https://www.pixiv.net/",
            "origin": "https://accounts.pixiv.net",
            "accept-language": "zh-CN,zh;q=0.9",  # 返回translation,中文翻译的标签组
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36",
        }
        self.ajax_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:52.0) Gecko/20100101 Firefox/52.0",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3",
            "Accept-Encoding": "",
            "Connection": "keep-alive",
        }

        self.folder_path = str(Path.cwd()) + f"\\plugins\\A_Pixiv\\image\\{pid}"

        # 路径：QQ-Bot\\plugins\\A_Pixiv\\image\\{pid}

        try:
            # 2. 发送请求并检查状态码
            self.r = requests.get(self.illust_url, headers=self.headers, timeout=10)
            self.r.raise_for_status()  # 如果状态码不是200，会抛出异常

            # 3. 解析JSON
            self.data = self.r.json()

            # 4. 安全地获取嵌套数据，避免键不存在时报错
            illust_details = self.data.get("body", {}).get("illust_details", {})

            if "manga_a" in illust_details and illust_details["manga_a"]:
                # 多图情况：直接用 manga_a
                self.manga = illust_details["manga_a"]

            else:
                # 单图情况：构造一个兼容的列表
                self.manga = [
                    {
                        "page": 0,
                        "url_big": illust_details["url_big"],
                        "url": illust_details["url"],
                        "url_small": illust_details.get("url_s", ""),
                    }
                ]
            self.title = illust_details.get("meta", {}).get("ogp", {}).get("title", {})
            self.tags = illust_details.get("tags", {})
            self.meta = illust_details.get("meta", {})
        except requests.exceptions.RequestException as e:
            print(f"网络请求失败: {e}")
            self.manga = []
            self.title = "获取失败"
        except ValueError as e:
            print(f"JSON解析失败: {e}")
            self.manga = []
            self.title = "获取失败"

    def get_img_urls_origin(self, requirement="origin"):
        "用来决定使用什么，目前看来有点多余，因为我没法请求master"
        if requirement == "small":
            urls = [item["url_small"] for item in self.manga]
            return urls
        elif requirement == "origin":
            urls = [item["url_big"] for item in self.manga]
            return urls
        else:
            return

    def img_urls(self, urls):
        "简简单单替换为可以get的"
        old_url_head = "pximg.net"
        new_url_head = "pixiv.cat"
        urls = [url.replace(old_url_head, new_url_head) for url in urls]
        return urls

    def download_img(self, urls):
        """下载器（假设 urls 是纯 URL 列表）"""
        os.makedirs(self.folder_path, exist_ok=True)

        for i, url in enumerate(urls):  # 用 enumerate 自动生成索引
            try:
                r = requests.get(url=url, headers=self.ajax_headers, timeout=10)
                if r.status_code == 200:
                    file_path = os.path.join(self.folder_path, f"{self.pid}_p{i}.png")
                    with open(file_path, "wb") as down:
                        down.write(r.content)
                    print(f"{self.pid}_p{i}.png 下载完成")
                else:
                    print(f"{self.pid}_p{i}.png 下载失败, 错误代码 {r.status_code}")
                time.sleep(1)

            except Exception as e:
                print(f"{self.pid}_p{i}.png 下载失败, {e}")


class A_Pixiv(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "A_Pixiv"
        self.type = "Group"
        self.author = "cojitaZ"
        self.introduction = """
                                简易的蓝p图片下载器
                                usage: pid+数字
                            """
        self.init_status()

    @plugin_main(call_word="pid")
    async def main(self, event: GroupMessageEventHandler, debug):
        message = event.message
        log.debug("尝试启用中", debug)

        try:
            pid = message[3:]
            if pid.isdecimal():
                pixic = pixiv_img_get(pid=pid)
                reply_message = f"{pixic.title}"
                self.api.groupService.send_group_msg(group_id=event.group_id, message=reply_message)
                urls = pixic.get_img_urls_origin()
                urls = pixic.img_urls(urls=urls)
                pixic.download_img(urls=urls)
            else:
                "输入并非纯数字"
                self.api.groupService.send_group_msg(
                    group_id=event.group_id, message="输入并非纯数字"
                )
        except Exception as e:
            log.debug(f"插件{self.name}运行时出错，作者{self.author}")
            log.debug(f"{e}")
        else:
            log.debug(f"成功向{event.group_id}发送内容", debug)

        return
