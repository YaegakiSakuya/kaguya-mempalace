# 部署指南

## 前置条件

- kaguya-gateway 服务正常运行（systemd）
- Inspector 在 8765 端口正常服务
- nginx 已配置域名和 HTTPS

## 部署步骤

### 1. 构建前端

```bash
cd /home/ubuntu/apps/kaguya-mempalace/miniapp
npm install
npm run build
```

### 2. 配置 nginx

将 `deploy/nginx-miniapp.conf` 中的 location 块合并到你的 nginx server 配置中。

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 3. 配置 Telegram BotFather

1. 打开 @BotFather
2. 选择你的 bot
3. /setmenubutton
4. 输入 Web App URL：`https://你的域名/miniapp/`
5. 输入按钮文字：`MemPalace`

### 4. 验证

在 Telegram 中点击 bot 的菜单按钮，应该能打开 Mini App。

### 生产环境 API 地址

前端通过 nginx 反代访问后端 API，不需要设置 VITE_API_BASE。
确保 useApi.js 和 useSSE.js 中的 API_BASE 默认值为空字符串。

## nginx 配置部署

权威文件：`nginx/api.onlykaguya.com.conf`，1:1 对应线上 `/etc/nginx/sites-available/api.onlykaguya.com` 的完整 server block。

### 部署步骤

```bash
sudo cp nginx/api.onlykaguya.com.conf /etc/nginx/sites-available/api.onlykaguya.com
sudo ln -sf /etc/nginx/sites-available/api.onlykaguya.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

第二步在符号链接已存在时是幂等的。

### TLS 证书

由 certbot 管理，路径 `/etc/letsencrypt/live/api.onlykaguya.com/`。新机器首次部署需先签发证书：

```bash
sudo certbot --nginx -d api.onlykaguya.com
```

### 当前 server block 包含的路由

- `/miniapp/` — Telegram Mini App 静态资源 + 4 个后端代理路由（`127.0.0.1:8765`）
- `/palace/` — 桌面端网页门面（`webui/` 目录），静态资源
- `/mcp` — FastMCP 服务（`127.0.0.1:8766`），IP 白名单
- `/exec/` — Exec MCP（`127.0.0.1:3456`），IP 白名单
- `/.well-known/oauth-*` — 显式 404，防止 MCP client 误探测
- `/` — 404（故意，根路径不对外服务）

### 维护约定

线上 `/etc/nginx/...` 有任何改动，必须立即同步回 `nginx/api.onlykaguya.com.conf` 并提 PR，避免再次漂移。
