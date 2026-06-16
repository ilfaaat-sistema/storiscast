# ТЗ: Сторискаст — сервис рассылки сторис (стек Render + Supabase)

> Документ для реализации в **Claude Code**. Цель — построить проект пофазно, без ошибок в API и инфраструктуре. Читать сверху вниз. Спорные параметры внешних API проверять по официальной документации (раздел 10), **не полагаться на память модели**.
> Версия стека: **Supabase (Postgres + Storage) + Render (Web + Cron Jobs) + React/Vite**. Серверов/VPS нет.

---

## 1. Что строим

Сервис принимает **одну историю** (фото/видео или группу медиа + подпись) и публикует её во все подключённые соцсети. Загрузка — один раз; дальше публикует сервер, независимо от соединения клиента. Старт — личные аккаунты владельца; архитектура сразу мультиарендная (клиенты позже).

**Ценность:** не «ещё один мультипостер», а связка `VK + личные Telegram-сторис + сведённая кросс-сетевая аналитика + офлайн-устойчивая рассылка`.

### Каналы и реальность API

| Канал | Как публикуется | Статус |
|---|---|---|
| ВКонтакте | Официальный stories API (upload-server → save) | прямой, первым |
| Telegram | Личный профиль, **MTProto user-сессия** (Telethon), не бот | прямой, лимит 3/сутки без Premium |
| Instagram | Graph API, `media_type=STORIES`, контейнерный flow | прямой, требует App Review |
| Facebook | **Прицепом за Instagram** (Meta Accounts Center) | авто, гипотеза — проверить |
| WhatsApp Status | Официального API нет | **вне ядра**, только вручную |

---

## 2. Границы (scope)

**В MVP:** VK, Telegram, Instagram (+ Facebook прицепом), очередь, аналитика, веб-UI.

**ВНЕ scope (не реализовывать):**
- Автопостинг WhatsApp Status (API нет). В UI — пометка «вручную».
- Эмулятор / UI-автоматизация. Отдельный модуль на будущее, с ToS-рисками. В проект не закладывать.
- Auth клиентов / биллинг — Phase 6. Сейчас один tenant по умолчанию, но модель данных мультиарендная.

---

## 3. Стек (зафиксировано)

- **Backend:** Python 3.11+, FastAPI, Uvicorn.
- **БД:** **Supabase Postgres** с первого дня. SQLAlchemy 2.x (async) + `asyncpg`. Миграции — Alembic. (SQLite не используем.)
- **Хранилище медиа:** **Supabase Storage**, публичный бакет → отдаёт публичные URL. Это обязательно: Instagram/Facebook требуют публично доступный `image_url`/`video_url`.
- **Очередь и расписание:** **НЕ вечный воркер.** Используем **Render Cron Jobs** — отдельные скрипты, запускаемые по расписанию (см. 4.2 и 8А). Бесплатный web service Render засыпает после 15 мин простоя, а Background Worker платный — поэтому всю фоновую работу делаем через cron.
- **HTTP-клиент:** `httpx` (async).
- **Telegram:** `telethon` (MTProto, **string session** — работает stateless из cron).
- **Frontend:** React + Vite (взять за основу готовый прототип-дизайн `storiscast-studio.jsx`).
- **Секреты:** переменные окружения Render + ключи Supabase. Токены аккаунтов в БД — **шифровать at rest** (`cryptography.Fernet`, ключ из env `FERNET_KEY`).
- **Тесты:** `pytest` + `respx` (мок httpx). Внешние API в тестах **всегда мокать**.

---

## 4. Архитектура

### 4.1 Паттерн адаптеров
Единый интерфейс публикатора, по реализации на канал:

```python
class StoryResult(BaseModel):
    ok: bool
    external_id: str | None = None   # id истории в сети (для аналитики/удаления)
    error: str | None = None
    manual: bool = False             # требует действия пользователя (WhatsApp)

class StoryPublisher(Protocol):
    platform: str
    async def publish_story(self, account, media: list, caption: str | None) -> StoryResult: ...
    async def fetch_insights(self, account, external_id: str) -> dict[str, int]: ...
```

Реализации: `VKPublisher`, `TelegramPublisher`, `InstagramPublisher`, `FacebookPublisher`. Изолированы: падение одной не влияет на другие.

### 4.2 Поток рассылки (cron-driven, не вечный процесс)
1. UI создаёт `cast` (медиа + подпись + каналы + время) → `POST /casts`.
2. Backend сохраняет `cast` и раскладывает на **по одному `job` на канал** со статусом `queued`.
3. **Cron `publish-worker`** (раз в ~1–2 мин): берёт `queued`/назревшие `scheduled` jobs, вызывает адаптер, пишет статус (`sending`→`done`/`error`), сохраняет `external_id`. Идемпотентность по `job.id` (не публиковать дважды).
4. Facebook-job выполняется **только после успеха Instagram-job** того же cast.
5. WhatsApp-job (если включён) сразу `manual`.
6. **Cron `insights-poller`** (раз в час): по jobs с `external_id` собирает метрики и пишет снапшоты (см. 5.3 про окно 24 ч).

Каждый cron-запуск — короткий, без состояния в памяти: читает Postgres, делает работу, выходит. Telethon поднимается из string session на время запуска.

### 4.3 Мультиарендность (заложить, не активировать UI)
`Tenant → ConnectedAccount → Credentials`. Все запросы скоупятся по `tenant_id`. На MVP один tenant по умолчанию.

---

## 5. Адаптеры — реализационные заметки и подводные камни

> Перед каждым клиентом — открыть официальную доку этого API (раздел 10) и сверить параметры.

### 5.1 VK (первым — проще всего)
- Публикация: `stories.getPhotoUploadServer` / `stories.getVideoUploadServer` → загрузка на `upload_url` → `stories.save`. Схему сверить в доке VK.
- Токен: с доступом к `stories` (для профиля — user-токен).
- Аналитика: `stories.getStats` (просмотры) и `stories.getViewers` (поимённый список зрителей).

### 5.2 Telegram (личный профиль)
- **Только MTProto user-сессия** (Telethon). НЕ bot-токен.
- Сессия создаётся владельцем заранее (`api_id`/`api_hash` + телефон + код + 2FA), хранится как **string session** (шифровать в БД/держать в env). Cron поднимает клиент из строки.
- Имя метода отправки истории — сверить в актуальном Telethon.
- **Лимиты без Premium: 3/сутки, 7/неделю, 30/месяц; жизнь 24 ч; подпись ≤200 симв.** Cron-воркер соблюдает суточный лимит: лишнее остаётся `queued` со сдвигом, не слать насильно.
- Обрабатывать `FloodWaitError` — уважать паузу.

### 5.3 Instagram (Graph API) — самый строгий
- Аккаунт: **Business/Creator**, обязательно связан с Facebook-страницей.
- Публикация — контейнерный flow: `POST /{ig-user-id}/media` с `media_type=STORIES` и **публичным** `image_url`/`video_url` (из Supabase Storage) → `creation_id` → `POST /{ig-user-id}/media_publish`. Локальные URL не пройдут.
- Разрешение `instagram_content_publish` + App Review (делает владелец). Токен — long-lived.
- **Лимит: 25 публикаций / 24 ч на аккаунт.** Воркер троттлит.
- **Аналитика (`story_insights`): `impressions`/views, `reach`, `replies`, `exits`, `taps_forward`, `taps_back`.** Метрики **исчезают после истечения истории (24 ч)** — `insights-poller` обязан собрать их до этого: опрашивать каждый IG-job через ~1, 6, 12, 23 ч после публикации, сохраняя снапшоты.
- Версию Graph API вынести в конфиг (сверить текущую перед кодом).

### 5.4 Facebook (прицепом)
- Гипотеза: при включённом тоггле Accounts Center «Sharing across profiles» (IG→FB Stories) история, опубликованная в IG через API, сама уезжает в FB. Для API-контента Meta это не гарантирует — владелец проверяет эмпирически.
- Реализация: сначала **без отдельного FB-адаптера**. FB-job = «ждёт IG», помечается `done (прицепом)` после успеха IG.
- **Фолбэк:** если тест покажет, что авто не срабатывает — тогда `FacebookPublisher` на Graph API. Пока — заглушка-интерфейс.

---

## 6. Модель данных (SQLAlchemy + Postgres)

- `tenants(id, name, created_at)`
- `connected_accounts(id, tenant_id, platform, handle, status, credentials_enc, meta_json, created_at)` — `credentials_enc` шифрованы.
- `casts(id, tenant_id, caption, status, scheduled_at, created_at)`
- `cast_media(id, cast_id, url, media_type[photo|video], position)`
- `jobs(id, cast_id, account_id, platform, status[queued|sending|done|error|manual|scheduled], attempts, last_error, external_id, published_at)`
- `insights(id, job_id, platform, metric, value, fetched_at)`

Enum-статусы строго перечислимые. Все `external_id` сохранять — нужны для аналитики и будущего удаления. Миграции — через Alembic.

---

## 7. API (FastAPI)

- `POST /media` — приём файла → загрузка в Supabase Storage → возврат публичного URL + типа.
- `GET /accounts` / `POST /accounts/{platform}/connect` (OAuth-колбэки) / `DELETE /accounts/{id}`.
- `POST /casts` — `{caption, media:[ids], targets:[platforms], scheduled_at?}` → создаёт cast + jobs (`queued`).
- `GET /casts/{id}` — агрегированный статус по каналам.
- `GET /casts/{id}/insights` — сведённые метрики.
- `GET /health` — healthcheck.

Публикацию **не** делать синхронно в запросе — только ставить `queued`, разгребает cron. (Иначе на спящем free-web задача может оборваться.)

---

## 8. Фазы и критерии приёмки

Работать строго пофазно, по одному адаптеру за раз, коммит в конце фазы.

- **Phase 0 — каркас.** Репозиторий, `CLAUDE.md`, Supabase-проект подключён (Postgres + Storage), модель данных + миграции, FastAPI-скелет, `POST /media` в Storage, интерфейс адаптера, **стаб-адаптеры**, cron-скрипты `publish-worker`/`insights-poller` (пока по стабам), React-UI на API. *Приёмка:* «создал cast → cron провёл jobs через стабы → статусы в UI».
- **Phase 1 — VK.** *Приёмка:* реальная история в VK + `getStats`/`getViewers` в `insights`.
- **Phase 2 — Telegram.** Telethon из string session, лимит 3/сутки. *Приёмка:* история в личном профиле; 4-я за сутки уходит в очередь, не в ошибку.
- **Phase 3 — Instagram.** Контейнерный flow + insights-поллер с окном 24 ч. *Приёмка:* реальная история; метрики собраны до истечения.
- **Phase 4 — Facebook.** Проверка авто-прицепа; при провале — адаптер. *Приёмка:* история в FB подтверждена.
- **Phase 5 — Аналитика.** Эндпоинт агрегации + дашборд «как разошлось».
- **Phase 6 — мультиарендность (позже).** Auth, изоляция по tenant; при росте — Render Background Worker вместо cron, отдельные процессы.

---

## 8А. Деплой (Render + Supabase)

**Состав сервисов:**
- **Supabase** (отдельный проект): Postgres (постоянный, в отличие от free-Postgres Render) + Storage (публичный бакет под медиа). Позже — Auth для клиентов.
- **Render Web Service** — FastAPI (API + OAuth-колбэки). HTTPS и домен Render даёт сам → колбэки VK/Meta работают из коробки, домен/Caddy не нужны.
- **Render Cron Job `publish-worker`** — раз в 1–2 мин разгребает очередь.
- **Render Cron Job `insights-poller`** — раз в час собирает метрики IG/VK.
- **Frontend** — Vite build как Render Static Site (или Vercel/Cloudflare Pages), указывает на API.

**Конфигурация:** описать инфраструктуру в `render.yaml` (Blueprint) — web + два cron. Все секреты — env-переменные Render (`DATABASE_URL` Supabase, ключи Supabase Storage, `FERNET_KEY`, токены, Telegram `api_id`/`api_hash`/session).

**Ограничения free-tier (учесть):**
- Free web засыпает после 15 мин → первый запрос после простоя 30–60 с (для OAuth-колбэка и редких публикаций терпимо; при необходимости поднять web до Starter).
- **Вечный Background Worker — платный.** Поэтому фон у нас на Cron Jobs. Текущую стоимость/лимиты cron сверить в дашборде Render.
- Free Postgres Render не использовать — БД берём в Supabase.

**Критично не потерять (хранить как секреты Render):** `FERNET_KEY`, Telegram **string session**, ключи Supabase. Потеря `FERNET_KEY` = токены аккаунтов в БД не расшифровать.

**Локальная разработка:** Phase 0–1 поднимаются локально (VK + стабы) на Supabase-базе. Прод-домен Render нужен начиная с Phase 3 (Meta заворачивает колбэк без https) — но Render даёт https сразу, отдельный домен покупать не обязательно.

---

## 9. Как вести работу в Claude Code (важно для агента)

1. **Сначала `/init`** → создать `CLAUDE.md`. Держать **коротким (≤200 строк)**, сверху — «контракт» из жёстких правил. Он подгружается в контекст каждой сессии.
2. **Контракт в CLAUDE.md (обязательные правила):**
   - Никогда не хардкодить токены/секреты. Только env + шифрование в БД. Поддерживать `.env.example`.
   - Не выдумывать параметры внешних API. Перед каждым клиентом — открыть официальную доку (раздел 10) и сверить.
   - Один адаптер за фазу. Не скаффолдить всё разом.
   - На каждый адаптер — тест с **замоканным** HTTP (`respx`), без реальных вызовов в CI.
   - Фон — только Render Cron Jobs; не добавлять вечный воркер/Celery/Redis без явного запроса.
   - Не блокировать event loop синхронным IO (только async/httpx).
   - Каждый платформенный job независим; идемпотентность по `job.id`.
   - Коммит в конце каждой фазы; перед крупным архитектурным решением — спросить.
3. Использовать venv, пинить зависимости, Alembic для миграций.
4. Сессии — под одну фазу, контекст не размазывать.
5. Спорные места API — не угадывать, останавливаться и уточнять.

---

## 10. Официальная документация (сверяться перед кодом)

- VK API (`stories.*`): https://dev.vk.com/ru/method/stories
- Telethon: https://docs.telethon.dev/
- Instagram — Content Publishing: https://developers.facebook.com/docs/instagram-platform/content-publishing
- Instagram — Insights: https://developers.facebook.com/docs/instagram-platform/insights/
- Meta Accounts Center — Sharing across profiles: https://www.meta.com/help/accounts-center/469011081363524/
- Supabase (Storage / Postgres): https://supabase.com/docs
- Render (Cron Jobs / Blueprints): https://render.com/docs
- FastAPI: https://fastapi.tiangolo.com/
- Claude Code: https://docs.claude.com/en/docs/claude-code/overview

---

## 11. DO / DON'T

**DON'T**
- Публиковать в IG/FB с локального URL — только публичный (Supabase Storage).
- Тянуть IG-insights позже 24 ч.
- Превышать 25 IG-публикаций/сутки и 3 TG-истории/сутки.
- Постить TG-истории бот-токеном — нужна user-сессия.
- Публиковать синхронно в HTTP-запросе — только через очередь + cron.
- Хранить токены в коде; терять `FERNET_KEY`.
- Тащить вечный воркер/Celery/Redis на MVP — фон на Cron Jobs.

**DO**
- Сохранять `external_id` каждого job; делать публикацию идемпотентной.
- FB прицепом за IG; отдельный адаптер — только если тест провалится.
- Мокать все внешние API в тестах.
- Шифровать креды; скоупить всё по tenant_id.
