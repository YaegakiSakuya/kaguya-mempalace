# Telegram Mini App (Legacy Home + MemPalace Realtime)

This repo now includes a dedicated Telegram Mini App frontend and backend API:

- Frontend: `/miniapp`
- Auth API: `POST /api/miniapp/auth`
- Data APIs: `GET /api/miniapp/current`, `GET /api/miniapp/history`, `GET /api/miniapp/stream`

## Required env vars

- `TELEGRAM_BOT_TOKEN` (already required)
- `MINIAPP_URL` — public HTTPS URL that points to `/miniapp`

Optional:

- `MINIAPP_SESSION_SECRET` (defaults to bot token)
- `MINIAPP_SESSION_TTL_SECONDS` (default: `900`)
- `MINIAPP_INITDATA_MAX_AGE_SECONDS` (default: `300`)
- `INSPECTOR_PORT` (shared API server port, default `8765`)

## Run

```bash
python -m app.main
```

When `MINIAPP_URL` is set, `/start` replies with an **Open Mini App** button.

## Test checklist

1. Open Telegram chat with your bot.
2. Send `/start`, tap **Open Mini App**.
3. Mini App should authenticate via `initData` and load only your `chat_id` current/history.
4. Send a message to the bot in same chat; Mini App stream should update live (`processing/thinking/replying/done`).

