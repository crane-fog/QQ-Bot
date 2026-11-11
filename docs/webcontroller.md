# 部署面板（WebController）

面板不依赖 QQ 登录和数据库，并且始终是拉起 Bot 的一方：面板先启动、先可用，Bot 作为其子进程运行，崩溃后自动退避重启；面板自身异常只记录日志、不影响 Bot，停止信号由面板转发给 Bot。Docker 部署中容器主进程是根启动器 `main.py`，它拉起面板子进程，面板再经启动链（数据库初始化、等待 QQ 登录）拉起 Bot；源码部署中 `main.py` 同样作为根启动器拉起面板，面板守护 `bot.py`。只想启动 Bot 本身时直接运行 `bot.py`，面板不会介入。两种方式均提供 TOML 配置管理、校验、差异及备份恢复；Docker 部署另外提供 Compose 表单/YAML 编辑。面板不挂载 Docker socket，对 Docker daemon 零访问：不显示容器运行状态，也不执行任何容器操作。

## 纯源码部署（Windows / Linux）

需要 uv 和 Python 3.13 或以上版本，不需要 Docker、Compose、QQ 登录或数据库连接。在项目根目录执行：

```bash
uv sync --no-dev
uv run main.py
```

这一条命令会拉起面板（自动初始化）并由面板守护 Bot。只想运行 Bot 本身、不使用面板时执行 `uv run bot.py`。也可先执行 `uv run -m src.deployment --init` 只初始化不启动。

初始化自动生成随机管理员密码，写入 `.webcontroller/initial-password`（仅当前用户可读），终端只提示文件路径，不显示密码内容；首次成功登录后面板自动删除该文件，请尽快用 `--reset-password` 设置自己的密码。也可在 `--init` 或 `--reset-password` 时用 `--password` 非交互指定密码，此时不生成密码文件。密码长度不限制，仅以 scrypt 哈希存储，强度由使用者自行负责。初始化从 `configs/*.toml.template` 补齐五类缺失配置，不覆盖已有文件；重复执行保留密码。设置与密码哈希存放于 `.webcontroller/`，不写入 `.env`。

建议同一时间只保留一个面板实例；同一批配置被多处同时编辑时，由版本检查兜底。

默认监听 `127.0.0.1:7001`，可使用 `--port` 指定其他端口。可用 `--bg` 以后台进程运行，PID 与日志分别记录在 `.webcontroller/panel.pid`、`panel.log`，用 `--stop` 停止（面板与 Bot 一同停止）；长期运行仍建议使用下文的 systemd 服务，一个服务即可同时守护面板和 Bot。远程访问使用下文的 SSH 转发。

忘记密码时执行：

```bash
uv run -m src.deployment --reset-password
```

重启面板后使用新密码登录。Linux 状态目录与文件限制为当前用户访问；Windows 使用用户目录的 Windows ACL，请将项目放在可信用户目录内，不与不可信用户共享配置和备份。

Linux 可使用独立 systemd 服务保持面板运行，以下为参考（替换用户名、uv 路径和项目路径，使用 `command -v uv` 查找路径）：

```ini
[Unit]
Description=Theresa WebController
After=network.target

[Service]
User=your-user
WorkingDirectory=/home/your-user/QQ-Bot
ExecStart=/home/your-user/.local/bin/uv run --frozen --no-dev main.py
Restart=on-failure
UMask=0077

[Install]
WantedBy=multi-user.target
```

将服务保存为 `/etc/systemd/system/theresa-webcontroller.service` 后，由管理员执行 `sudo systemctl daemon-reload` 和 `sudo systemctl enable --now theresa-webcontroller`。Windows 可在独立终端运行或使用 `--bg`；本版不自动安装系统服务。

## Bot TOML 配置管理（两种部署共用）

源码部署下面板只有这一部分；Docker 部署下面板另有 Compose 部署页，通过页签切换到“Bot 配置”。只允许管理 `bot.toml`、`plugins.toml`、`groups.toml`、`ai.toml`、`scheduler.toml`，不能编辑任意宿主机文件。

Bot 基础配置提供表单，密码和令牌默认遮蔽；插件提供全局启用开关，群聊提供群配置增删与插件开关。复杂参数、AI 与定时任务使用完整 TOML。表单与文本共享草稿，保留注释和未知字段。缺失或语法错误的配置可以通过完整 TOML 修复；切换文件和重新读取前会提示未保存草稿。

校验覆盖 TOML 语法、Bot 必需字段及类型、地址端口、插件/群聊开关和基本配置表结构，不导入插件或测试外部连接，不保证所有插件自定义参数均有效。配置版本冲突会拒绝覆盖。保存和恢复前备份当前文件，并原子替换；备份按文件存于 `.webcontroller/config-backups/`，与 Compose 备份隔离。原文件无效时保存同样会先备份；恢复出的内容则必须通过校验。

**保存只写入磁盘。** 保存后点击工具栏的“重启 Bot”即可让子进程带着新配置立即重启（面板本身不重启，两种部署方式一致；Bot 崩溃循环中也可用，重启请求不受退避等待影响）。多个文件分别保存，不提供跨文件事务，也不会在保存时自动重启——何时应用由管理员决定。Compose 保存/恢复期间拒绝 TOML 保存/恢复；两侧的修改都不会自动触发容器操作。

完整 TOML、差异、下载及备份可能含密码或 API Key，仅向已登录管理员开放。修改监听端口需手动同步 LLBot；数据库配置修改不会修改现有数据库账号密码。

## Docker 部署（新装）

支持 Linux Docker Engine 和 WSL 内的 Linux Docker Engine。宿主机需要 Docker 与 Compose 插件，不需要 Python/uv。

执行发布包中的 `bash scripts/docker_compose_init.sh`，按提示从模板生成 `configs/*.toml` 并填写，然后执行：

```bash
docker compose up -d
```

容器主进程是根启动器 `main.py`：容器启动后它拉起面板子进程，面板再以子进程拉起原启动链（数据库初始化、等待 QQ 登录、`bot.py`）。部署目录以 `source: .` 挂载到容器内固定路径 `/deploy`，端口映射为 `127.0.0.1:7001:7001`。首次启动自动初始化，初始面板密码生成于宿主机的 `.webcontroller/initial-password`，首次成功登录后自动删除；与 LLBot WebUI 密码独立。Bot 崩溃后面板按 1 秒起步、指数延长至最长 10 分钟的退避自动重启（稳定运行 60 秒后重新从 1 秒开始）；等待 QQ 扫码期间面板照常可用。面板不使用 Docker socket，`compose.yaml` 无需为面板增加任何变量。

访问 `http://127.0.0.1:7001`。远程服务器使用 SSH 转发：

```bash
ssh -L 7001:127.0.0.1:7001 user@server
```

再打开本机的 `http://127.0.0.1:7001`。面板仅接受 localhost/回环地址的 Host，不支持公网反向代理或局域网直接访问。面板的 Compose 端口只绑定宿主机回环地址。

**面板对 Docker daemon 零访问。** 校验只执行 `docker compose config` 等客户端操作，不读取容器状态、不启停容器；容器更新和状态查询都在宿主机执行。仍不要将端口绑定到公网，面板没有公开注册入口。

## Docker 部署（补装面板）

不要重新执行 `docker_compose_init.sh`，它用于首次初始化。保留当前 `compose.yaml` 与配置，拉取新版镜像，并在 `theresa` 服务中加入面板所需的两项：`127.0.0.1:7001:7001` 端口映射和 `source: .` 到 `/deploy` 的挂载，然后执行：

```bash
docker compose up -d
```

面板首次启动时自动初始化，从 `compose.yaml`、`.env` 或目录名推断 Compose 项目名称；推断结果不符时在宿主机明确指定：

```bash
bash scripts/setup_webcontroller.sh --init --project-name existing-project
```

`scripts/setup_webcontroller.sh` 保留为宿主机维护入口（重置密码、登记保护配置等），内部通过 `docker compose run --entrypoint python3 theresa` 执行同一命令。密码哈希、会话密钥、受保护配置和备份保存在 `.webcontroller/`；文件权限为 0600、状态目录为 0700。这些文件不应提交到 Git 或打包进镜像。

面板把部署目录挂载到容器内 `/deploy`，并以该路径作为 `--project-directory`。移动部署目录后状态记录中的路径不再匹配，需删除 `.webcontroller/settings.json` 重新初始化（密码和备份保留）。容器内以 root 写入 `.webcontroller/` 后，这些文件在宿主机上归 root 所有；切换回源码运行面板前需先 `chown` 给启动用户，否则面板读取状态文件会因权限失败（Bot 不受影响，但面板不可用）。

## 编辑与保存

1. 在服务表单编辑镜像、重启策略、环境变量、端口、挂载、依赖与健康检查。结构字段接受 JSON 列表/对象；留空删除字段。点击“更新草稿”或切换到完整 YAML，同步到同一份草稿。
2. 完整 YAML 可以配置其他 Compose 字段和增加业务服务。面板管理单个 `compose.yaml`，不支持 `include`、`extends` 或多个文件叠加。
3. 展开“配置差异”面板会校验当前草稿并显示与磁盘文件的差异。校验把部署目录（容器内为 `/deploy`）作为 `--project-directory`、部署目录内的 `.env`（如存在）作为 `--env-file` 传给 Compose，先执行 `docker compose config --quiet`，再检查相对 bind 源：部署目录内的源必须已存在，防止误挂载空目录；绝对路径源无法在容器内验证，仅透传。
4. 点击“校验并保存”保存：校验通过后自动备份当前文件并原子替换。若文件已被其他操作修改，返回冲突并保留草稿，可下载草稿后重新读取比较。
5. 面板不执行任何容器操作。保存后需在宿主机执行 `docker compose up -d` 更新容器；变更端口、挂载或环境变量通常需要重建容器，仅 `restart` 不会应用这些变化。删除服务配置后，旧容器仍可能存在，需在宿主机确认后处理。

需要长期停用某个服务时，为它设置 profiles（服务表单或完整 YAML）；宿主机执行 `docker compose up -d` 时只会启动没有 profiles 的服务，不使用 `.env` 中的 `COMPOSE_PROFILES`。有 profile 的服务在宿主机显式启动。镜像按 Compose 默认策略拉取，不强制更新所有 latest 镜像；修改镜像版本可明确触发升级。

Compose、Bot TOML、LLBot JSON 暂不联动。修改监听端口后要同步检查相关文件；已有 PostgreSQL 数据卷时，修改 `POSTGRES_PASSWORD` 不会修改现有用户密码，需要另外执行数据库改密。

## 恢复与面板维护

页面中预览备份并确认恢复；恢复当前配置前也会自动备份。恢复只替换配置文件，不回滚数据库、卷数据或容器状态。

Compose 项目名称不能从网页修改。修改名称或面板启动项（端口映射、`/deploy` 挂载）时，在宿主机编辑 `compose.yaml` 后重新登记保护配置：

```bash
bash scripts/setup_webcontroller.sh --accept-panel-upgrade
docker compose up -d
```

忘记密码时：

```bash
bash scripts/setup_webcontroller.sh --reset-password
docker compose restart theresa
```

密码文件只在面板启动时读取一次，重置后必须重启容器，新密码才生效（“重启 Bot”按钮只重启 Bot 子进程，不起作用）。

会话 8 小时后过期，面板重启使旧会话失效；失败登录超过每分钟 5 次会暂时限速。重置密码不会在终端输出新密码。校验命令的报错输出会过滤 Compose 环境变量和 `.env` 中的值；完整 YAML、差异、下载与备份仍可能包含明文密码，仅对登录管理员开放。

## 本地构建与验证

首次发布前，或暂不使用已发布镜像时，在 Linux/WSL 构建 Bot 镜像（面板代码与 Docker CLI 已包含在内，无独立面板镜像）：

```bash
docker build -t heai/theresa:latest .
docker compose up -d
```

镜像内置 Docker CLI 与 Compose 插件，仅用于客户端校验，容器不挂载 Docker socket。镜像版本变更直接修改 `compose.yaml` 中 theresa 服务的 `image` 字段。

如果构建机器依赖 HTTP 代理，镜像拉取走 Docker 服务的代理；BuildKit 的认证请求也可能由 Docker CLI 进程发起，需要同时给构建进程设置代理。构建阶段的 `uv sync` 则使用 build args。例如（将地址替换为构建机器可达的代理）：

```bash
BUILD_PROXY=http://192.168.134.1:10809
sudo env HTTP_PROXY="$BUILD_PROXY" HTTPS_PROXY="$BUILD_PROXY" \
  docker build \
  --build-arg HTTP_PROXY="$BUILD_PROXY" \
  --build-arg HTTPS_PROXY="$BUILD_PROXY" \
  -t heai/theresa:latest .
```

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run --extra Schedule playwright install chromium
RUN_WEB_BROWSER_TESTS=1 uv run --extra Schedule pytest tests/test_deployment_browser.py
RUN_WEB_DOCKER_TESTS=1 uv run pytest tests/test_deployment_docker.py
```

浏览器测试使用临时配置和进程内的校验替身（FakeRunner），不访问 Docker；Docker 集成测试在宿主机上使用随机命名的隔离项目、Alpine 容器和临时挂载，结束后仅清理该测试项目及其卷。

如果测试进程本身也在 Linux 容器中运行，需要挂载 Docker socket、将测试目录以相同绝对路径挂载，并使用 `--network host`。

更早版本的验证记录（2026-10-06 前后）针对含一键应用、容器状态与 Docker socket 的设计，相关结论不再逐条适用。当前版本（main.py 根启动器拉起面板、面板守护 Bot、无独立面板镜像、模块路径 src.deployment）在 Windows 运行全量测试：223 项通过、3 项跳过，其中 2 项 Chromium 浏览器测试已单独启用并通过，1 项 Linux Docker 集成测试因本机缺少 Docker Engine 跳过；theresa 容器内部署流程（面板拉起启动链、自动初始化、登录、保存）需在 Linux/WSL 验证。

实现依据：[Compose config](https://docs.docker.com/reference/cli/docker/compose/config/)、[Profiles](https://docs.docker.com/compose/how-tos/profiles/)、[项目名称](https://docs.docker.com/compose/how-tos/project-name/)。
