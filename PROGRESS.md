# PROGRESS — Сторискаст

## Phase 0 — Каркас на стаб-адаптерах ✓

### Что сделано

- **Структура репо:** `backend/` (FastAPI) + `frontend/` (React/Vite) + `render.yaml` (Blueprint).
- **Модель данных:** 6 таблиц (tenants, connected_accounts, casts, cast_media, jobs, insights) — Alembic-миграция `0001_initial.py`.
- **Supabase:** `asyncpg` для Postgres, `supabase-py` через `asyncio.to_thread` для Storage.
- **POST /media** — загружает файл в Supabase Storage, возвращает публичный URL + тип.
- **POST /casts** — создаёт Cast + CastMedia + Jobs (по одному на платформу); FB добавляется автоматически при наличии IG.
- **GET /casts/{id}** — текущий статус cast + jobs (для поллинга из UI).
- **GET /accounts** — список подключённых аккаунтов.
- **Адаптеры:** `StoryPublisher` (Protocol), `StubPublisher` — мгновенно возвращает `ok=True`.
- **publish_worker** — поднимает `queued` jobs, вызывает адаптер, пишет `done`/`error`; WA → `manual`; FB ждёт IG.
- **insights_poller** — по jobs с `external_id` вызывает `fetch_insights`, сохраняет снапшоты.
- **Auto-seed:** при первом старте FastAPI создаёт default tenant + stub-аккаунты для всех платформ.
- **Frontend:** точный визуальный язык прототипа (canvas #E9E7E0, primary #1B3A8F, amber #EC8B2B). Экраны: Compose (upload → /media), Publishing (poll GET /casts/{id}), Done, Channels (GET /accounts), Analytics (GET /casts/{id}/insights). Состояние `lastCastId` → localStorage.
- **Тесты:** `test_stub_adapter.py` — 3 теста, respx не нужен для стабов (нет сети).

### Ключевые решения

| Вопрос | Решение |
|--------|---------|
| FB job | auto-добавляется при IG; `publish_worker` ставит `done` сразу после успеха IG |
| WA job | `manual` сразу при создании cast |
| Supabase Storage | sync supabase-py в `asyncio.to_thread` (async-клиент нестабилен в 2.x) |
| Alembic + async | `async_engine_from_config` + `asyncio.run()` в `env.py` |
| Секреты | только из env, `.env.example` с комментариями; `FERNET_KEY` — generate-команда вписана |
| enum статусов | `TEXT` + `CHECK CONSTRAINT` вместо Postgres ENUM (проще Alembic) |
| DB seed | lifespan-событие FastAPI — идемпотентно |

---

## Phase 1 — VK адаптер ✓

### Что сделано

- **`backend/app/adapters/vk.py`** — `VKPublisher`:
  - `publish_story`: `stories.getPhotoUploadServer` / `stories.getVideoUploadServer` → скачать медиа из Supabase Storage → POST на `upload_url` (field `file`) → `stories.save(upload_results_json=...)` → `external_id = "{owner_id}_{story_id}"`.
  - `fetch_insights`: `stories.getStats` (views/replies/shares/likes/subscribers/answer/bans/open_link) + `stories.getViewers` (viewers_count). Оба вызова независимы — частичный успех сохраняется.
- **VK API версия:** 5.199 (из официальной JSON-схемы VKCOM/vk-api-schema).
- **Токен:** из `account.credentials_enc` (Fernet-decrypt → JSON → `access_token`) или из env `VK_ACCESS_TOKEN` (fallback).
- **`backend/app/config.py`** — добавлено `VK_ACCESS_TOKEN: str = ""`.
- **`backend/requirements.txt`** — httpx понижен до `0.27.2` (supabase==2.10.0 требует `<0.28`).
- **Cron:** `publish_worker.py` и `insights_poller.py` — `"vk"` теперь использует `VKPublisher()`.
- **Тесты:** `tests/test_vk_adapter.py` — 9 тестов, respx-мок, без реальных вызовов. **12/12 passed**.

### Ключевые решения

| Вопрос | Решение |
|--------|---------|
| Поле при загрузке в upload_url | `file` — подтверждено из vk_api library (key_format='file') |
| Передача результата в stories.save | `upload_results_json=json.dumps(upload_data)` — весь JSON от upload-сервера |
| external_id | `"{owner_id}_{story_id}"` — оба поля из `stories.save` response `items[0]` |
| Content-type | Берётся из заголовка ответа Supabase Storage (не захардкожено) |
| Частичные insights | getStats и getViewers — раздельные try/except, partial data сохраняется |

### Критерий приёмки

**Реальная история в VK:** `VK_ACCESS_TOKEN` (user-токен scope `stories`) → запуск `python -m cron.publish_worker` → story появляется в профиле, `job.status = done`, `job.external_id` заполнен → запуск `python -m cron.insights_poller` → метрики в таблице `insights`.

---

## Phase 2 — Telegram адаптер ✓

### Что сделано

- **`backend/app/adapters/telegram.py`** — `TelegramPublisher`:
  - `publish_story`: `CanSendStoryRequest` (проверка квоты) → скачать медиа httpx → `client.upload_file()` → `InputMediaUploadedPhoto` / `InputMediaUploadedDocument` → `SendStoryRequest(peer=InputPeerSelf(), privacy_rules=[InputPrivacyValueAllowAll()], period=86400)` → извлечь `UpdateStoryID.id` → `external_id = str(story_id)`.
  - `fetch_insights`: `GetStoriesViewsRequest` → `StoryViews.views_count` + `reactions_count` + `forwards_count`.
  - Лимит 3/сутки: `CanSendStoryRequest.count_remains == 0` → `retry_later=True` (job остаётся `queued`).
  - `FloodWaitError` → `retry_later=True` с сообщением о паузе.
  - Подпись обрезается до 200 символов.
- **`backend/app/adapters/base.py`** — добавлено поле `retry_later: bool = False` в `StoryResult`.
- **`backend/app/config.py`** — добавлены `TG_API_ID: int`, `TG_API_HASH: str`, `TG_SESSION_STRING: str`.
- **`backend/cron/publish_worker.py`** — `"tg"` → `TelegramPublisher()`; обработка `retry_later`: job возвращается в `queued`, не в `error`.
- **`backend/cron/insights_poller.py`** — `"tg"` → `TelegramPublisher()`.
- **`backend/requirements.txt`** — добавлен `telethon==1.44.0`.
- **Тесты:** `tests/test_telegram_adapter.py` — 11 тестов, Telethon замокан через `@patch` (TelegramClient + StringSession), respx для httpx. **23/23 passed**.

### Ключевые решения

| Вопрос | Решение |
|--------|---------|
| Telethon API для сторис | `telethon.tl.functions.stories.SendStoryRequest` — подтверждён из исходников пакета v1.44.0 |
| Извлечение story_id | `UpdateStoryID.id` из `updates.updates` в ответе `SendStoryRequest` |
| Квота 3/день | `CanSendStoryRequest` → `count_remains == 0` → `retry_later=True`, job → `queued` |
| FloodWaitError | catch отдельно → `retry_later=True`, job → `queued` |
| Мок в тестах | `StringSession` нужно мокать наряду с `TelegramClient` (валидирует строку в конструкторе) |
| Статeless из cron | `async with TelegramClient(StringSession(session_str), ...)` — поднимается и закрывается за один прогон |
| Insights | `GetStoriesViewsRequest` → `StoryViews.views_count/reactions_count/forwards_count`; нет данных → `{}` |

### Критерий приёмки

**Реальная история в Telegram:** задать `TG_API_ID`, `TG_API_HASH`, `TG_SESSION_STRING` → создать cast с target `tg` → запустить `python -m cron.publish_worker` → история появляется в личном профиле Telegram, `job.status = done`, `job.external_id` (int story_id) заполнен.

**Лимит:** при 4-й попытке за сутки `CanSendStoryRequest.count_remains == 0` → `job.status = queued` (не `error`).

---

## Phase 3 — Instagram адаптер + insights-поллер ✓

### Что сделано

- **`backend/app/adapters/instagram.py`** — `InstagramPublisher`:
  - `publish_story`: quota check → POST `/{ig-user-id}/media` (STORIES, image_url/video_url) → creation_id → (video: poll status_code до FINISHED, 6×5с) → POST `/{ig-user-id}/media_publish` → external_id.
  - `fetch_insights`: два раздельных вызова — `metric=impressions,reach,replies` + `metric=navigation&breakdown=story_navigation_action_type` → ключи `taps_forward/taps_back/exits/swipe_forward`. Частичный успех сохраняется (независимые try/except).
  - Rate limit: `GET /{ig-user-id}/content_publishing_limit?fields=config,quota_usage` → `quota_usage >= quota_total` → `retry_later=True` (job остаётся queued). При ошибке проверки — оптимистично пропускаем.
- **Graph API version:** v21.0 по умолчанию, переопределяется через `IG_GRAPH_API_VERSION`.
- **`backend/app/config.py`** — добавлены `IG_ACCESS_TOKEN`, `IG_USER_ID`, `IG_GRAPH_API_VERSION`.
- **`backend/cron/publish_worker.py`** — `"ig"` → `InstagramPublisher()`.
- **`backend/cron/insights_poller.py`** — `"ig"` → `InstagramPublisher()`; IG-jobs старше 23.5ч пропускаются (`_IG_INSIGHTS_TTL`), т.к. метрики исчезают после 24ч.
- **`.env.example`** — добавлены `IG_ACCESS_TOKEN`, `IG_USER_ID`, `IG_GRAPH_API_VERSION` с комментариями о нужных scope.
- **Тесты:** `tests/test_instagram_adapter.py` — 12 тестов, respx-мок, без реальных вызовов. **35/35 passed** (весь сьют).

### Ключевые решения

| Вопрос | Решение |
|--------|---------|
| Метрики exits/taps_forward/taps_back | НЕ самостоятельные метрики — breakdown-значения метрики `navigation` с `breakdown=story_navigation_action_type`. Два раздельных вызова insights. |
| Rate limit | Динамическая проверка через `content_publishing_limit` (возвращает `quota_total` из API, не хардкодим). Официальная дока — 100/24ч (CLAUDE.md указывал 25 — устаревшее). |
| Video processing | Polling `status_code` (FINISHED/IN_PROGRESS/ERROR), 6 попыток × 5с = макс 30с. При ERROR — ошибка. |
| IG insights TTL | insights_poller пропускает IG-jobs старше 23.5ч (`_IG_INSIGHTS_TTL`) — гарантирует последний снапшот до истечения 24ч. |
| external_id | media_id из `media_publish` ответа (строка вида `"987654321_123456789"`). |
| Медиа URL | Публичный URL из Supabase Storage — IG забирает его сам (не загружаем бинарник). |
| Оптимизм при ошибке квоты | Если `content_publishing_limit` недоступен → разрешаем публикацию (сервер вернёт ошибку и job уйдёт в error). |

### Критерий приёмки

**Реальная история в Instagram:** задать `IG_ACCESS_TOKEN` (user-токен scope `instagram_basic,instagram_content_publish,instagram_manage_insights`) + `IG_USER_ID` → создать cast с target `ig` → `python -m cron.publish_worker` → история появляется в профиле, `job.status=done`, `job.external_id` заполнен.

**Лимит:** при исчерпании квоты `quota_usage >= quota_total` → `job.status=queued` (не `error`).

**Метрики:** `python -m cron.insights_poller` в течение 23.5ч с момента публикации → `impressions`, `reach`, `replies`, `taps_forward`, `taps_back`, `exits`, `swipe_forward` в таблице `insights`.

---

## Phase 5 — Аналитика ✓

### Что сделано

- **`_aggregate_insights(jobs, insights)`** — экстрактирована в чистую функцию в `backend/app/routers/casts.py`. Принимает списки объектов с `.job_id/.metric/.value/.fetched_at` → возвращает `list[JobInsightOut]`. Для каждого `(job_id, metric)` оставляет снапшот с наибольшим `fetched_at`.
- **`GET /casts`** — новый эндпоинт: список последних N кастов tenant'а (порядок desc, лимит 50 максимум). Возвращает `list[CastListOut]` с `id, caption, status, created_at, platforms[]`.
- **`CastListOut`** — новая Pydantic-схема в `schemas.py`.
- **`GET /casts/{id}/insights`** — рефакторинг: теперь использует `_aggregate_insights()` вместо инлайн-логики.
- **`frontend/src/api.js`** — добавлен `getCasts(limit=10)`.
- **`frontend/src/components/Analytics.jsx`** — добавлен `CastPicker`: горизонтальный скролл последних 5 кастов; клик меняет `selectedId` → перезагружает insights. Начальный выбор: `lastCastId` из props (последний опубликованный), иначе первый в списке.
- **Тесты:** `tests/test_insights_aggregation.py` — 9 тестов чистой функции (no DB/network). Плюс `tests/test_analytics_endpoint.py` (5 тестов, ASGI-мок). **62/62 passed.**

### Ключевые решения

| Вопрос | Решение |
|--------|---------|
| Тестируемость aggregation | Экстракт в `_aggregate_insights()` — чистая функция, нет async/DB |
| Пикер кастов | Горизонтальный скролл до 5 кастов; каждая карточка показывает время, цветные точки платформ, первую строку подписи |
| Первый выбор | `lastCastId` prop → иначе `casts[0].id` из `/casts` |
| `GET /casts` лимит | `min(limit, 50)` — защита от неограниченных запросов |
| latest snapshot | Сравнение `fetched_at` — побеждает самый поздний |

### Критерий приёмки

**Автоматический:** `pytest` — **62 passed**.

**Ручной:**
1. Вкладка «Аналитика» показывает горизонтальную полосу кастов — клик переключает.
2. При выборе каста загружаются метрики через `GET /casts/{id}/insights`.
3. Суммарный охват + барчарт по платформам отображаются корректно.

---

## Phase 4 — Facebook auto-done ✓

### Что сделано

- **Логика в `cron/publish_worker.py`** (реализована в Phase 0, верифицирована в Phase 4):
  - Блок `platform == "fb"`: ищет IG-job того же `cast_id`; если `ig_job.status == "done"` → ставит `fb_job.status = "done"` + `published_at`. Если IG не готов (любой другой статус) или вовсе нет — ждёт следующего тика cron.
  - Отдельного FB-адаптера нет. Accounts Center (Sharing across profiles IG→FB) обеспечивает появление сторис в FB автоматически при публикации через IG Graph API.
- **Тесты: `tests/test_facebook_worker.py`** — 8 тестов, без реальной DB и сети:
  - `test_fb_done_when_ig_done` — FB → done после IG done.
  - `test_fb_published_at_is_utc_aware` — `published_at` tz-aware и попадает в ожидаемое окно.
  - `test_fb_scheduled_also_auto_done` — FB в статусе `scheduled` тоже обрабатывается.
  - `test_fb_stays_queued_while_ig_queued/sending/error` — FB ждёт при незавершённом IG.
  - `test_fb_stays_queued_when_no_ig_job` — FB ждёт если IG-job вообще нет.
  - `test_fb_not_reprocessed_when_already_done` — `_process_job` выходит на первой проверке `status`.
- **Полный тест-сьют: 43/43 passed.**

### Ключевые решения

| Вопрос | Решение |
|--------|---------|
| Отдельный FB-адаптер? | Нет — FB получает сторис через Accounts Center за IG (авто-прицеп). Отдельный адаптер — только если тест реального прохождения покажет сбой. |
| Мок DB-сессии | `AsyncMock` + `MagicMock` ScalarResult; Job-объекты — `SimpleNamespace` (нет ORM-зависимости). |
| `published_at` | `datetime.now(timezone.utc)` — timezone-aware, контракт выполнен. |
| IG в статусе `error` | FB остаётся `queued` (IG может быть retried), не падает в `error`. |

### Критерий приёмки

**Автоматический:** `pytest` — 43 passed.

**Ручной:** опубликовать cast с targets `["ig", "fb"]` → IG-job уходит в `done` → на следующем тике cron-воркера FB-job также переходит в `done`. История появляется в Facebook Stories через Accounts Center (Sharing across profiles включён).

---

## Phase 5 — Аналитика ✓

### Что сделано

- **`GET /casts/{id}/insights`** — переработан из заглушки в полноценный агрегирующий эндпоинт:
  - Возвращает `{ "jobs": [{ "platform", "status", "metrics": { metric: value } }] }`.
  - Агрегация: по каждому `(job_id, metric)` берём снапшот с максимальным `fetched_at` (последнее значение поллера).
  - Если у job нет insights — `metrics: {}` (job включается в ответ, фронт фильтрует визуально).
- **`backend/app/schemas.py`** — добавлены `JobInsightOut` и `CastInsightsOut`.
- **`frontend/src/components/Analytics.jsx`** — обновлён под новый формат `{ jobs }`:
  - Обрабатывает `data.jobs` вместо плоского массива.
  - Вычисляет "reach" из первого найденного ключа `reach / impressions / views / views_count`.
  - Отображает доп. метрики (replies, likes, taps_forward и т.д.) с русскими метками ниже бара.
  - Заглушка "Данные ещё собираются" когда ни у одного job нет метрик.
  - Дизайн сохранён (canvas #E9E7E0, primary #1B3A8F, amber #EC8B2B).
- **`backend/tests/test_analytics_endpoint.py`** — 5 тестов, `AsyncMock` DB, без сети. **48/48 passed.**

### Ключевые решения

| Вопрос | Решение |
|--------|---------|
| Агрегация "последнее значение" | В Python: `dict[(job_id, metric)] → (fetched_at, value)`, один проход по all_insights |
| Jobs без insights | Включаются в ответ с `metrics: {}`; фронт показывает только те, где len(metrics) > 0 |
| Тест без реальной БД | `app.dependency_overrides[get_db] = lambda: mock_db` + `httpx.ASGITransport` — lifespan не триггерится |
| Reach-метрика по платформе | VK: `views`, TG: `views_count`, IG: `reach` — все покрыты списком `REACH_KEYS` в компоненте |

### Критерий приёмки

**GET /casts/{id}/insights** возвращает `{ "jobs": [...] }`, где каждый job содержит последний снапшот метрик. Дашборд Analytics показывает карточки VK / TG / IG с охватом и доп. метриками; если данных нет — заглушка "Данные ещё собираются".

---

## Phase 6 — Мультиарендность ✓

### Что сделано

- **`backend/app/auth.py`** — `get_current_tenant` dependency:
  - Принимает `Authorization: Bearer <supabase_jwt>`.
  - Верифицирует JWT (HS256, audience `authenticated`) через `PyJWT` с ключом `SUPABASE_JWT_SECRET`.
  - По `sub` (Supabase user UUID) ищет `Tenant.owner_uid == uid`.
  - Первый вход → автоматически создаёт tenant (email из JWT в качестве имени).
  - Возвращает `tenant_id: str`.
- **`backend/app/routers/auth.py`** — `GET /auth/me` → `{ tenant_id }`.
- **Все роутеры** (`accounts`, `casts`, `media`) — `settings.DEFAULT_TENANT_ID` заменён на `Depends(get_current_tenant)`. Все эндпоинты требуют валидный JWT.
- **`GET /health`** — публичный, без auth (нужен Render для healthcheck).
- **`backend/app/models.py`** — `Tenant.owner_uid TEXT UNIQUE` (1 пользователь = 1 tenant в MVP).
- **`backend/alembic/versions/0002_add_owner_uid_to_tenants.py`** — миграция: `ALTER TABLE tenants ADD COLUMN owner_uid VARCHAR(255) UNIQUE`.
- **`backend/app/config.py`** — `SUPABASE_JWT_SECRET: str = ""`.
- **`backend/requirements.txt`** — добавлен `PyJWT==2.9.0`.
- **`frontend/src/supabase.js`** — Supabase client (VITE_SUPABASE_URL + VITE_SUPABASE_ANON_KEY).
- **`frontend/src/components/Login.jsx`** — экран входа (email/password → `supabase.auth.signInWithPassword`), дизайн совпадает с приложением.
- **`frontend/src/api.js`** — `request()` автоматически берёт `session.access_token` и добавляет `Authorization: Bearer` ко всем запросам.
- **`frontend/src/App.jsx`** — auth gate: при загрузке проверяет сессию; нет сессии → `<Login />`; есть → приложение. Email пользователя в шапке. Кнопка «Выйти».
- **`frontend/package.json`** — добавлен `@supabase/supabase-js ^2.47.0`.
- **`frontend/.env.example`** — `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`.
- **`.env.example`** — добавлен `SUPABASE_JWT_SECRET`.
- **Тесты:** `tests/test_auth.py` — 5 тестов (valid/existing, valid/auto-provision, bad-signature, expired, wrong-audience). **53/53 passed**.

### Ключевые решения

| Вопрос | Решение |
|--------|---------|
| Auth-провайдер | Supabase Auth — уже используем Supabase, JWT стандартный HS256, верифицируется за 5 строк |
| Связка user→tenant | `Tenant.owner_uid TEXT UNIQUE`: 1 user = 1 tenant (MVP). Команды — Phase 7. |
| Первый вход | Автопровиженинг: если `owner_uid` не найден → создаём tenant, возвращаем его id |
| Cron-воркеры | Напрямую через SQLAlchemy, JWT не нужен — обрабатывают все тенанты |
| GET /health | Без auth — Render healthcheck должен работать без токена |
| Фронт токен | `supabase.auth.getSession()` внутри `request()` — не нужно прокидывать токен вручную |

### Критерий приёмки

1. Зарегистрироваться через Supabase Auth (Dashboard → Authentication → Add user или Supabase JS `signUp`).
2. Войти в UI (Login-экран) — токен выдаётся Supabase JS клиентом.
3. Все запросы проходят с `Authorization: Bearer <token>` — возвращают данные своего tenant.
4. Незалогиненный запрос → 401.
5. `alembic upgrade head` → колонка `owner_uid` добавлена в `tenants`.

### Для деплоя

- Render → Environment → добавить `SUPABASE_JWT_SECRET` (Supabase → Settings → API → JWT Settings).
- Frontend → добавить `VITE_SUPABASE_URL` и `VITE_SUPABASE_ANON_KEY` в Render Static Site / Vercel env vars.
