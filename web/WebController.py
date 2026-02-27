import configparser
import logging
import os

import requests
from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
)
from gevent.pywsgi import WSGIServer

total_lines_read = 0
last_cleared_line = 0


def create_web_app(web_controller):
    basedir = os.path.abspath(os.path.dirname(__file__))
    # 设置模板文件夹路径
    template_dir = os.path.join(basedir, "templates")
    # 静态文件目录路径
    static_dir = os.path.join(basedir, "static")

    app = Flask("Web Controller", template_folder=template_dir, static_folder=static_dir)
    app.secret_key = "just monika"

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/baseInfo.html")
    def base_info():
        bot_info = WebController.get_bot_info(web_controller)
        plugins_info = WebController.get_plugins_init_info(web_controller)

        return render_template("baseInfo.html", bot_info=bot_info, plugins_info=plugins_info)

    @app.route("/log.html")
    def log():
        return render_template("log.html")

    @app.route("/leave-log.html")
    def leave_log():
        global total_lines_read, last_cleared_line
        total_lines_read = last_cleared_line
        return jsonify(success=True)

    @app.route("/plugins.html")
    def plugins():
        plugins_info = WebController.get_all_plugins_info(
            web_controller
        )  # 假设这是从数据库获取信息的函数
        return render_template("plugins.html", plugins=plugins_info)

    @app.route("/log.out")
    def log_file():
        global total_lines_read, last_cleared_line

        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_file_path = os.path.join(parent_dir, "log.out")

        lines_to_send = []
        with open(log_file_path, encoding="utf-8") as file:  # 以读模式打开文件
            all_lines = file.readlines()
            lines_to_send = all_lines[total_lines_read:]  # 提取新的日志行
            total_lines_read = len(all_lines)  # 更新读取的总行数

        # 处理错误标记并准备写回文件
        new_lines = [
            line.replace("[ERROR]", "[error]") if "[ERROR]" in line else line for line in all_lines
        ]

        # 将更新后的内容写回文件
        with open(log_file_path, "w", encoding="utf-8") as file:
            file.writelines(new_lines)

        return Response("".join(lines_to_send), mimetype="text/plain")

    @app.route("/clear-log", methods=["POST"])
    def clear_log():
        global total_lines_read, last_cleared_line
        last_cleared_line = total_lines_read
        return jsonify(success=True)

    @app.route("/save_config", methods=["POST"])
    def save_config():
        config_data = request.json
        print(config_data)

        result = WebController.save_config(web_controller, config_data)

        return jsonify(result)

    app.logger.setLevel(logging.ERROR)
    return app


class WebController:
    flask_log = logging.getLogger("werkzeug")
    flask_log.setLevel(logging.ERROR)

    def __init__(self, bot):
        self.bot = bot
        self.api = bot.api

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
            # print(plugins_status)
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

    # 创建一个不记录任何内容的日志器
    class SilentLogger:
        def write(self, *args, **kwargs):
            pass

        def flush(self, *args, **kwargs):
            pass

    def run(self, ip, port):
        app = create_web_app(self)
        server = WSGIServer((ip, port), app, log=self.SilentLogger())
        # server = WSGIServer((ip, port), app)
        server.serve_forever()

    def get_all_plugins_info(self):
        plugins_info = {}
        loaded_plugin_names = set()

        # 1. 获取已加载插件的信息
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

        # 2. 扫描未加载的插件 (从 plugins.ini 和 文件夹)

        plugins_config_path = os.path.join(bot.configs_path, "plugins.ini")
        groups_config_path = os.path.join(bot.configs_path, "groups.ini")

        config = configparser.ConfigParser()
        config.optionxform = str
        if os.path.exists(plugins_config_path):
            config.read(plugins_config_path, encoding="utf-8")

        g_config = configparser.ConfigParser()
        g_config.optionxform = str
        if os.path.exists(groups_config_path):
            g_config.read(groups_config_path, encoding="utf-8")

        for item in os.listdir(bot.plugins_path):
            plugin_dir = os.path.join(bot.plugins_path, item)
            if os.path.isdir(plugin_dir) and not item.startswith("__"):
                if item not in loaded_plugin_names:
                    # 这是一个未加载的插件
                    plugin_config = {}
                    if config.has_section(item):
                        for k, v in config.items(item):
                            # 简单的类型转换，为了前端显示
                            if v.lower() in ("true", "false"):
                                plugin_config[k] = v.lower() == "true"
                            elif "," in v:
                                try:
                                    plugin_config[k] = [int(x) for x in v.split(",")]
                                except Exception:
                                    plugin_config[k] = v.split(",")
                            else:
                                plugin_config[k] = v

                    # 确保有 enable 字段
                    if "enable" not in plugin_config:
                        plugin_config["enable"] = False

                    # 构建 effected_group
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
        # 此方法似乎未被前端直接调用，或者逻辑需要更新
        # 暂时保留，但指向 plugins.ini
        from plugins import plugins_path

        config_path = os.path.join(plugins_path, "plugins.ini")
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
            from plugins import plugins_path

            plugins_config_path = os.path.join(plugins_path, "plugins.ini")
            groups_config_path = os.path.join(plugins_path, "groups.ini")

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

            # 更新配置文件中的值
            for key, value in config_data.items():
                if key in ["plugin_name", "effected_group"]:
                    continue
                if isinstance(value, list):
                    p_config.set(plugin_name, key, ",".join(map(str, value)))
                else:
                    p_config.set(plugin_name, key, str(value))

            # 保存配置文件
            with open(plugins_config_path, "w", encoding="utf-8") as f:
                p_config.write(f)

            with open(groups_config_path, "w", encoding="utf-8") as f:
                g_config.write(f)

            # 如果插件已加载，更新内存中的配置和状态
            for plugin in self.bot.plugins_list:
                if plugin_name == plugin.name:
                    plugin.load_effected_groups()
                    status = "running" if plugin.config.get("enable") else "disable"
                    plugin.set_status(status=status)
                    break

            return {"success": True}

        except Exception as e:
            return {"success": False, "message": f"后端执行操作时出错：{e}"}


if __name__ == "__main__":
    bot = None  # 创建或获取你的bot对象
    web_controller = WebController(bot)
    web_controller.run("127.0.0.1", 3000)
