import json
import os
from pathlib import Path

import requests

import plugins.A_music.music_api
from plugins import Plugins, plugin_main
from src.event_handler import GroupMessageEventHandler
from src.PrintLog import Log


class cookies:
    "非常简单的管理cookies类的方式,因为我懒所以我没有抄项目里关于cookie管理的项"

    def __init__(self):
        self.cookie_data = {"MUSIC_U": "", "os": "pc", "appver": "8.9.70"}
        self.cookie_path = Path.cwd() / "plugins" / "A_music" / "cookies.json"

    def load_cookies(self):
        "读取cookies"
        if os.path.exists(self.cookie_path):
            with open(self.cookie_path) as r:
                cookies = json.load(r)
            self.cookie_data = cookies
            return cookies
        else:
            return None

    def qr_get_cookies(self):
        "使用二维码登陆的方式获取cookies"
        "使用前可以调用一次，当然也可以直接编辑cookies.json"
        cookie_str = plugins.A_music.music_api.qr_login()
        cookie_data = dict(item.split("=") for item in cookie_str.split(";") if "=" in item)
        with open(self.cookie_path, "w", encoding="utf-8") as f:
            json.dump(cookie_data, f, indent=2, ensure_ascii=False)
        print(f"cookie存储成功,位置为{self.cookie_path}")

    def test_cookies(self):
        "验证cookies是否有用,简单的发送，其实没什么保障"
        try:
            cookies = self.load_cookies()
            test = plugins.A_music.music_api.NeteaseAPI().get_song_url(
                1917030387, "standard", cookies=cookies
            )
            if test.get("code") == 200:
                print("成功返回数据,cookie有效")
                return True
            else:
                print(f"cookies无效，错误代码{test.get('code')}")
                return False
        except Exception as e:
            print(f"错误，代码为{e}")
            return False


class get_music:
    def __init__(self):
        "拿到url之后的请求头，其实本来就是这个请求头，意义不大"
        self.headers = {
            "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36 Chrome/91.0.4472.164 NeteaseMusicDesktop/2.10.2.200154",
            "REFERER": "https://music.163.com/",
        }
        "下载位置"
        self.music_folder = Path.cwd() / "plugins" / "A_music" / "music"
        os.makedirs(self.music_folder, exist_ok=True)
        "url直接返回mp3文件，我不需要cookie就能直接写入"

        self.cookies = cookies().load_cookies()

    def search_music(self, keywords):
        "好吧，搜索需要cookie"
        try:
            music_list = "搜索结果\n"
            result = plugins.A_music.music_api.search_music(
                keywords=keywords, cookies=self.cookies, limit=5
            )
            "返回5个结果"
            for i in range(0, 5):
                music_list = (
                    music_list
                    + str(i + 1)
                    + ":"
                    + result[i].get("name")
                    + "\n"
                    + result[i].get("artists")
                    + "\n"
                    + "歌曲id:"
                    + str(result[i].get("id"))
                    + "\n"
                )
            return music_list
        except Exception as e:
            print(f"搜索时发生错误,{e}")

    def download_music_by_id(self, id):
        "下载"
        try:
            details = plugins.A_music.music_api.NeteaseAPI().get_song_detail(id)
            title = details["songs"][0]["name"]
            url_info = plugins.A_music.music_api.url_v1(id, "standard", self.cookies)
            url = url_info["data"][0]["url"]
            type = url_info["data"][0]["encodeType"]
            r = requests.get(headers=self.headers, url=url)
            self.name = f"{title}"
            self.mp3_path = self.music_folder / f"{title}.{type}"
            if r.status_code == 200:
                if not os.path.exists(self.mp3_path):
                    with open(self.mp3_path, "wb") as down:
                        down.write(r.content)
            else:
                print(f"下载失败，错误代码{r.status_code}")
        except Exception as e:
            print(f"下载失败，请检查日志，{e}")


class A_music(Plugins):
    def __init__(self, server_address, bot):
        super().__init__(server_address, bot)
        self.name = "A_music"
        self.type = "Group"
        self.author = "cojitaZ"
        self.introduction = """
                                A_music,网易云听歌插件
                                usage: /music+音乐id 返回文件或者语音,/music+歌名 返回搜索结果
                            """

        self.init_status()

    @plugin_main(check_call_word=True, call_word=["/music"])
    async def main(self, event: GroupMessageEventHandler, debug):
        message = event.message
        if "/music" in message[0:6]:
            Log.debug(f"检测到music请求:{message[6:]}")

            if message[7:].isdecimal():
                "请求歌曲"
                try:
                    id = message[7:]
                    music = get_music()
                    music.download_music_by_id(id=id)
                    reply_message = music.name + "下载完成"
                    self.api.groupService.send_group_msg(
                        group_id=event.group_id, message=reply_message
                    )
                    self.api.groupService.send_group_record_msg(
                        group_id=event.group_id, file_path=music.mp3_path
                    )
                except Exception as e:
                    Log.error(f"插件{self.name}运行时出错，{e}")
                else:
                    Log.debug(f"成功向{event.group_id}发送音乐", debug)
                return
            else:
                "请求搜索结果"
                try:
                    keywords = message[7:]
                    music = get_music()
                    reply_message = music.search_music(keywords=keywords)
                    self.api.groupService.send_group_msg(
                        group_id=event.group_id, message=reply_message
                    )
                except Exception as e:
                    Log.error(f"插件{self.name}运行时出错，{e}")
                else:
                    Log.debug(f"成功向{event.group_id}发送搜索结果", debug)

                return
