#!/bin/bash
# docker compose 入口脚本，请勿手动执行

set -e

echo "--------------------------------------------------------"
echo "检查数据库初始化..."

FLAG_FILE="/app/theresa/.dbinitialized"
DB_SCRIPT="/app/theresa/scripts/create_tables.py"

if [ ! -f "$FLAG_FILE" ]; then
  echo "首次启动，正在初始化数据表..."
  python3 "$DB_SCRIPT"
  touch "$FLAG_FILE"
  echo "数据库初始化完成"
else
  echo "非首次启动，跳过"
fi

echo "--------------------------------------------------------"
echo "检查 QQ 登录状态..."

ONEBOT_API_URL="http://llbot:5700/get_login_info"
LOGIN_SUCCESS=0

while [ $LOGIN_SUCCESS -eq 0 ]; do

  IS_OK=$(python3 -c "
import urllib.request, json
try:
    with urllib.request.urlopen('$ONEBOT_API_URL', timeout=2) as resp:
        if 'ok' in resp.read().decode():
            print('yes')
except Exception:
    pass
" 2>/dev/null)

  if [ "$IS_OK" = "yes" ]; then
    LOGIN_SUCCESS=1
  else
    echo "请扫码登录 QQ，或在浏览器中打开 http://localhost:3080"
    sleep 3
  fi
done

echo "QQ 登录成功！正在拉起 Theresa..."
echo "--------------------------------------------------------"

exec "$@"
