#!/bin/bash
# docker compose 所需配置的初始化脚本

set -e
cd "$(dirname "$0")"

LLBOT_DIR="../llbot_config"
COMPOSE_FILE="../compose.yaml"

if [ -d "$LLBOT_DIR" ]; then
    echo "llbot 配置目录已存在，如需重新初始化，请先删除 $LLBOT_DIR 目录"
    exit 1
fi

if [ ! -f "$COMPOSE_FILE" ]; then
    echo "未找到 docker compose 配置文件 $COMPOSE_FILE"
    exit 1
fi

while true; do
    read -e -r -p "请输入 QQ 号: " qq_number
    if [ -n "$qq_number" ]; then
        break
    fi
done

while true; do
    read -e -r -p "请输入 WebUI 密码: " webui_password
    if [ -n "$webui_password" ]; then
        break
    fi
done

while true; do
    read -e -r -p "请输入数据库密码: " db_password
    if [ -n "$db_password" ]; then
        break
    fi
done

escape_for_sed() {
    printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | sed -e 's/\\/\\\\/g' -e 's/&/\\&/g' -e 's/|/\\|/g'
}

sedi() {
    if [ "$(uname)" = "Darwin" ]; then
        sed -i '' "$@"
    else
        sed -i "$@"
    fi
}

escaped_db_pass=$(escape_for_sed "$db_password")

mkdir -p "$LLBOT_DIR"

cat << 'EOF' > "${LLBOT_DIR}/config_${qq_number}.json"
{
  "milky": {
    "enable": false,
    "reportSelfMessage": false,
    "http": {
      "host": "",
      "port": 3000,
      "prefix": "/milky",
      "accessToken": ""
    },
    "webhook": {
      "urls": [],
      "accessToken": ""
    }
  },
  "satori": {
    "enable": false,
    "host": "",
    "port": 5500,
    "token": ""
  },
  "ob11": {
    "enable": true,
    "connect": [{"type":"http","enable":true,"host":"","port":5700,"token":"","reportSelfMessage":false,"reportOfflineMessage":false,"messageFormat":"string","debug":false},{"type":"http-post","enable":true,"url":"http://theresa:5701/onebot","token":"","reportSelfMessage":true,"reportOfflineMessage":false,"messageFormat":"string","debug":false,"enableHeart":false,"heartInterval":30000}]
  },
  "webui": {
    "enable": true,
    "host": "",
    "port": 3080
  }
}
EOF

printf "%s" "$webui_password" > "${LLBOT_DIR}/webui_token.txt"

echo "llbot 配置已生成"

sedi -E "s/(AUTO_LOGIN_QQ=).*/\1${qq_number}/" "$COMPOSE_FILE"
sedi -E "s|(POSTGRES_PASSWORD: ).*|\1\"${escaped_db_pass}\"|" "$COMPOSE_FILE"

echo "compose.yaml 已更新"

THERESA_DIR="../configs"

for tpl in "$THERESA_DIR"/*.template; do
    [ -f "$tpl" ] || continue

    target="${tpl%.template}"
    if [ ! -e "$target" ]; then
        echo "配置文件 $target 不存在，从模板复制"
        cp "$tpl" "$target"
        if [ "$(basename "$target")" = "bot.toml" ]; then
            sedi -E 's/(server_address = ).*/\1"llbot:5700"/' "$target"
            sedi -E 's/(client_address = ).*/\1"0.0.0.0:5701"/' "$target"
            sedi -E "s/(database_address = ).*/\1\"db:5432\"/" "$target"
            sedi -E "s|(database_passwd = ).*|\1\"${escaped_db_pass}\"|" "$target"
        fi
    fi
done

echo "--------------------------------------------------------"
echo "请在手动填写 bot 相关配置文件后执行"
echo "docker compose up"
