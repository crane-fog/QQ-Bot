#!/bin/bash
# 对随 Bot 容器运行的面板执行宿主机维护命令（重置密码、登记保护配置等），无需宿主机 Python。
set -euo pipefail
DEPLOY_DIR="$(cd "$(dirname "$0")/.." && pwd -P)"
command -v docker >/dev/null || { echo "需要安装 Docker 和 Compose 插件" >&2; exit 1; }
docker compose version >/dev/null
docker compose --project-directory "$DEPLOY_DIR" -f "$DEPLOY_DIR/compose.yaml" \
    run --rm --no-deps --entrypoint python3 theresa -m src.deployment "$@"
