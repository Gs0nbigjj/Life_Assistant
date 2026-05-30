#!/bin/bash
# 讓腳本一出錯就停止執行
set -e

echo "🚀 [1/3] Running database migrations..."
alembic upgrade head

echo "📦 [2/3] Installing editable local package..."
python -m pip install -e .

echo "🤖 [3/3] Starting Discord Bot..."
# 使用 exec 讓 python 進程直接取代目前的 shell，奪回 PID 1 寶座！
exec python -m bot