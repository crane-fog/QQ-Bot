import configparser
import os

import requests
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

total_lines_read = 0
last_cleared_line = 0


def create_web_app(web_controller):
    basedir = os.path.abspath(os.path.dirname(__file__))
    # 设置模板文件夹路径
    template_dir = os.path.join(basedir, "templates")
    # 静态文件目录路径
    static_dir = os.path.join(basedir, "static")

    app = FastAPI(title="Web Controller")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    templates = Jinja2Templates(directory=template_dir)

    @app.get("/")
    async def index(request: Request):
        return templates.TemplateResponse("index.html", {"request": request})

    @app.get("/baseInfo.html")
    async def base_info(request: Request):
        bot_info = web_controller.get_bot_info()
        plugins_info = web_controller.get_plugins_init_info()
        return templates.TemplateResponse(
            "baseInfo.html",
            {
                "request": request,
                "bot_info": bot_info,
                "plugins_info": plugins_info,
            },
        )

    @app.get("/log.html")
    async def log_page(request: Request):
        return templates.TemplateResponse("log.html", {"request": request})

    @app.get("/leave-log.html")
    async def leave_log():
        global total_lines_read, last_cleared_line
        total_lines_read = last_cleared_line
        return JSONResponse({"success": True})

    @app.get("/plugins.html")
    async def plugins_page(request: Request):
        plugins_info = web_controller.get_all_plugins_info()
        return templates.TemplateResponse(
            "plugins.html",
            {"request": request, "plugins": plugins_info},
        )

    @app.get("/log.out")
    async def log_file():
        global total_lines_read

        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_file_path = os.path.join(parent_dir, "log.out")

        with open(log_file_path, encoding="utf-8") as file:
            all_lines = file.readlines()
            lines_to_send = all_lines[total_lines_read:]
            total_lines_read = len(all_lines)

        return PlainTextResponse("".join(lines_to_send))

    @app.post("/clear-log")
    async def clear_log():
        global total_lines_read, last_cleared_line
        last_cleared_line = total_lines_read
        return JSONResponse({"success": True})

    @app.post("/save_config")
    async def save_config(request: Request):
        config_data = await request.json()
        result = web_controller.save_config(config_data)
        return JSONResponse(result)

    return app


class WebController:
    def __init__(self, bot):
        self.bot = bot
        self.api = bot.api
        self._server = None

    async def run(self, ip, port):
        app = create_web_app(self)
        config = uvicorn.Config(app=app, host=ip, port=port, log_level="warning", access_log=False)
        self._server = uvicorn.Server(config)
        await self._server.serve()

    async def stop(self):
        if self._server is not None:
            self._server.should_exit = True

    def get_bot_info(self):
        login_info = self.api.botSelfInfo.get_login_info().get("data")
        user_id = login_info.get("user_id")
        nickname = login_info.get("nickname")
        response = requests.get(f"http://q1.qlogo.cn/g?b=qq&nk={user_id}&s=100")
        save_path = "static/images/bot-avatar.png"
        basedir = os.path.abspath(os.path.dirname(__file__))

        save_path = os.path.join(basedir, save_path)
        with open(save_path, "wb") as f:
            f.write(response.content)

        bot_name = self.bot.bot_name
        return {
            "avatar": "bot-avatar.png",
            "qq": user_id,
            "nickname": nickname,
            "name": bot_name,
        }

    def get_plugins_init_info(self):
        active_plugins = []
        inactive_plugins = []
        error_plugins = []
        for plugins in self.bot.plugins_list:
            plugins_status = plugins.status
            plugins_name = plugins.name
            plugins_type = plugins.type
            plugins_author = plugins.author
            plugins_info = {
                "name": plugins_name,
                "info": f"{plugins_name}——类型：{plugins_type}, 作者：{plugins_author}",
            }
            if plugins_status == "running":
                active_plugins.append(plugins_info)
            elif plugins_status == "disable":
                inactive_plugins.append(plugins_info)
            elif plugins_status == "error":
                error_plugins.append(plugins_info)

        return {
            "active_plugins_count": len(active_plugins),
            "inactive_plugins_count": len(inactive_plugins),
            "error_plugins_count": len(error_plugins),
            "active_plugins": active_plugins,
            "inactive_plugins": inactive_plugins,
            "error_plugins": error_plugins,
        }

    def get_all_plugins_info(self):
        plugins_info = {}
        loaded_plugin_names = set()

        for plugins in self.bot.plugins_list:
            plugins_name = plugins.name
            loaded_plugin_names.add(plugins_name)
            plugins_type = plugins.type
            plugins_status = plugins.status
            plugins_info[plugins_name] = {}
            plugins_info[plugins_name]["type"] = plugins_type
            plugins_info[plugins_name]["status"] = plugins_status
            plugins_author = plugins.author
            plugins_introduction = plugins.introduction
            plugins_error_info = plugins.error_info
            plugins_info[plugins_name]["other_info"] = {
                "author": plugins_author,
                "introduction": plugins_introduction,
                "error_info": plugins_error_info,
            }
            plugins_info[plugins_name]["config"] = plugins.config

        plugins_config_path = os.path.join(self.bot.configs_path, "plugins.ini")
        groups_config_path = os.path.join(self.bot.configs_path, "groups.ini")

        config = configparser.ConfigParser()
        config.optionxform = str
        if os.path.exists(plugins_config_path):
            config.read(plugins_config_path, encoding="utf-8")

        g_config = configparser.ConfigParser()
        g_config.optionxform = str
        if os.path.exists(groups_config_path):
            g_config.read(groups_config_path, encoding="utf-8")

        for item in os.listdir(self.bot.plugins_path):
            plugin_dir = os.path.join(self.bot.plugins_path, item)
            if os.path.isdir(plugin_dir) and not item.startswith("__"):
                if item not in loaded_plugin_names:
                    plugin_config = {}
                    if config.has_section(item):
                        for k, v in config.items(item):
                            if v.lower() in ("true", "false"):
                                plugin_config[k] = v.lower() == "true"
                            elif "," in v:
                                try:
                                    plugin_config[k] = [int(x) for x in v.split(",")]
                                except Exception:
                                    plugin_config[k] = v.split(",")
                            else:
                                plugin_config[k] = v

                    if "enable" not in plugin_config:
                        plugin_config["enable"] = False

                    effected_group = []
                    for section in g_config.sections():
                        if section.isdigit():
                            if g_config.has_option(section, item):
                                if g_config.getboolean(section, item):
                                    try:
                                        effected_group.append(int(section))
                                    except ValueError:
                                        pass
                    plugin_config["effected_group"] = effected_group

                    plugins_info[item] = {
                        "type": "Unknown (Disabled)",
                        "status": "disable",
                        "other_info": {
                            "author": "Unknown",
                            "introduction": "插件未加载，请启用并重启 Bot 以加载。",
                            "error_info": "",
                        },
                        "config": plugin_config,
                    }

        return plugins_info

    def update_plugin_status(self, plugin_name, new_status):
        config_path = os.path.join(self.bot.configs_path, "plugins.ini")
        config = configparser.ConfigParser()
        config.optionxform = str

        enable = "True" if new_status == "running" else "False"
        try:
            config.read(config_path, encoding="utf-8")
            if not config.has_section(plugin_name):
                config.add_section(plugin_name)

            config.set(plugin_name, "enable", enable)
            with open(config_path, "w", encoding="utf-8") as configfile:
                config.write(configfile)

            for plugin in self.bot.plugins_list:
                if plugin.name == plugin_name:
                    plugin.status = new_status
                    plugin.config["enable"] = new_status == "running"

            return True
        except Exception as e:
            print(f"Error updating plugin status: {e}")
            return False

    def save_config(self, config_data):
        plugin_name = config_data.get("plugin_name")
        if not plugin_name:
            return {"success": False, "message": "缺少插件名称"}

        try:
            plugins_config_path = os.path.join(self.bot.configs_path, "plugins.ini")
            groups_config_path = os.path.join(self.bot.configs_path, "groups.ini")

            p_config = configparser.ConfigParser()
            p_config.optionxform = str
            p_config.read(plugins_config_path, encoding="utf-8")

            if not p_config.has_section(plugin_name):
                p_config.add_section(plugin_name)

            g_config = configparser.ConfigParser()
            g_config.optionxform = str
            g_config.read(groups_config_path, encoding="utf-8")

            if "effected_group" in config_data:
                new_groups = set()
                raw_groups = config_data["effected_group"]

                if isinstance(raw_groups, list):
                    new_groups = set(map(str, raw_groups))
                elif isinstance(raw_groups, str):
                    if raw_groups.strip():
                        new_groups = set(x.strip() for x in raw_groups.split(",") if x.strip())

                for section in g_config.sections():
                    if g_config.has_option(section, plugin_name):
                        g_config.remove_option(section, plugin_name)
                        if not g_config.options(section):
                            g_config.remove_section(section)

                for group_id in new_groups:
                    if not g_config.has_section(group_id):
                        g_config.add_section(group_id)
                    g_config.set(group_id, plugin_name, "True")

            for key, value in config_data.items():
                if key in ["plugin_name", "effected_group"]:
                    continue
                if isinstance(value, list):
                    p_config.set(plugin_name, key, ",".join(map(str, value)))
                else:
                    p_config.set(plugin_name, key, str(value))

            with open(plugins_config_path, "w", encoding="utf-8") as f:
                p_config.write(f)

            with open(groups_config_path, "w", encoding="utf-8") as f:
                g_config.write(f)

            for plugin in self.bot.plugins_list:
                if plugin_name == plugin.name:
                    plugin.load_effected_groups()
                    status = "running" if plugin.config.getboolean("enable") else "disable"
                    plugin.set_status(status=status)
                    break

            return {"success": True}

        except Exception as e:
            return {"success": False, "message": f"后端执行操作时出错：{e}"}
