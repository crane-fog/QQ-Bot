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
    "这个类我尽量不用框架内的东西，这样在外面也能用"
    def __init__(self, pid=None):
        "一个简单的获取数据的类"
        self.pid = str(pid)
        self.illust_url = f"https://www.pixiv.net/touch/ajax/illust/details?illust_id={pid}"

        # 添加必要的请求头，避免403
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
        origin_folder_path = Path.cwd() /"plugins" /"A_Pixiv" /"image"

        self.folder_path_SFW  = origin_folder_path / "SFW"  /f"{pid}"
        self.folder_path_NSFW = origin_folder_path / "NSFW" /f"{pid}"
        self.folder_path_MFSN = origin_folder_path / "MFSN" /f"{pid}"
        self.paths = []  # paths 列表，待会要加入聊天记录

        # 路径：QQ-Bot\\plugins\\A_Pixiv\\image\\SFW/NSFW/MFSN\\{pid}
        # 目前用的是当前路径
        if pid:
            try:
                "请求信息部分"
                # 发送请求并检查状态码
                self.r = requests.get(self.illust_url, headers=self.headers, timeout=10)
                self.r.raise_for_status()  # 如果状态码不是200，会抛出异常
                self.data = self.r.json()
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
                self.title = self.title[:-6]
                self.tags = illust_details.get("tags", {})
                if "R-18" in self.tags:
                    self.folder_path = self.folder_path_NSFW
                else:
                    self.folder_path = self.folder_path_SFW
                self.R_18 = "R-18" in self.tags
                self.meta = illust_details.get("meta", {})
                
                

                print(f"获取成功，图像为{self.title},R-18:{self.R_18}")
                self.error="no"
            except requests.exceptions.RequestException as e:
                print(f"网络请求失败: {e}")
                self.manga = []
                self.title = "获取失败"
                self.error=f"网络请求失败: {e}"
            except ValueError as e:
                print(f"JSON解析失败: {e}")
                self.manga = []
                self.title = "获取失败"
                self.error=f"JSON解析失败: {e}"
            except Exception as e:
                print(f"错误：{e}")
                self.manga = []
                self.title = "获取失败"
                self.error=f"错误：{e}"
        else:
            # 全部删掉重新建
            try:
                if os.path.exists(origin_folder_path / "SFW"):
                    shutil.rmtree(origin_folder_path / "SFW")
                    os.makedirs(origin_folder_path / "SFW")
                if os.path.exists(origin_folder_path / "NSFW"):
                    shutil.rmtree(origin_folder_path / "NSFW")
                    os.makedirs(origin_folder_path / "NSFW")
                if os.path.exists(origin_folder_path / "MFSN"):
                    shutil.rmtree(origin_folder_path / "MFSN")
                    os.makedirs(origin_folder_path / "MFSN")
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

            self.page = len(urls)  # 页数
            return urls
        else:
            return

    def img_urls(self, urls):
        "简简单单替换为可以get的"
        old_url_head = "pximg.net"
        new_url_head = "pixiv.cat"
        urls = [url.replace(old_url_head, new_url_head) for url in urls]
        return urls
    def download_img_by_url(self,img_name,url,file_path,retry_times=5):
        "url下载器，内置倒转,处理了429情形，增加了最大重试上限"
        if retry_times>0:
            try:
                "存在判断：如果已经存在就不请求"
                if os.path.exists(file_path) and os.path.getsize(file_path) > 1000:
                        print(f"图片{img_name}已存在")
                        # R-18翻转
                        if not ( "预览" in img_name) and self.R_18:
                            origin_path = file_path
                            file_path = os.path.join(
                                self.folder_path_MFSN, f"{img_name}"
                            )
                            "判断好像出问题了，直接就不判得了"
                            Image.open(origin_path).rotate(180).save(file_path)
                            
                        self.paths.append(file_path)
                        
                        return True
                else:
                    r = requests.get(url=url, headers=self.ajax_headers, timeout=10)
                    if r.status_code == 200:
                            
                        with open(file_path, "wb") as down:
                            down.write(r.content)
                        # R-18翻转
                        if not ( "预览" in img_name) and self.R_18:
                            origin_path = file_path
                            file_path = os.path.join(
                                self.folder_path_MFSN, f"{img_name}"
                            )
                            
                            Image.open(origin_path).rotate(180).save(file_path)
                            print(f"R-18作品翻转完成，位置{file_path}")
                        
                        # 加入列表
                            self.paths.append(file_path)
                            print(f"{img_name} 下载完成,位置为{file_path}")
                    elif r.status_code==429:
                        "429：繁忙，重试"
                        print("429繁忙，等待4-5秒后重试")
                        time_layer = random.uniform(3.9, 5.1)
                        time.sleep(time_layer)

                        return self.download_img_by_url(
                                img_name=img_name,
                                url=url,
                                file_path=file_path,
                                retry_times=retry_times
                        )

                    else:
                        print(f"{img_name} 下载失败, 错误代码 {r.status_code}")
                        return False
                    
                    time_layer = random.uniform(0.9, 1.4)
                    time.sleep(time_layer)
                    return  True

            except Exception as e:
                "超时重试"
                print(f"{img_name} 下载失败, {e},剩余重试次数{retry_times}")
                return self.download_img_by_url(
                            img_name=img_name,
                            url=url,
                            file_path=file_path,
                            retry_times=retry_times-1
                    )

        else:
            print(f"重试次数达到上限，{img_name}下载失败")
            return False
            
    

    def download_img(self, urls):
        """整体下载器（假设 urls 是纯 URL 列表）"""
        os.makedirs(self.folder_path, exist_ok=True)
        if self.R_18:
            os.makedirs(self.folder_path_MFSN, exist_ok=True)

        for i, url in enumerate(urls):  
            "生成名字"
            self.format = url[-3:]
            if i == self.page - 1:
                file_path = os.path.join(self.folder_path, f"{self.pid}_预览.{self.format}")
                img_name = f"{self.pid}_预览.{self.format}"
            else:
                file_path = os.path.join(self.folder_path, f"{self.pid}_p{i}.{self.format}")
                img_name = f"{self.pid}_p{i}.{self.format}"
            if not self.download_img_by_url(img_name=img_name,file_path=file_path,url=url):
                "下载失败直接断进程"
                return False


        "预览图位置"
        self.preview_path = self.paths[- 1]
        return True

    def get_forward(self):
        "原图加入聊天记录"
        print(f"\nforward打包\n")
        f = Forward("000")
        for i, file_path in enumerate(self.paths):
            if i < self.page - 1:
                f.add_sth(type="image", file_path=file_path)
                print(f"已经加入图片，位置{file_path}")
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
        self.send_R_18 = False #是否发送R-18作品的倒转图
        self.init_status()

    @plugin_main(call_word=["pid", "p_clean"], check_call_word=True)
    async def main(self, event: GroupMessageEventHandler, debug):
        message = event.message
        if "pid" in message[0:3]:
            # 下载部分
            pid = message[3:]
            log.debug(f"截取到pid:{pid},请求中.....", debug)

            try:
                
                if pid.isdecimal():
                    pixic = pixiv_img_get(pid=pid)
                    

                    # 一套标准流程
                    if pixic.error=="no":
                        urls = pixic.get_img_urls_origin()
                        urls = pixic.img_urls(urls=urls)
                        if  pixic.download_img(urls=urls):
                            forward_message = pixic.get_forward()
                        else:
                            log.error("下载失败")
                            self.api.groupService.send_group_msg(
                                group_id=event.group_id,
                                message="下载失败了!请检查日志"
                            )
                            return 

                        reply_message = f"标题:{pixic.title}\ntags:{pixic.tags}"

                        if pixic.R_18:
                            self.api.groupService.send_group_msg(
                                group_id=event.group_id,
                                message=reply_message + "\n由于请求为R-18作品，小孩子还是不要看啦...",
                            )
                            if self.send_R_18:
                                self.api.groupService.send_group_forward_msg(
                                        group_id=event.group_id, forward_message=forward_message
                                    )
                            else :
                                self.api.groupService.send_group_msg(
                                    group_id=event.group_id,
                                    message="基于本群的bot设置,R-18图像的倒转将不会被发出"
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
                        "某种失败"
                        self.api.groupService.send_group_msg(
                                    group_id=event.group_id,
                                    message=pixic.error
                                )
                        if pixic.error[0:4]=="网络请求":
                            self.api.groupService.send_group_msg(
                                        group_id=event.group_id,
                                        message="看来网络不是很稳定呢..."
                                    )
                        elif pixic.error[0:4]=="JSON":
                            self.api.groupService.send_group_msg(
                                        group_id=event.group_id,
                                        message="JSON解析失败了....是获取到的数据有问题吗？"
                                    )
                        else:
                            self.api.groupService.send_group_msg(
                                        group_id=event.group_id,
                                        message="某种未知的错误，看看是不是插件写错啦？"
                                    )
                else:
                    "输入并非纯数字"
                    self.api.groupService.send_group_msg(
                        group_id=event.group_id, message="输入并非纯数字"
                    )
            except Exception as e:
                log.error(f"插件{self.name}运行时出错，{e}")
            else:
                log.debug(f"成功处理{event.group_id}的pid请求", debug)

            return
        elif message == "p_clean" :
            try:
                """
                直接删除整个文件夹，然后重新创建空文件夹
                """
                pixiv_img_get()
                self.api.groupService.send_group_msg(group_id=event.group_id, message="已全部删除")
            except Exception as e:
                log.error(f"插件{self.name}运行时出错，{e}")
            else:
                log.debug(f"成功处理{event.group_id}的删除请求", debug)
