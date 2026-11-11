# Python QQ-Bot 框架

## 这是什么？

一款由 Python 编写的基于 onebot 协议的 qq 机器人后端框架，使用面向对象的思想实现了便于插件管理和开发的框架环境，部分插件主要用于高级语言程序设计课程群聊管理

## 部署指南

- [方式一：手动源码部署](#方式一手动源码部署)

- [方式二：Docker compose 部署](#方式二docker-compose-部署)

- [配置文件解释](#配置文件解释)

### 方式一：手动源码部署

#### 1. 代码及依赖

**本项目使用 uv 进行依赖管理，需要先安装 uv**

[uv安装文档](https://docs.astral.sh/uv/getting-started/installation/)

**拉取项目代码及初始化**

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

> 如需启用 Schedule 插件（依赖 playwright），需额外安装可选依赖，在 `uv sync` 语句中添加 `--extra Schedule`，并执行 `playwright install`

#### 2. 使用 LLBot 作为监听端

**安装 LLBot**

参考 [LLBot 安装文档](https://luckylillia.com/guide/choice_install)

建议编写 systemd 服务脚本管理 LLBot 进程，保持其后台常驻运行

**在 WebUI 中进入 OneBot 11 选项页面进行配置**

一般安装完后 WebUI 为 `http://localhost:3080`，仅限本机访问，对于远程开发环境，建议在本地使用 ssh 端口转发

```bash
ssh -L 3080:localhost:3080 user@remote_host
```

- 事件接收
    - 点击“HTTP服务”
    - 启用“启用此适配器”，监听地址/端口对应 `bot.toml` 中的 server_address
    - 消息格式选择“CQ码”
    - 保存

- 事件上报
    - 点击“HTTP上报”
    - 启用“启用此适配器”，监听地址/端口对应 `bot.toml` 中的 client_address
    - 消息格式选择“CQ码”
    - 保存

#### 3. 启动面板和 Bot

完成 `uv sync --no-dev` 后，用原启动命令运行：

```bash
uv run main.py
```

`main.py` 会拉起部署面板子进程；面板从 `configs/*.toml.template` 自动生成缺失的配置文件，随后拉起并守护 Bot。初始管理员密码生成于 `.webcontroller/initial-password`，首次成功登录后自动删除。

浏览器打开 `http://127.0.0.1:7001`，在“Bot 配置”中按 [配置文件解释](#配置文件解释) 修改必要配置项并保存。对于远程开发环境，建议在本地使用 ssh 端口转发。

修改配置并保存后，点击面板上的“重启 Bot”即应用新配置；`--bg` 可后台运行。只想直接运行 Bot 本身（不使用面板）可执行 `uv run bot.py`。更多说明见 [WebController 文档](docs/webcontroller.md)。

#### 4. 初始化数据库（可选）

尽管 bot 本身并不强制要求使用数据库，但大部分主要插件都需要数据库支持

建表脚本从 `configs/bot.toml` 读取连接信息，因此在面板生成配置并填好数据库连接后执行（若 `database_enable = true`）：

```bash
uv run scripts/create_tables.py
```

执行完成后在面板点击“重启 Bot”，Bot 即以新配置连接数据库。

> 如果你想为 `src/Api.py` 添加尚未实现在该项目中的 LLBot api，请参考 [LLBot api 文档](https://llonebot.apifox.cn/)

### 方式二：Docker compose 部署

> 对于 Windows 用户，下面的脚本需在已安装 Docker Engine 的 WSL 中执行。

从 [Github Releases](https://github.com/crane-fog/QQ-Bot/releases/latest) 下载最新 `Theresa-<version>-Docker.tar.gz`，解压、进入目录、执行脚本

```bash
tar -xzvf Theresa-<version>-Docker.tar.gz -C /your/desired/path
cd /your/desired/path
bash scripts/docker_compose_init.sh
```

按提示操作，脚本生成 `configs/*.toml` 配置文件后，请做必要的修改

首次启动只需关注 `configs/bot.toml` 中的部分配置项，详见 [配置文件解释](#配置文件解释)

> 如使用 Gitea Webhook 功能，或因其他原因需要 bot 监听外部端口，请手动修改 `compose.yaml` 中 services - theresa 一节，添加类似下文的端口映射
>
> ```yaml
> ports:
>     - "3000:3000"
> ```

执行 `docker compose up -d`。面板作为 theresa 容器的主进程自动启动并拉起 Bot，浏览器打开 `http://127.0.0.1:7001` 即可使用（初始管理员密码生成于 `.webcontroller/initial-password`，首次登录后自动删除），等待 QQ 登录期间面板照常可用。

容器启动后执行 `docker compose logs`，日志中将显示 QQ 登录二维码（也可直接在浏览器打开 `http://localhost:3080` 登录 llbot WebUI 后查看），手机扫码登录，务必勾选“下次登录无需手机确认”

> 宿主机 `configs/` 目录（以及 `llbot_config/` 目录）会被挂载到容器中。修改配置后，在面板上点击“重启 Bot”即可生效（也可在宿主机执行 `docker compose restart theresa`）



### 配置文件解释

#### 1. `configs/bot.toml` bot 基础信息及 Gitea Webhook 配置

> 首次启动只需关注该配置文件

对于标注 + 的配置项，请勿在 Docker compose 部署时手动修改（无论直接编辑文件还是通过面板）：初始化脚本已把它们改写为容器网络的专用值（`server_address` 指向 `llbot`、`database_address` 指向 `db`、`database_passwd` 与 `db` 服务的 `POSTGRES_PASSWORD` 成套）；模板默认的 `127.0.0.1` 在容器内指向容器自身，手动改回会直接断连

请特别关注标注 \* 的配置项

| 配置项                 | 说明                                                             |
| ---------------------- | ---------------------------------------------------------------- |
| server_address         | +\* 监听端的监听地址（即 bot 上报事件的目标地址）                |
| client_address         | +\* 监听端的事件上报的地址（即 bot 接收事件的监听地址）          |
| bot_name               | 目前无实际用途，bot 的名字                                       |
| debug                  | 是否开启日志调试模式（true/false）                               |
| database_enable        | +\* 是否启用 PostgreSQL 数据库（true/false）                     |
| database_username      | +\* 数据库用户名                                                 |
| database_address       | +\* 数据库地址                                                   |
| database_passwd        | +\* 数据库密码                                                   |
| database_name          | +\* 数据库名                                                     |
| owner_id               | \* 机器人所有者QQ号                                              |
| assistant_group        | 助教群号（用于部分插件）                                         |
| enable_webhook_handler | 是否启用 Webhook Handler 服务（true/false），用于高程 Gitea 处理 |

当启用了 `enable_webhook_handler` 后，需要在 `[Gitea]` 节中配置以下项：

| 配置项                    | 说明                                                                                                    | 必填 |
| ------------------------- | ------------------------------------------------------------------------------------------------------- | ---- |
| `webhook_handler_address` | Webhook Handler 服务监听地址                                                                            | 是   |
| `webhook_response_group`  | Webhook Handler 发送消息的群号                                                                          | 是   |
| `api_url`                 | Gitea 对 Bot 可访问的基础地址；若部署在子路径，必须包含该子路径（如 `https://gitea.example.com/tjhlp`） | 是   |
| `api_token`               | Gitea 个人访问令牌                                                                                      | 是   |

详细说明见 **[Gitea Webhook 文档](docs/gitea-webhook.md)**

#### 2. `configs/groups.toml` 群聊插件启用信息配置

```toml
[123456789]
PluginName1 = true
PluginName2 = true

[987654321]
PluginName1 = true
PluginName3 = true
```

决定了一个群聊（123456789）中启用哪些插件（PluginName1、PluginName2），未配置的插件默认不启用

#### 3. `configs/plugins.toml` 插件启用信息及部分特殊配置

```toml
[PluginName1]
enable = true

[PluginName2]
enable = false
some_special_config = 123
```

`enable` 决定插件是否启用，此处的启用优先级高于群聊配置，即，只要配置了 `enable = false`，该插件不会被加载，不会在任何群聊中生效

其余可包含插件需要读取的特殊配置项，建议将插件中需要可变的配置项写入此文件

#### 4. `configs/ai.toml` AI 服务配置

供 AI 相关插件（TheresaChat、TheresaAI、GroupSum 等）使用，分为三部分：

- `[provider.*]`：模型服务商配置
- `[profile.*]`：模型配置，指定 provider、model 及可选参数，插件按名称引用
- `[tool.*]`：AI 可调用的工具定义，供 profile 中的 `tools` 列表引用

\*若需使用相关插件，务必填写 api_key

模板包含完整示例，一般只需按需增改 provider 及填入 api_key

#### 5. `configs/scheduler.toml` 定时任务配置

键名对应 `scheduled_tasks` 目录下的文件名，`enable` 决定是否启用该定时任务，`kwargs` 为注册任务时传递给 main 函数的参数

## 开发提交

PR 提交 dev 分支，一次提交尽量只包含一个功能点或修复一个 bug

## 插件文档

[插件文档](docs/plugins.md)

## 项目开发路线图

[ROADMAP.md](ROADMAP.md)

---

该项目曾为 [JustMon1ka/QQ-Bot-New](https://github.com/JustMon1ka/QQ-Bot-New) 的 Fork

[原作者提供的详细插件开发教程](https://github.com/JustMon1ka/QQ-Bot-New/wiki/%E4%BB%8E%E8%BF%99%E9%87%8C%E5%BC%80%E5%A7%8B%E7%AC%AC%E4%B8%80%E6%AC%A1%E5%BC%80%E5%8F%91%EF%BC%81)
