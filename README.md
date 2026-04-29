# Python QQ-Bot 框架

## 这是什么？

一款由 Python 编写的基于 onebot 协议的 qq 机器人后端框架，使用面向对象的思想实现了便于插件管理和开发的框架环境，部分插件主要用于高级语言程序设计课程群聊管理

## 启动准备
### 代码及依赖
- 本项目使用 uv 进行依赖管理 [uv安装文档](https://docs.astral.sh/uv/getting-started/installation/)
- 拉取项目代码及初始化

  对于使用：

  ```bash
  git clone https://github.com/crane-fog/QQ-Bot
  cd QQ-Bot
  uv sync --no-dev
  ```

  对于开发：

  ```bash
  git clone https://github.com/crane-fog/QQ-Bot
  cd QQ-Bot
  uv sync
  uv run pre-commit install
  ```

### 使用 LLBot 作为监听端

#### 安装 LLBot

参考 [LLBot 安装文档](https://luckylillia.com/guide/choice_install)

建议编写 systemd 服务脚本管理 LLBot 进程，保持其后台常驻运行

#### 在 WebUI 中进入 OneBot 11 选项页面进行配置

一般安装完后 WebUI 为 `http://localhost:3080`，仅限本机访问，对于远程开发环境，建议在本地使用 ssh 端口转发

```bash
ssh -L 3080:localhost:3080 user@remote_host
```

- 事件接收
  - 点击“HTTP服务”
  - 启用“启用此适配器”，监听地址/端口对应 `bot.ini` 中的 server_address
  - 消息格式选择“CQ码”
  - 保存

- 事件上报
  - 点击“HTTP上报”
  - 启用“启用此适配器”，监听地址/端口对应 `bot.ini` 中的 client_address
  - 消息格式选择“CQ码”
  - 保存

### 配置 configs/*.ini

```bash
cp configs/bot.ini.template configs/bot.ini
cp configs/groups.ini.template configs/groups.ini
cp configs/plugins.ini.template configs/plugins.ini
```

> 对于 `configs` 文件夹下的每个配置文件，需要复制一份去掉 `.template` 后缀的文件，并根据需要修改配置项，bot 启动时如无法找到配置文件会自动复制模板文件

#### `configs/bot.ini` bot 基础信息配置

配置项 | 说明
------|----
server_address | 监听端的监听地址（即 bot 上报事件的地址）
client_address | 监听端的事件上报的地址（即 bot 接收事件的地址）
web_controller_address | bot web 控制面板的监听地址，目前弃用
bot_name | bot 的名字（目前似乎没有什么用）
debug | 是否开启日志调试模式（True/False）
database_enable | 是否启用数据库（True/False）（建议使用 PostgreSQL）
database_username | 数据库用户名
database_address | 数据库地址
database_passwd | 数据库密码
database_name | 数据库名
owner_id | 机器人所有者QQ号
assistant_group | 助教群号（用于部分插件）
enable_webhook_handler | 是否启用 Webhook Handler 服务（True/False），用于高程 Gitea 处理
webhook_handler_address | Webhook Handler 服务监听地址
webhook_response_group | Webhook Handler 发送消息的群号


#### `configs/groups.ini` 群聊插件启用信息配置
```ini
[123456789]
PluginName1 = True
PluginName2 = True

[987654321]
PluginName1 = True
PluginName3 = True
```
决定了一个群聊（123456789）中启用哪些插件（PluginName1、PluginName2），未配置的插件默认不启用

#### `configs/plugins.ini` 插件启用信息及部分特殊配置
```ini
[PluginName1]
enable = True

[PluginName2]
enable = False
some_special_config = 123
```
`enable` 决定插件是否启用，此处的启用优先级高于群聊配置，即，只要配置了 `enable = False`，该插件不会被加载，不会在任何群聊中生效

其余可包含插件需要读取的特殊配置项，建议将插件中需要可变的配置项写入此文件

### 启动 bot

```bash
uv run python main.py
```

> 与 LLBot 类似，长期运行建议编写 systemd 服务脚本

> 如果你想为 `src/Api.py` 添加尚未实现在该项目中的 LLBot api，请参考 [LLBot api 文档](https://llonebot.apifox.cn/)

## 开发提交

PR 提交 dev 分支，一次提交尽量只包含一个功能点或修复一个 bug

## 插件文档

[插件文档](docs/plugins.md)

## 项目开发路线图

[ROADMAP.md](ROADMAP.md)

---

该项目曾为 [JustMon1ka/QQ-Bot-New](https://github.com/JustMon1ka/QQ-Bot-New) 的 Fork

[原作者提供的详细插件开发教程](https://github.com/JustMon1ka/QQ-Bot-New/wiki/%E4%BB%8E%E8%BF%99%E9%87%8C%E5%BC%80%E5%A7%8B%E7%AC%AC%E4%B8%80%E6%AC%A1%E5%BC%80%E5%8F%91%EF%BC%81)
