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
