# Деплой Assistant Home

## Можно ли использовать `http://xa.homesmart.netcraze.pro:81/home`?

**Нет** — для Mini App это не подходит:

| Причина | Пояснение |
|---------|-----------|
| **HTTP** | Telegram Web App принимает только **HTTPS** в BotFather |
| **Порт 81** | Там уже крутится **Home Assistant**, не наш FastAPI |
| **Путь `/home`** | Это UI Home Assistant, не API бота |

HA остаётся по `HA_URL=http://xa.homesmart.netcraze.pro:81` — сервер **ходит к HA по API**, пользователь в Telegram открывает **другой** HTTPS-URL.

## Рабочие варианты `PUBLIC_BASE_URL`

1. **Тот же VPS, что Keenetic Unified** (рекомендуется, если есть доступ):
   - `https://keenetichome.ru/ah` → nginx → `127.0.0.1:8010`
   - Mini App в BotFather: `https://keenetichome.ru/ah/tg/app`

2. **Поддомен на netcraze** (если на роутере/хосте HA можно добавить location в nginx **без** поломки `/home`):
   - `https://xa.homesmart.netcraze.pro/ah/tg/app` — только если настроите прокси на процесс uvicorn (отдельно от HA на :81)

3. **Отдельный поддомен** с Let's Encrypt, например `https://assistant.homesmart.netcraze.pro`

## Установка на VPS (рядом с KU)

```bash
sudo mkdir -p /opt/assistant_home
sudo git clone https://github.com/andrey271192/assistant_home.git /opt/assistant_home
cd /opt/assistant_home
python3 -m venv .venv
.venv/bin/pip install -r server/requirements.txt
cp server/.env.example server/.env
# заполнить server/.env (HA_URL, HA_TOKEN, TELEGRAM_*, PUBLIC_BASE_URL)
cp server/data/rooms.example.json server/data/rooms.json
cp server/data/access.example.json server/data/access.json

sudo cp deploy/assistant-home.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now assistant-home
```

Nginx: фрагмент `deploy/nginx/keenetichome-ah.conf` — вставить в server {} для `keenetichome.ru`, затем `sudo nginx -t && sudo systemctl reload nginx`.
