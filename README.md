# Python QQ-Bot框架

## 这是什么？

一款由 Python 编写的基于 onebot 协议的 qq 机器人框架，使用面向对象的思想实现了（自认为）便于插件管理和开发的框架环境
 
框架自带比较完善的运行日志输出系统，同时配备了由原作者编写的 web 控制面板方便远程管理 bot 的运行情况与监测运行日志

## 在开发插件之前，你需要做哪些准备？
本项目使用 uv 进行依赖管理

[uv安装文档](https://docs.astral.sh/uv/getting-started/installation/)

```bash
git clone https://github.com/crane-fog/QQ-Bot-New
cd QQ-Bot-New
uv sync
```

执行以下命令启动 bot：
```bash
uv run main.py
```
  
## 项目推荐使用的bot监听端框架
[LLOneBot](https://github.com/LLOneBot/LuckyLilliaBot)

## [点击这里跳转到原作者提供的详细插件开发教程](https://github.com/JustMon1ka/QQ-Bot-New/wiki/%E4%BB%8E%E8%BF%99%E9%87%8C%E5%BC%80%E5%A7%8B%E7%AC%AC%E4%B8%80%E6%AC%A1%E5%BC%80%E5%8F%91%EF%BC%81)
