# 用 cpolar 让别人临时打开网站（你的 Mac + 内网穿透）

写于 2026-11-15。Cecilia 选了 `hosting-options.md` 的 B：网站还在你的 Mac 上跑，cpolar 给它一个别人能打开的网址。香港服务器（`deploy-hk.md`）先不做。

cpolar 的命令和免费版限制来自 cpolar 官网（出处在最后），2026-11-15 查的；官网的 macOS 教程写于 2022、2023 年，命令如果对不上，以官网为准。

## 先知道这几件事

- **只有你的 Mac 开着、网站和 cpolar 都在跑的时候，别人才打得开。** 合上盖子、睡眠、断网，链接就打不开了。
- **免费版的网址是随机的，官网说 24 小时内会变**（配置示例里写 24 到 48 小时）。重启 cpolar 会不会变，官网没写。所以网址每次用之前都要重新看一眼，再发给别人。
- **分享链接也跟着变。** 分享页的链接用的是当时打开网站的地址，cpolar 地址变了，以前发出去的分享链接就打不开了（链接后面那 8 位还有效，换成新地址就行）。
- **免费版限速 1Mbps**，地图和网页第一次打开会慢一点。cpolar 默认走国内节点，国内的朋友打开比香港快。
- 免费版同时只能开 **1 个 cpolar 进程**。

## 第 0 步：只做一次

### 装 Homebrew 和 cpolar

你的 Mac 上还没有 Homebrew。cpolar 官网说 Mac 上只能用 Homebrew 装。Homebrew 的安装命令以 [brew.sh](https://brew.sh) 为准，装完按它最后的提示把 brew 加进 PATH。

装 cpolar（官网的命令）：

```bash
brew tap probezy/core && brew install cpolar
```

### 注册 cpolar 账号，填 authtoken

1. 在 [cpolar 官网](https://www.cpolar.com) 注册，登录后台，在"验证"页面找到你的 authtoken。
2. 在终端运行（把后面换成你的 authtoken；这一步你自己做，token 不要发给 Claude）：

```bash
cpolar authtoken 你的authtoken
```

## 第 1 步：打开公开模式（每次给人看之前）

公开模式（ADR 0008）会限制访客排行程的次数，"我的行程"要口令，也不显示占位照片。不开的话，任何拿到网址的人都能无限次调用千问和豆包，花的是你的钱。

打开 `apps/api/.env`，在最后加上这几行（你的 `.env` 里现在还没有这几项）：

```text
PUBLIC_MODE=true
OWNER_PASSCODE=（你想好的口令）
TRUST_PROXY_HEADERS=true
RATE_PER_CLIENT_PER_HOUR=5
RATE_PER_DAY=50
```

- `RATE_PER_CLIENT_PER_HOUR`：每个访客每小时最多排几次。`RATE_PER_DAY`：整个网站一天最多排几次，这是最后一道闸。
- `TRUST_PROXY_HEADERS=true` 的原因：请求要先经过 cpolar 和前端再到后端，后端看到的地址都是你自己的 Mac。如果关着，所有访客会被当成同一个人，加起来每小时只能排 5 次。打开以后，后端用请求里的 X-Forwarded-For 区分访客。cpolar 官网没写它会不会加这个头：不加的话，效果和关着一样；如果有人故意伪造这个头，能绕过"每人每小时"，但绕不过"全站每天 50 次"。

## 第 2 步：构建正式版

先把开发时开着的两个终端（`pnpm dev` 和 `pnpm dev:api`）用 Ctrl+C 关掉，再运行：

```bash
cd ~/WuhanMemory-project2 && corepack pnpm build
```

要几分钟。代码改过、或者 `apps/web/.env.local` 里的高德 JS key 改过，都要重新构建。

## 第 3 步：启动网站（两个终端窗口，都别关）

后端（正式版不用 `--reload`）：

```bash
cd ~/WuhanMemory-project2 && corepack pnpm start:api
```

前端：

```bash
cd ~/WuhanMemory-project2 && corepack pnpm start:web
```

在你的 Mac 浏览器打开 `http://localhost:3000`，能看到首页就好了。

## 第 4 步：开 cpolar（第三个终端窗口，别关）

```bash
cpolar http 3000
```

终端里 `Forwarding` 那几行就是网址，一个 `http://`、一个 `https://`，**发 `https://` 那个**。也可以在浏览器打开 `http://127.0.0.1:9200`，用 cpolar 账号登录，在"状态 → 在线隧道列表"里看。

官网提醒：不要同时开好几个 `cpolar http`，否则会提示登录实例超过限制。

## 第 5 步：别让 Mac 睡着（给人看的这段时间）

第四个终端窗口运行这个，Mac 就不会自动睡眠，Ctrl+C 停掉就恢复（macOS 自带的命令）：

```bash
caffeinate -dims
```

合上盖子还是会睡眠，给人看的时候盖子别合。

## 第 6 步：高德地图

如果你在高德控制台给 JS key 设过域名白名单，要把 cpolar 的域名加进去，地图才出得来；cpolar 地址变了要再加。没设过白名单就不用管。

## 第 7 步：自己先试一遍

- [ ] 用手机**关掉 Wi-Fi、用流量**打开 `https://` 那个网址，首页能出来。
- [ ] `/map`：地图和图钉出来；发一句"武汉两天，喜欢历史和美食，坐地铁，11 月 28 日出发"，能排出方案。
- [ ] `/places/hubei-museum`：没有占位照片。
- [ ] `/trips`：先要口令，输对后能看到行程；生成一个分享链接，用手机打开能看到明信片和地图。

## 用完以后

1. 三个终端都按 Ctrl+C：cpolar、前端、后端（还有 `caffeinate`）。
2. 把 `apps/api/.env` 里的 `PUBLIC_MODE=true` 改回 `PUBLIC_MODE=false`（其余几行留着没关系，公开模式关着时不起作用）。
3. 照常 `corepack pnpm dev:api` 和 `corepack pnpm dev` 继续开发。

## 出处

- cpolar 文档：[cpolar.com/docs](https://www.cpolar.com/docs)（authtoken、`cpolar http`、9200 后台、免费地址 24 小时内会变、同时开多个会超限）
- cpolar 下载页：[cpolar.com/download](https://www.cpolar.com/download)（Mac 用 Homebrew 装）
- cpolar macOS 安装教程：[cpolar.com/blog/macos-installation-cpolar](https://www.cpolar.com/blog/macos-installation-cpolar)（`brew tap probezy/core && brew install cpolar`）
- cpolar macOS 快速入门：[cpolar.com/blog/cpolar-quick-start-tutorial-macos-series](https://www.cpolar.com/blog/cpolar-quick-start-tutorial-macos-series)（一个 http 地址、一个 https 地址）
- cpolar 价格：[cpolar.com/pricing](https://www.cpolar.com/pricing)（免费版 1Mbps、随机二级域名、1 个在线进程）
