# Кратко, что сделано (день 2)

- Подключение к удалённым БД через `.env`: Postgres, MongoDB, Redis, Qdrant, Neo4j (RabbitMQ пока не трогаем).
- Скрипт `scripts/check_connections.py` проверяет все сервисы (RabbitMQ сейчас не подключается, это нормально).
- Скрипт `scripts/mongo_show_db.py` показывает базы/коллекции в Mongo.
- API (FastAPI) поднято в `api/`:
  - Запуск: `./.venv/bin/uvicorn api.main:app --reload --port 8000`
  - Эндпойнты: `/health`, `/ping`, `POST /notes`, `GET /notes/{id}`, `GET /notes?q=...&limit=&offset=`.
  - Таблица в Postgres создаётся автоматически на старте как `notes_<student>` (имя студента берётся из `STUDENT_NAME` в нижнем регистре).
  - Дата в ответах теперь `datetime`, не строки (исправлено).

Сейчас работает:
- Подключения к Postgres/Mongo/Redis/Qdrant/Neo4j ок (см. последний запуск check_connections).
- CRUD по заметкам в Postgres работает после фикса схемы ответа.

Доступные функции (эндпойнты):
- GET /health — статус сервера, имя студента, хосты сервисов из .env.
- GET /ping — простая проверка «живости».
- POST /notes — создать заметку (title, content, tags?), пишет в Postgres, возвращает созданную запись.
- GET /notes/{id} — получить заметку по id из Postgres.
- GET /notes?q=...&limit=&offset= — список заметок, либо поиск по подстроке в title/content (ILIKE), с пагинацией.
- PUT /notes/{id} — обновить заметку (title/content/tags) в Postgres, пишет новую версию в Mongo.
- GET /notes/{id}/versions — версии заметки из Mongo (последние, по убыванию версии).
- POST /notes/{id}/restore — восстановить заметку из указанной версии (берёт снапшот из Mongo, пишет в Postgres, создаёт новую версию).
- GET /notes/popular?limit=10 — топ заметок по просмотрам (счётчики в Redis).

Что дальше (предлагаемое):
- Добавить сохранение версий заметок в Mongo при создании/обновлении.
- Добавить Redis-кэш для `GET /notes/{id}`.
- Подготовить заглушку для RabbitMQ/worker или пропустить до появления сервиса.

Как работает API сейчас:
- `main.py` — входная точка FastAPI. При старте читает `.env`, создаёт таблицу в Postgres (если её нет), подключает маршруты и служебные ручки `/health` и `/ping`.
- `routes.py` — описывает HTTP-ручки `/notes`: создать, получить по id, список/поиск, обновить, показать версии, восстановить из версии. Делегирует операции в `db.py` и `mongo_versions.py`.
- `db.py` — общение с Postgres. Собирает имя базы и таблицы с суффиксом `STUDENT_NAME` (нижний регистр), создаёт таблицу с триггером на `updated_at` и GIN-индексом. Функции: `insert_note`, `fetch_note`, `search_notes`, `update_note`.
- `mongo_versions.py` — хранение версий в Mongo: `save_version`, `get_versions`, `get_version`, коллекция `note_versions_<student>`.
- `cache.py` — работа с Redis: кэш заметок (key `note:<id>`, TTL по умолчанию 120 c), счётчик популярности в sorted set (`popular_notes`).
- `schemas.py` — Pydantic-схемы. `NoteCreate` валидирует вход (title, content, tags). `NoteUpdate` для изменений. `NoteRestore` для восстановления из версии. `NoteOut` описывает ответ (включая `datetime` для created_at/updated_at).

Как работает кэш и топ в Redis:
- При `GET /notes/{id}` сначала читаем кэш (`note:<id>`). Если нет — берём из Postgres и кладём в кэш (TTL 120 секунд).
- На каждом чтении увеличиваем счётчик популярности в sorted set `popular_notes` (`zincrby`).
- Эндпойнт `GET /notes/popular` читает топ из Redis и пытается вернуть сами заметки (из кэша или БД), вместе с числом просмотров (`score`).
- Переменные окружения, которые влияют: `REDIS_HOST/PORT/DB`, `REDIS_NOTE_TTL` (секунды, по умолчанию 120), `REDIS_POPULAR_KEY` (по умолчанию `popular_notes`).

Как показать (демо):
1) Запусти API: `./.venv/bin/uvicorn api.main:app --reload --port 8000`.
2) Создай 2–3 заметки через `POST /notes`.
3) Сделай несколько запросов `GET /notes/{id}` к разным заметкам (чтобы накрутить просмотры). Повтори одни и те же id несколько раз.
4) Вызови `GET /notes/popular?limit=5` — увидишь список заметок с `score` (кол-во просмотров). Если кэш истёк, заметки подтянутся из БД, но счётчики останутся в Redis.
