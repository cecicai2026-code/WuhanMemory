#!/usr/bin/env bash
# 更新服务器上的网站：拉最新的 main、装依赖、跑后端测试、构建前端、重启两个服务。
# 在服务器上用 wuhan 用户运行：bash /opt/wuhanmemory/infra/deploy/update.sh
# 重启服务那一步要 sudo，会问一次密码。见 docs/operations/deploy-hk.md。
set -euo pipefail

APP=/opt/wuhanmemory
cd "$APP"
# corepack 第一次用 pnpm 时会问要不要下载，脚本里不问
export COREPACK_ENABLE_DOWNLOAD_PROMPT=0

echo "== 1/5 拉最新的 main"
git fetch origin
git checkout main
git pull --ff-only origin main

echo "== 2/5 装前端依赖"
corepack pnpm install --frozen-lockfile

echo "== 3/5 装后端依赖并跑后端测试（不调用真实接口）"
apps/api/.venv/bin/pip install --quiet -e "./apps/api[dev]"
(cd apps/api && .venv/bin/python -m pytest -q)

echo "== 4/5 构建前端"
corepack pnpm build

echo "== 5/5 重启服务"
sudo systemctl restart wuhanmemory-api wuhanmemory-web
sleep 3
systemctl --no-pager --lines=0 status wuhanmemory-api wuhanmemory-web
echo "完成。用浏览器打开网站看一眼。"
