# Python QQ-Bot 框架

## 这是什么？

一款由 Python 编写的基于 onebot 协议的 qq 机器人后端框架，使用面向对象的思想实现了（自认为）便于插件管理和开发的框架环境

框架自带比较完善的运行日志输出系统，同时配备了由原作者编写的 web 控制面板方便远程管理 bot 的运行情况与监测运行日志

## 在开发插件之前，你需要做哪些准备？
本项目使用 uv 进行依赖管理

[uv安装文档](https://docs.astral.sh/uv/getting-started/installation/)

拉取项目代码及初始化
```bash
git clone https://github.com/crane-fog/QQ-Bot
cd QQ-Bot
uv sync
uv run pre-commit install
```

安装并正确配置运行 bot 的 qq 监听端（详见后文），建议使用 [LLBot](https://github.com/LLOneBot/LuckyLilliaBot)

启动 bot
```bash
uv run main.py
```

## 监听端配置教程
启用HTTP服务

设置“HTTP服务监听端口”，例：5700（对应 `bot.ini` 中的 server_address 端口）（端口可任意指定）

勾选“启用HTTP事件上报”

设置上报地址，例：http://127.0.0.1:5701/onebot （其端口对应 `bot.ini` 中的 client_address 端口）（端口可任意指定）

以CQ码格式接收消息

> 如果你想为 `./src/Api.py` 添加尚未实现在该项目中的 llbot api，请参考 [llbot api 文档](https://llonebot.apifox.cn/)

## 配置文件说明

### `configs/bot.ini` bot 基础信息配置

配置项 | 说明
------|----
server_address | 监听端的监听地址（即 bot 上报事件的地址）
client_address | 监听端的事件上报的地址（即 bot 接收事件的地址）
web_controller_address | bot web 控制面板的监听地址
bot_name | bot 的名字（目前似乎没有什么用）
debug | 是否开启日志调试模式（True/False）
database_enable | 是否启用数据库（True/False）（建议使用 PostgreSQL）
database_username | 数据库用户名
database_address | 数据库地址
database_passwd | 数据库密码
database_name | 数据库名
owner_id | 机器人所有者QQ号
assistant_group | 助教群号（用于部分插件）

### `configs/groups.ini` 群聊插件启用信息配置
```ini
[123456789]
PluginName1 = True
PluginName2 = True
```
决定了一个群聊（123456789）中启用哪些插件（PluginName1、PluginName2），未配置的插件默认不启用

### `configs/plugins.ini` 插件启用信息及部分特殊配置
```ini
[PluginName1]
enable = True

[PluginName2]
enable = False
some_special_config = 123
```
`enable` 决定插件是否启用，此处的启用优先级高于群聊配置，即，只要配置了 `enable = False`，该插件不会被加载，不会在任何群聊中生效

其余可包含插件需要读取的特殊配置项，建议将插件中需要可变的配置项写入此文件

---

TODO:

优化插件 log 使用

重写 EventController

配置文件读取优化

---

该项目曾为 [JustMon1ka/QQ-Bot-New](https://github.com/JustMon1ka/QQ-Bot-New) 的 Fork

[原作者提供的详细插件开发教程](https://github.com/JustMon1ka/QQ-Bot-New/wiki/%E4%BB%8E%E8%BF%99%E9%87%8C%E5%BC%80%E5%A7%8B%E7%AC%AC%E4%B8%80%E6%AC%A1%E5%BC%80%E5%8F%91%EF%BC%81)
