# Assistant Home

Telegram Mini App для управления **Home Assistant**: комнаты, выключатели, статусы, автоматизации. Отдельный проект, не связан с [keenetic-unified](https://github.com/andrey271192/keenetic-unified).

## Возможности

- Mini App в Telegram (как у Keenetic Unified): список комнат → устройства → автоматизации
- Доступ по Telegram user ID + опциональный PIN
- ACL: у каждого пользователя свой набор комнат (`server/data/access.json`)
- Прокси к HA REST API (токен только на сервере)

## Быстрый старт

```bash
cd assistant_home
python3 -m venv .venv && source .venv/bin/activate
pip install -r server/requirements.txt
cp server/.env.example server/.env
cp server/data/rooms.example.json server/data/rooms.json
cp server/data/access.example.json server/data/access.json
# Отредактируйте server/.env и data/*.json
uvicorn server.main:app --host 0.0.0.0 --port 8010
```

В BotFather укажите Web App URL: `https://ВАШ_ДОМЕН/tg/app` (нужен **HTTPS**).

**Не путать с Home Assistant:** `http://xa.homesmart.netcraze.pro:81/home` — это только UI HA.  
Mini App живёт на отдельном HTTPS (например `https://keenetichome.ru/ah/tg/app`). Подробнее: [docs/PRODUCTION.md](docs/PRODUCTION.md).

### Переменные `.env`

| Переменная | Назначение |
|------------|------------|
| `TELEGRAM_TOKEN` | Токен бота |
| `TELEGRAM_ALLOWED_IDS` | Telegram user ID через запятую |
| `TELEGRAM_PIN` | PIN для toggle/автоматизаций (пусто = без PIN) |
| `PUBLIC_BASE_URL` | Публичный HTTPS без слэша в конце |
| `HA_URL` | URL Home Assistant |
| `HA_TOKEN` | Long-lived access token (профиль HA) |

### Комнаты и доступ

- `server/data/rooms.json` — комнаты и `entity_id` (свет, switch, climate…)
- `server/data/access.json` — кто какие комнаты видит (`rooms: ["*"]` = всё для admin)

Обновить комнаты из HA:

```bash
.venv/bin/python scripts/build_rooms_from_ha.py
```

(нужны `HA_URL` и `HA_TOKEN` в `server/.env`)

Узнать свой Telegram ID: напишите боту [@userinfobot](https://t.me/userinfobot).

## API (Mini App)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/tg/auth` | initData + опционально PIN |
| GET | `/api/tg/rooms` | Список комнат |
| GET | `/api/tg/room/{id}` | Устройства + статусы |
| POST | `/api/tg/entity/toggle` | Переключить сущность |
| POST | `/api/tg/automation/trigger` | Запустить автоматизацию |

## Деплой

См. `deploy/assistant-home.service` — systemd на VPS рядом с nginx (прокси на `127.0.0.1:8010`).

## Дальше

- [ ] Синхронизация комнат из HA Areas (WebSocket)
- [ ] Сценарии / scripts
- [ ] Уведомления HA → Telegram
- [ ] Админ-страница для редактирования `rooms.json`
