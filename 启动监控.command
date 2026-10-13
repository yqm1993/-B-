#!/bin/bash
# 本地运行 B站动态监控：每 10 分钟检查一次。关掉本窗口即停止。
cd "$(dirname "$0")"

# ======== 把下面两处改成你自己的 ========
export BARK_KEY="在这里填你的BarkKey"
export BILI_UID="470672214"
# 可选：住宅IP一般不用填；想更稳可填完整 Cookie（见 README「关于 BILI_COOKIE」）
export BILI_COOKIE=""
# =======================================

export BARK_SERVER="https://api.day.app"
export STATE_FILE="seen.json"

echo "开始监控 UID=$BILI_UID，每 10 分钟检查一次。按 Ctrl+C 或关闭窗口停止。"
while true; do
  echo "---- $(date '+%Y-%m-%d %H:%M:%S') 检查中 ----"
  python3 monitor.py
  sleep 600
done
