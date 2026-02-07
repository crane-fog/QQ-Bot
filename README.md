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

安装并正确配置运行 bot 的 qq 监听端，建议使用 [LLOneBot](https://github.com/LLOneBot/LuckyLilliaBot)（详见后文）

启动 bot
```bash
uv run main.py
```

## 监听端配置教程
启用HTTP服务

设置“HTTP服务监听端口”，例：5700（对应 `BotConfig.ini` 中的 server_address 端口）（端口可任意指定）

勾选“启用HTTP事件上报”

设置上报地址，例：http://127.0.0.1:5701/onebot （其端口对应 `BotConfig.ini` 中的 client_address 端口）（端口可任意指定）

以CQ码格式接收消息

（todo）

---

三份配置文件：

`./BotConfig.ini` bot 基础信息配置

`./Plugins/groups.ini` 群聊插件启用信息配置

`./Plugins/plugins.ini` 插件启用信息及部分特殊配置

（todo）

---

该项目曾为 [JustMon1ka/QQ-Bot-New](https://github.com/JustMon1ka/QQ-Bot-New) 的 Fork

[原作者提供的详细插件开发教程](https://github.com/JustMon1ka/QQ-Bot-New/wiki/%E4%BB%8E%E8%BF%99%E9%87%8C%E5%BC%80%E5%A7%8B%E7%AC%AC%E4%B8%80%E6%AC%A1%E5%BC%80%E5%8F%91%EF%BC%81)
