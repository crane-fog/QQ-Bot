import os
import random
import shutil
import time
from pathlib import Path

import requests
from PIL import Image

from plugins import Plugins, plugin_main
from src.event_handler import GroupMessageEventHandler
from src.PrintLog import Log
from utils.CQType import Forward

log = Log()


class pixiv_img_get:
    def __init__(self, pid=None):
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
        # 图片的请求头
        self.ajax_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:52.0) Gecko/20100101 Firefox/52.0",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3",
            "Accept-Encoding": "",
            "Connection": "keep-alive",
        }
        origin_folder_path = str(Path.cwd()) + "\\plugins\\A_Pixiv\\image"

        self.folder_path_SFW = origin_folder_path + f"\\SFW\\{pid}"
        self.folder_path_NSFW = origin_folder_path + f"\\NSFW\\{pid}"
        self.folder_path_MFSN = origin_folder_path + f"\\MFSN\\{pid}"

        # 路径：QQ-Bot\\plugins\\A_Pixiv\\image\\SFW/NSFW/MFSN\\{pid}
        # 目前用的是当前路径
        if pid:
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
                self.title = self.title[:-11]
                self.tags = illust_details.get("tags", {})
                if "R-18" in self.tags:
                    self.folder_path = self.folder_path_NSFW
                else:
                    self.folder_path = self.folder_path_SFW

                self.R_18 = "R-18" in self.tags

                self.meta = illust_details.get("meta", {})
                print(f"获取成功，图像为{self.title},R-18:{self.R_18}")
            except requests.exceptions.RequestException as e:
                print(f"网络请求失败: {e}")
                self.manga = []
                self.title = "获取失败"
            except ValueError as e:
                print(f"JSON解析失败: {e}")
                self.manga = []
                self.title = "获取失败"
        else:
            # 全部删掉重新建
            try:
                if os.path.exists(origin_folder_path + "\\SFW"):
                    shutil.rmtree(origin_folder_path + "\\SFW")
                    os.makedirs(origin_folder_path + "\\SFW")
                if os.path.exists(origin_folder_path + "\\NSFW"):
                    shutil.rmtree(origin_folder_path + "\\NSFW")
                    os.makedirs(origin_folder_path + "\\NSFW")
                if os.path.exists(origin_folder_path + "\\MFSN"):
                    shutil.rmtree(origin_folder_path + "\\MFSN")
                    os.makedirs(origin_folder_path + "\\MFSN")
                print("清除完毕")
            except Exception as e:
                print(f"清除失败,{e}")

    def get_img_urls_origin(self, requirement="origin"):
        "用来决定使用什么，目前看来有点多余，因为我不太可能全部请求small"
        if requirement == "small":
            urls = [item["url_small"] for item in self.manga]
            return urls
        elif requirement == "origin":
            urls = [item["url_big"] for item in self.manga]
            "这里加上预览图"
            urls.append(self.manga[0]["url_small"])
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
        if self.R_18:
            os.makedirs(self.folder_path_MFSN, exist_ok=True)
        self.page = len(urls)  # 页数
        self.paths = []  # paths 列表，待会要加入聊天记录

        for i, url in enumerate(urls):  # 用 enumerate 自动生成索引
            try:
                r = requests.get(url=url, headers=self.ajax_headers, timeout=10)
                if r.status_code == 200:
                    self.format = url[-3:]

                    if i == self.page - 1:
                        file_path = os.path.join(self.folder_path, f"{self.pid}_预览.{self.format}")
                        img_name = f"{self.pid}_预览.{self.format}"
                    else:
                        file_path = os.path.join(self.folder_path, f"{self.pid}_p{i}.{self.format}")
                        img_name = f"{self.pid}_p{i}.{self.format}"
                    if os.path.exists(file_path) and os.path.getsize(file_path) > 1000:
                        print(f"图片{img_name}已存在")
                    else:
                        with open(file_path, "wb") as down:
                            down.write(r.content)

                    # R-18翻转
                    if i <= self.page - 1 and self.R_18:
                        origin_path = file_path
                        file_path = os.path.join(
                            self.folder_path_MFSN, f"{self.pid}_p{i}.{self.format}"
                        )
                        if os.path.exists(file_path) and os.path.getsize(file_path) > 1000:
                            Image.open(origin_path).rotate(180).save(file_path)
                        print("R-18作品翻转完成")
                    # 加入列表
                    self.paths.append(file_path)
                    print(f"{img_name} 下载完成")
                else:
                    print(f"{img_name} 下载失败, 错误代码 {r.status_code}")
                time_layer = random.uniform(0.9, 1.4)
                time.sleep(time_layer)

            except Exception as e:
                print(f"{img_name} 下载失败, {e}")
        "预览图位置"
        self.preview_path = self.paths[self.page - 1]

    def get_forward(self):
        "原图加入聊天记录"
        f = Forward("000")
        for i, file_path in enumerate(self.paths):
            if i < self.page - 1:
                f.add_sth(type="image", file_path=file_path)
        return f.message


class A_Pixiv(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "A_Pixiv"
        self.type = "Group"
        self.author = "cojitaZ"
        self.introduction = """
                                简易的蓝p图片下载器,同时附带删除的功能
                                usage: pid+数字，p_clean
                            """
        self.send_R_18 = True
        self.init_status()

    @plugin_main(call_word=["pid", "p_clean"], check_call_word=True)
    async def main(self, event: GroupMessageEventHandler, debug):
        message = event.message
        if "pid" in message[0:3]:
            # 下载部分

            log.debug("尝试启用中", debug)

            try:
                pid = message[3:]
                if pid.isdecimal():
                    pixic = pixiv_img_get(pid=pid)

                    # 一套标准流程
                    urls = pixic.get_img_urls_origin()
                    urls = pixic.img_urls(urls=urls)
                    pixic.download_img(urls=urls)
                    forward_message = pixic.get_forward()

                    reply_message = f"标题:{pixic.title}\ntags:{pixic.tags}"

                    if pixic.R_18:
                        self.api.groupService.send_group_msg(
                            group_id=event.group_id,
                            message=reply_message + "\n\n由于请求为R-18作品，小孩子还是不要看啦...",
                        )
                        if self.send_R_18:
                            self.api.groupService.send_group_forward_msg(
                                group_id=event.group_id, forward_message=forward_message
                            )
                    else:
                        self.api.groupService.send_group_msg_with_img(
                            group_id=event.group_id,
                            message=reply_message,
                            image_path=pixic.preview_path,
                        )
                        self.api.groupService.send_group_forward_msg(
                            group_id=event.group_id, forward_message=forward_message
                        )
                else:
                    "输入并非纯数字"
                    self.api.groupService.send_group_msg(
                        group_id=event.group_id, message="输入并非纯数字"
                    )
            except Exception as e:
                log.error(f"插件{self.name}运行时出错，{e}")
            else:
                log.debug(f"成功向{event.group_id}发送内容", debug)

            return
        elif message == "p_clean":
            try:
                """
                直接删除整个文件夹，然后重新创建空文件夹
                """
                pixiv_img_get()
                self.api.groupService.send_group_msg(group_id=event.group_id, message="已全部删除")
            except Exception as e:
                log.error(f"插件{self.name}运行时出错，{e}")
            else:
                log.debug(f"成功向{event.group_id}发送内容", debug)
