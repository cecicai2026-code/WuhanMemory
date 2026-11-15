# 部署到香港轻量服务器（一步一步）

写于 2026-11-15。Cecilia 选了香港轻量服务器（`hosting-options.md` 的 D），部署的五个选择都按推荐：2G 内存以上的 Ubuntu 24.04、买域名、用只读部署密钥从 GitHub 拉代码、Caddy 负责 HTTPS 和转发、前后端各做成一个系统服务。

配置文件都在 [`infra/deploy/`](../../infra/deploy/)：`Caddyfile`、`wuhanmemory-api.service`、`wuhanmemory-web.service`、`update.sh`。

**两条安全规则**：key 和口令只出现在服务器的 `.env` 文件里，不要贴到任何聊天（包括和 Claude 的对话）、截图或文档里。下面凡是要你填 key 的地方，都是你在自己的终端里填。

## 网站在服务器上是什么样子

```text
访客浏览器 ──HTTPS──> Caddy（80、443 端口，自动证书）
                        ├─ /api/*、/_AMapService/*、/media/* ──> 后端 FastAPI  127.0.0.1:8000
                        └─ 其余 ─────────────────────────────> 前端 Next.js   127.0.0.1:3000
                                                                 └─ 服务器端取数据也直接连 127.0.0.1:8000
后端：SQLite 数据库 apps/api/wuhanmemory.db；调用千问、豆包、高德。公开模式打开。
```

服务器上的数据库是新的：景点资料启动时从 `data/pois/` 导入；我的行程是空的，上线后在网站上重新排几份、生成分享链接。占位照片不在 git 里，服务器上没有，公开模式下也不显示。

## 0. 准备（在你的 Mac 上）

- `deploy-hk` 分支合进 main，并在 GitHub Desktop 推送 main。服务器拉的是 GitHub 上的 main。
- 想好一个 OWNER_PASSCODE：一串不好猜、不和别的密码相同的字。

## 1. 买服务器（你在云服务商的网页上操作）

1. 阿里云或腾讯云的**轻量应用服务器**，地域选**香港**，系统镜像选 **Ubuntu 24.04**，配置**内存 2G 以上**（构建网站时 1G 以下不够）。价格以官网为准。
2. 登录方式选 **SSH 密钥**，下载私钥文件保存好（例如放到 Mac 的 `~/.ssh/wuhan-hk.pem`）。
3. 在控制台的**防火墙**里放行 **80** 和 **443**（22 一般默认已开）。其他端口都不要开。
4. 记下服务器的**公网 IP**，下面写成 `服务器IP`。

## 2. 买域名并解析（网页上操作）

1. 买一个域名（国内平台要实名认证；服务器在香港，不用做 ICP 备案）。
2. 在域名的 DNS 设置里加一条 **A 记录**：主机记录可以用 `@`（整个域名）或一个子域名如 `wuhan`，记录值填 `服务器IP`。下面把网站地址写成 `你的域名`。
3. 等几分钟，在 Mac 终端运行 `ping 你的域名`，看到的 IP 是服务器 IP 就好了。

## 3. 第一次登录，建一个专用用户（在 Mac 终端）

```bash
chmod 600 ~/.ssh/wuhan-hk.pem
```

```bash
ssh -i ~/.ssh/wuhan-hk.pem 默认用户@服务器IP
```

默认用户以控制台显示的为准（常见的是 `root` 或 `ubuntu`）。登录后，在服务器上：

```bash
sudo adduser wuhan
```

```bash
sudo usermod -aG sudo wuhan
```

```bash
sudo mkdir -p /home/wuhan/.ssh && sudo cp ~/.ssh/authorized_keys /home/wuhan/.ssh/ && sudo chown -R wuhan:wuhan /home/wuhan/.ssh && sudo chmod 700 /home/wuhan/.ssh && sudo chmod 600 /home/wuhan/.ssh/authorized_keys
```

退出后，以后都用 `wuhan` 登录：

```bash
ssh -i ~/.ssh/wuhan-hk.pem wuhan@服务器IP
```

## 4. 加 2G 交换空间（构建时防止内存不够，只做一次）

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile && echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 5. 装软件

系统更新和基础工具：

```bash
sudo apt update && sudo apt upgrade -y && sudo apt install -y git curl python3-venv debian-keyring debian-archive-keyring apt-transport-https
```

Node.js 24（和你 Mac 上的大版本一样；命令以 [NodeSource 的说明](https://github.com/nodesource/distributions) 为准）：

```bash
curl -fsSL https://deb.nodesource.com/setup_24.x -o /tmp/nodesource_setup.sh && sudo -E bash /tmp/nodesource_setup.sh && sudo apt install -y nodejs && node -v
```

Caddy（命令以 [Caddy 官网的安装页](https://caddyserver.com/docs/install#debian-ubuntu-raspbian) 为准）：

```bash
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
```

```bash
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
```

```bash
sudo chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg /etc/apt/sources.list.d/caddy-stable.list && sudo apt update && sudo apt install -y caddy
```

Ubuntu 24.04 自带 Python 3.12，项目要求 3.11 以上，可以用（你 Mac 上是 3.13，第 8 步会在服务器上跑一遍后端测试确认）。

## 6. 部署密钥：让服务器能读 GitHub 上的私有仓库

在服务器上生成一把只给这台服务器用的密钥：

```bash
ssh-keygen -t ed25519 -C "wuhanmemory-hk-server" -f ~/.ssh/github_deploy -N ""
```

```bash
cat ~/.ssh/github_deploy.pub
```

把显示的那一行复制下来，在 GitHub 网页上：仓库 `cecicai2026-code/WuhanMemory` → Settings → Deploy keys → Add deploy key，标题写"香港服务器"，粘贴，**不要**勾 "Allow write access"（只读）。

让 git 用这把密钥：

```bash
printf 'Host github.com\n  IdentityFile ~/.ssh/github_deploy\n  IdentitiesOnly yes\n' >> ~/.ssh/config && chmod 600 ~/.ssh/config
```

```bash
ssh -T git@github.com
```

第一次会问是否信任 GitHub，输入 `yes`。看到 "successfully authenticated" 就对了。

## 7. 拉代码

```bash
sudo mkdir -p /opt/wuhanmemory && sudo chown wuhan:wuhan /opt/wuhanmemory
```

```bash
git clone git@github.com:cecicai2026-code/WuhanMemory.git /opt/wuhanmemory && cd /opt/wuhanmemory && git log --oneline -1
```

## 8. 装依赖、跑后端测试

```bash
cd /opt/wuhanmemory && COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm install --frozen-lockfile
```

```bash
cd /opt/wuhanmemory/apps/api && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]" && .venv/bin/python -m pytest -q
```

最后一行应该是 "… passed"。有失败的，把输出贴给 Claude（输出里没有 key）。

## 9. 填环境变量

**后端**：把你 Mac 上已经填好的 `.env` 传上去，再改公开模式那几行。在 **Mac 终端**运行：

```bash
scp -i ~/.ssh/wuhan-hk.pem ~/WuhanMemory-project2/apps/api/.env wuhan@服务器IP:/opt/wuhanmemory/apps/api/.env
```

回到**服务器**，打开编辑：

```bash
chmod 600 /opt/wuhanmemory/apps/api/.env && nano /opt/wuhanmemory/apps/api/.env
```

确认或改成下面这样（其余 key 保持你 Mac 上的值）：

```text
PUBLIC_MODE=true
OWNER_PASSCODE=（你想好的口令）
TRUST_PROXY_HEADERS=true
RATE_PER_CLIENT_PER_HOUR=5
RATE_PER_DAY=50
PUBLIC_APP_URL=https://你的域名
DATABASE_URL=sqlite:///./wuhanmemory.db
```

`TRUST_PROXY_HEADERS=true` 只在有 Caddy 在前面时才能开（这里有）。nano 里按 Ctrl+O 回车保存，Ctrl+X 退出。

**前端**：

```bash
nano /opt/wuhanmemory/apps/web/.env.local
```

写两行（JS key 用你 Mac 上 `apps/web/.env.local` 里的那个）：

```text
NEXT_PUBLIC_AMAP_JS_KEY=（高德 JS key）
API_BASE_URL=http://127.0.0.1:8000
```

## 10. 检查资料、构建前端

```bash
cd /opt/wuhanmemory && corepack pnpm check:data && corepack pnpm build
```

构建要几分钟。`NEXT_PUBLIC_AMAP_JS_KEY` 是构建时写进网页的，以后改了这个 key 要重新构建。

## 11. 启动两个服务

```bash
sudo cp /opt/wuhanmemory/infra/deploy/wuhanmemory-api.service /opt/wuhanmemory/infra/deploy/wuhanmemory-web.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now wuhanmemory-api wuhanmemory-web
```

```bash
sleep 5 && curl -s http://127.0.0.1:8000/health && curl -sI http://127.0.0.1:3000 | head -1
```

应该看到 `{"status":"ok",…}` 和 `HTTP/1.1 200 OK`。

## 12. 配 Caddy（HTTPS）

```bash
sudo cp /opt/wuhanmemory/infra/deploy/Caddyfile /etc/caddy/Caddyfile && sudo sed -i 's/^example.com {/你的域名 {/' /etc/caddy/Caddyfile && sudo systemctl reload caddy
```

```bash
sleep 20 && sudo journalctl -u caddy -n 30 --no-pager
```

看到 "certificate obtained successfully" 之类的就好了。在 Mac 浏览器打开 `https://你的域名`。

## 13. 高德控制台

- **JS key 设域名白名单**：在高德开放平台控制台，给前端用的 JS key 加上 `你的域名`。你在本机开发也用这个 key 的话，同时保留 `localhost`。
- **Web 服务 key（可选）**：可以给服务器单独申请一个 Web 服务 key，IP 白名单只填服务器 IP，服务器的 `.env` 用这个新 key。这样就算服务器的 key 泄露，别处也用不了。
- 改了 `.env` 要重启后端：`sudo systemctl restart wuhanmemory-api`。

## 14. 预热路线（一次，用约 144 次高德路线查询）

```bash
cd /opt/wuhanmemory && corepack pnpm routes:prewarm
```

## 15. 验收

- [ ] `https://你的域名` 打开首页，地址栏有锁。
- [ ] `/map`：地图和图钉出来；发一句"武汉两天，喜欢历史和美食，坐地铁，11 月 28 日出发"，能排出方案。
- [ ] `/places/hubei-museum`：没有占位照片。
- [ ] `/trips`：先要口令，输对后能看到刚才那份行程；生成一个分享链接。
- [ ] 用手机**关掉 Wi-Fi、用流量**打开分享链接，能看到明信片和地图。
- [ ] 请一位在大陆的朋友和（如果可以）一位在香港的人分别打开，看速度。

## 以后更新网站

在 Mac 上合并、推送 main 以后，登录服务器运行：

```bash
bash /opt/wuhanmemory/infra/deploy/update.sh
```

它会拉最新的 main、装依赖、跑后端测试、构建、重启两个服务；测试不通过会停下，不会重启。

## 备份数据库

数据库里有线上排的行程和分享链接。在服务器上做一份一致的副本：

```bash
cd /opt/wuhanmemory/apps/api && .venv/bin/python -c "import sqlite3; s=sqlite3.connect('wuhanmemory.db'); d=sqlite3.connect('backup.db'); s.backup(d); d.close(); s.close()"
```

再在 Mac 终端拉回来：

```bash
scp -i ~/.ssh/wuhan-hk.pem wuhan@服务器IP:/opt/wuhanmemory/apps/api/backup.db ~/wuhanmemory-backup.db
```

## 出问题时看哪里

```bash
sudo journalctl -u wuhanmemory-api -n 100 --no-pager
```

```bash
sudo journalctl -u wuhanmemory-web -n 100 --no-pager
```

```bash
sudo journalctl -u caddy -n 100 --no-pager
```

把输出贴给 Claude 前看一眼，确认里面没有 key（正常情况下日志里不会有）。

## 还没管住的

- 路线接口和高德安全密钥代理没有限次数（见 ADR 0008）。
- 服务器只有一台，没有自动备份；重要的时候按上面手动备份。
- 规划任务的进度存在后端进程的内存里，所以后端只能开 1 个进程；`update.sh` 重启时正在排的行程会丢（已经存下的不丢）。
