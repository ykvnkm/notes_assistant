# Notes Assistant (multi-DB demo)

Веб-API и веб-обёртка для заметок, показывающие работу сразу с несколькими хранилищами и очередью задач.

## Идея
- CRUD заметок с кэшем и счётчиком популярности.
- Версионирование заметок (MongoDB) и откат к версии.
- Векторный поиск похожих заметок (Qdrant).
- Граф связей «заметка ↔ тег» (Neo4j) и выборка по тегам.
- События о CRUD заметок в RabbitMQ.

## Архитектура
- **FastAPI** (директория `api/`) — один сервис, подключается ко всем БД и очереди.
- **БД/сервисы:**
  - Postgres — основное хранилище заметок.
  - MongoDB — версии заметок.
  - Redis — кэш заметок и счётчик популярности.
  - Qdrant — векторный поиск похожих заметок.
  - Neo4j — граф тегов/заметок.
  - RabbitMQ — события `note_created/updated/deleted`.
- **Веб-UI** (`web/index.html`) — страница с карточками для всех запросов.

## Структура
- `api/` — код сервиса: `main.py`, `routes.py`, `db.py`, `mongo_versions.py`, `cache.py`, `qdrant_vectors.py`, `graph.py`, `queue.py`, `schemas.py`, `__init__.py`.
- `web/` — веб-обёртка (статические файлы, точка входа `index.html`).
- `scripts/` — утилиты:
  - `check_connections.py` — проверка всех сервисов из `.env`.
  - `consume_queue.py` — простой консюмер RabbitMQ для просмотра событий.
  - `qdrant_inspect.py` — инспекция коллекций/точек Qdrant.
- `docker-compose.yml` — локальный стенд (если нужен).
- `.env.example` — шаблон переменных окружения.
- `requirements.txt` — зависимости.

## Эндпойнты и функционал
- **Заметки (Postgres + Redis):**
  - `POST /notes` — создать заметку (кэшируется, идёт в очередь, Qdrant, Neo4j).
  - `GET /notes/{id}` — получить (кэш + инкремент популярности).
  - `PUT /notes/{id}` — обновить (кэш, версия в MongoDB, Qdrant, Neo4j, очередь).
  - `DELETE /notes/{id}` — удалить (чистит кэш, версии, Qdrant, Neo4j, очередь).
  - `GET /notes?q=&limit=&offset=` — список/поиск (ILIKE по title/content).
  - `GET /notes/popular` — топ по просмотрам (Redis sorted set).
- **Версии (MongoDB):**
  - `GET /notes/{id}/versions` — посмотреть версии.
  - `POST /notes/{id}/restore` — откат к версии (создаёт новую версию).
- **Похожие (Qdrant):**
  - `GET /notes/{id}/similar?limit=` — возвращает исходную заметку и список похожих.
- **Теги (Neo4j):**
  - `GET /tags?limit=` — список тегов.
  - `GET /graph/tags/{tag}?limit=` — заметки с этим тегом (детали из Postgres).
- **События (RabbitMQ):**
  - При create/update/delete публикуется `{action, note}` в очередь `notes_tasks_<student>` (или `RABBITMQ_QUEUE`).

## Переменные окружения (основные)
- `STUDENT_NAME` — суффикс для таблиц/коллекций/очереди по умолчанию.
- Postgres: `POSTGRES_HOST/PORT/USER/PASSWORD/DB`.
- Mongo: `MONGO_HOST/PORT/USER/PASSWORD/DB`, `MONGO_AUTH_SOURCE`.
- Redis: `REDIS_HOST/PORT/DB`, `REDIS_NOTE_TTL`, `REDIS_POPULAR_KEY`.
- Qdrant: `QDRANT_HOST/PORT`, `QDRANT_COLLECTION` (или `notes_vectors_<student>`), `QDRANT_VECTOR_SIZE`.
- Neo4j: `NEO4J_HOST/PORT/USER/PASSWORD`.
- RabbitMQ: `RABBITMQ_HOST/PORT/USER/PASSWORD`, `RABBITMQ_QUEUE` (или `notes_tasks_<student>`).

## Запуск
1) Скопировать конфиг и заполнить:
   ```bash
   cp .env.example .env
   # указать STUDENT_NAME и хост/порты сервисов
   ```
2) Установить зависимости:
   ```bash
   pip install -r requirements.txt
   ```
3) (Опционально) проверить подключения:
   ```bash
   python scripts/check_connections.py
   ```
4) Запустить API:
   ```bash
   uvicorn api.main:app --reload --port 8000
   ```
5) Веб-UI: открыть `http://localhost:8000/web/` и использовать карточки для всех запросов.
6) RabbitMQ консюмер (для просмотра событий):
   ```bash
   python scripts/consume_queue.py
   ```
