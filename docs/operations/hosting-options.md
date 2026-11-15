# 让老师和朋友能打开网站：几种办法的比较（板块 7）

写于 2026-11-15，由 Claude 整理。**Cecilia 选了 D（香港轻量服务器）**（2026-11-15）。价格和"国内能不能访问"会变，下面标了出处；第三方文章的价格只当参考，下单前以官网为准。

## 先说三件不管选哪种都要做的事

1. **浏览器现在直接连 `localhost:8000` 的后端。** 别人的浏览器连不到你电脑上的 `localhost`，所以上线前要改成"浏览器只连网站一个地址"：前端把 `/api/*`、`/_AMapService/*`（高德安全密钥代理）、`/media/*` 转给后端（Next.js 的 rewrites）。这样也只需要对外开一个地址。这是上线前的一项代码改动，已做（2026-11-15，分支 `deploy-hk`，见 `apps/web/lib/backend.ts`）。
2. **打开公开模式**（ADR 0008）：`PUBLIC_MODE=true`、设 `OWNER_PASSCODE`；有隧道或反向代理时 `TRUST_PROXY_HEADERS=true`。网站用 `pnpm build` 后的正式版本运行，不用开发模式。
3. **高德 JS key 加域名白名单**：JS key 会出现在浏览器里（这是高德的设计），在高德控制台把它限制在你的网站域名上，别人拿走也用不了。千问、豆包、高德 Web 服务 key 和安全密钥只在后端的 `.env`，不会出现在网页里。

还有一点：你的听众里有港理工的老师（多半在香港或境外）和国内的朋友，两边能不能打开要分开看。

## 比较

| 办法 | 成本 | 难度 | key 的安全 | 国内能不能打开 | 香港和境外 | 网站什么时候能打开 |
|---|---|---|---|---|---|---|
| A. 只给录屏和 GitHub 代码 | 0 | 最低 | 最安全：网站不对外 | 视频平台能看 | 能看 | 一直能看录屏，但没人能自己操作 |
| B. 你的 Mac + 国内内网穿透（例如 cpolar、花生壳） | 免费版能用，固定域名和不限速要付费 | 低：装一个客户端，一条命令 | key 留在你的 Mac 上；靠公开模式管次数 | 好（服务器在国内） | 一般 | 只有你的 Mac 开着、网站在跑的时候 |
| C. 你的 Mac + Cloudflare Tunnel | 免费 | 低 | 同 B | 慢、可能断，不保证 | 好 | 同 B |
| D. 香港轻量云服务器（阿里云或腾讯云），一台跑前后端 | 第三方文章说阿里云香港约 25 元/月起；再加一个域名（可选，几十元/年） | 中：要在 Linux 上装 Node 和 Python、配好自动启动；Claude 写步骤和脚本，你照着在服务器上运行 | key 放在服务器的 `.env`，只有你能登录服务器 | 一般能打开，速度比国内服务器慢 | 好 | 24 小时 |
| E. Vercel 放前端 + 境外平台放后端（Render、Railway、Fly.io 等） | 免费档能用，后端要持久磁盘可能收费 | 中到高：前后端分两处，SQLite 要单独的持久磁盘 | key 放在平台的环境变量里 | `vercel.app` 默认域名在大陆不稳定，Vercel 官方说不保证 | 好 | 24 小时 |
| F. 内地云服务器 + 域名 + ICP 备案 | 服务器几十到几百元/年；域名几十元/年 | 高：备案要准备材料，等审核 | 同 D | 最好 | 一般 | 备案通过后 24 小时；备案初审 1 到 2 个工作日，管局审核 1 到 20 个工作日，之后 30 天内还要公安备案 |

### 每种办法的要点

- **A**：适合"只是要证明做出来了"。配合演示视频和 README 截图。
- **B / C**：适合约好时间给人看一次，比如面试前一天给朋友试用。电脑合上或断网，网站就打不开。cpolar 的免费版据第三方文章说域名随机、会变，还限速。国内用户多选 B；看的人在香港或境外选 C 更稳。
- **D**：适合"把链接写进材料里，老师什么时候点都能打开"。香港服务器不用备案。要做的事：买服务器、装环境、把代码拉下来、填 `.env`、配自动启动和 HTTPS。你的开发数据库不用传上去，服务器上会是一个新的数据库（景点资料从 git 里导入，我的行程是空的，你在线上重新排几份、生成分享链接）。占位照片本来就不在 git 里，服务器上不会有。
- **E**：免费，但改动最大，而且大陆访问没保证。不推荐。
- **F**：大陆访问最好，但备案时间不确定。未成年人能不能自己做备案主体，这次没查到确定的说法，要以你所在省份管局的规定为准。

## Claude 的推荐

- 要把链接写进给学校的材料：**D（香港轻量服务器）**。成本低、24 小时在线、香港和大陆都能打开、不用备案。
- 只是演示前后几天给朋友试：**B 或 C**，不花钱，用完就关。
- 不管选哪种，都同时准备 **A**（录屏），网站打不开时有备用。

选好后，Claude 先做"浏览器只连一个地址"的代码改动，再写具体的部署步骤（要在你电脑或服务器上运行的命令都写给你）。

## 出处

- Vercel 官方：[Accessing Vercel-hosted sites from mainland China](https://vercel.com/kb/guide/accessing-vercel-hosted-sites-from-mainland-china)（大陆没有节点；`.vercel.app` 可能被拦截或限速；不保证）
- Vercel 社区：[China project access network access failed](https://community.vercel.com/t/china-project-access-network-access-failed/10968)
- 腾讯云 CloudBase 博客（推广文章，立场有倾向）：[2026 cloudbase deployment domestic choice](https://cloudbase.cloud.tencent.com/en/blog/2026/04/20/2026-cloudbase-deployment-domestic-choice)
- 阿里云香港轻量服务器价格（第三方文章，非官方报价）：[developer.aliyun.com/article/1712992](https://developer.aliyun.com/article/1712992)；官方产品页：[aliyun.com/product/swas](https://www.aliyun.com/product/swas)
- Cloudflare Tunnel 在国内的速度（经验文章）：[redreamality.com 的 Cloudflare Tunnel 教程](https://redreamality.com/cn/garden/notes/library/cloudflare-tunnel-free-intranet-penetration-guide/)、[掘金：使用 cloudflare tunnel 打洞](https://juejin.cn/post/7186228417699217467)
- cpolar 免费版的限制（第三方文章）：[CSDN：cpolar 免费版经常重新分配 HostName 和 Port](https://blog.csdn.net/weixin_42426841/article/details/139842214)、[localtonet 常见问题里的对比](https://localtonet.com/zh/faq)
- ICP 备案时长、香港节点不用备案：[阿里云 ICP 备案帮助](https://help.aliyun.com/zh/dws/icp-filing)、[阿里云：域名备案后的处理](https://help.aliyun.com/zh/dws/user-guide/domain-name-processing-after-registration)
