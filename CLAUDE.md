# CLAUDE.md — Сторискаст

Сервис рассылки одной сторис (фото/видео + подпись) во все соцсети. Стек: **FastAPI + Supabase (Postgres+Storage) + Render (Web + Cron) + React/Vite**. Полное ТЗ — в `storiscast_TZ.md` (читать перед новой фазой).

## КОНТРАКТ (нарушать нельзя)

1. **Секреты** — только из env (+ `.env.example`). Токены аккаунтов в БД шифровать (`Fernet`, ключ `FERNET_KEY`). Никогда не хардкодить и не коммитить секреты.
2. **Внешние API** — не выдумывать параметры. Перед написанием любого клиента открыть офдоку (ссылки внизу) и сверить методы/поля/версии.
3. **Одна фаза за раз.** Не скаффолдить будущие фазы. В конце фазы — коммит, показать критерий приёмки. Phase N+1 — только по команде владельца.
4. **Фон — только Render Cron Jobs.** Не добавлять вечный воркер / Celery / Redis без явного запроса.
5. **Публикация — только через очередь.** В HTTP-запросе ставить job в `queued`; публикует cron. Никогда не публиковать синхронно в запросе.
6. **Каждый job независим и идемпотентен** по `job.id`. Падение одного канала не останавливает другие. Всегда сохранять `external_id`.
7. **Тесты:** на каждый адаптер — тест с замоканным HTTP (`respx`). Реальных сетевых вызовов в CI нет.
8. **Async везде** (httpx, asyncpg). Не блокировать event loop синхронным IO.
9. При архитектурной развилке или неоднозначности API — **остановиться и спросить**, не угадывать.

## Стек и структура

- Python 3.11+, FastAPI, Uvicorn, SQLAlchemy 2 (async) + asyncpg, Alembic.
- Supabase Postgres (БД) + Supabase Storage (публичный бакет под медиа).
- Telegram — Telethon (MTProto, string session, stateless из cron).
- Frontend — React + Vite (основа дизайна — `storiscast-studio.jsx`).

```
backend/
  app/        # FastAPI: routers, models, schemas, adapters/, services/
  cron/       # publish_worker.py, insights_poller.py (запускаются Render Cron)
  alembic/
  tests/
frontend/     # React + Vite
render.yaml   # web + 2 cron
.env.example
```

## Команды (поддерживать в актуальном виде)

- Запуск API: `uvicorn app.main:app --reload`
- Тесты: `pytest`
- Миграции: `alembic revision --autogenerate -m "..."` / `alembic upgrade head`
- Cron локально: `python -m cron.publish_worker` / `python -m cron.insights_poller`

## Каналы — критические факты API

- **VK:** `stories.getPhotoUploadServer`/`getVideoUploadServer` → upload → `stories.save`. Метрики: `stories.getStats`, `stories.getViewers`. User-токен со scope `stories`.
- **Telegram:** только user-сессия (НЕ бот). Лимит без Premium **3/сутки**, жизнь 24 ч, подпись ≤200 симв. Ловить `FloodWaitError`. Лишнее — оставлять `queued`, не слать насильно.
- **Instagram:** Business/Creator + связанная FB-страница. Контейнерный flow `media_type=STORIES` с **публичным** URL (Supabase Storage) → `creation_id` → `media_publish`. Лимит **25/24ч**. Метрики `story_insights` (`impressions/reach/replies/exits/taps_forward/taps_back`) **исчезают через 24 ч** — поллер собирает через ~1/6/12/23 ч.
- **Facebook:** прицепом за IG (Accounts Center). Сначала БЕЗ адаптера: FB-job → `done` после успеха IG. Отдельный адаптер только если тест авто-прицепа провалится.
- **WhatsApp:** API нет. Вне ядра, job помечается `manual`. Не автоматизировать.

## Модель данных

`tenants` · `connected_accounts(credentials_enc)` · `casts` · `cast_media` · `jobs(status: queued|sending|done|error|manual|scheduled, external_id)` · `insights`. Всё скоупится по `tenant_id` (MVP — один tenant по умолчанию).

## Фазы

0 каркас на стабах · 1 VK · 2 Telegram · 3 Instagram (+insights-поллер) · 4 Facebook · 5 аналитика · 6 мультиарендность (позже). Критерии приёмки — в `storiscast_TZ.md` §8.

## Деплой (Render + Supabase)

`render.yaml`: web (FastAPI) + cron `publish-worker` (1–2 мин) + cron `insights-poller` (1 ч). БД и Storage — Supabase. HTTPS/домен даёт Render (OAuth-колбэки работают). Free web засыпает после 15 мин — это ок для редких публикаций. Не терять секреты: `FERNET_KEY`, Telegram string session, ключи Supabase.

## Документация

- VK: https://dev.vk.com/ru/method/stories
- Telethon: https://docs.telethon.dev/
- IG Content Publishing: https://developers.facebook.com/docs/instagram-platform/content-publishing
- IG Insights: https://developers.facebook.com/docs/instagram-platform/insights/
- Supabase: https://supabase.com/docs · Render: https://render.com/docs · FastAPI: https://fastapi.tiangolo.com/
