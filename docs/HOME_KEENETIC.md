# HA дома за Keenetic — как это стыкуется

## Зачем вообще говорили про VPS

**Telegram Mini App открывается только по HTTPS из интернета.**  
Это требование Telegram, не прихоть проекта.

У вас сейчас:

- **Home Assistant** — ПК дома, снаружи виден как `http://xa.homesmart.netcraze.pro:81` (проброс порта на роутере).
- **Assistant Home** — отдельная программа (FastAPI). Её **нельзя** «вшить» в URL `/home` — это страница интерфейса HA.

VPS (`keenetichome.ru`) предлагался только как **маленькая HTTPS-витрина** для Telegram. **HA может оставаться дома** — сервер ходит к нему по `HA_URL` (у вас уже работает снаружи по :81).

## Два нормальных варианта без «переезда HA»

### A) Всё на ПК с HA (логичнее)

1. Установить `assistant_home` на тот же ПК (или другой в LAN).
2. В `.env`:
   - `HA_URL=http://127.0.0.1:8123` (или локальный IP HA)
   - `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID=371010834`
3. Дать Mini App **HTTPS** одним из способов:
   - **Cloudflare Tunnel** на порт `8010` (бесплатно, без VPS)
   - проброс другого порта на Keenetic + свой сертификат (сложнее)
   - reverse SSH на VPS **только для HTTPS** (как туннель для SSH у KU)

### B) Только бот на VPS, HA дома

На VPS крутится только uvicorn; в `.env` на VPS:

`HA_URL=http://xa.homesmart.netcraze.pro:81` — как сейчас.

## Что не нужно

- Переносить Home Assistant на VPS.
- Использовать `http://...:81/home` как адрес Mini App.

## BotFather

Web App URL = ваш **HTTPS** + `/tg/app`, например:

`https://xxxx.trycloudflare.com/tg/app` (тест) или постоянный туннель/домен.

`PUBLIC_BASE_URL` в `.env` должен совпадать с этим URL (без `/tg/app`).
