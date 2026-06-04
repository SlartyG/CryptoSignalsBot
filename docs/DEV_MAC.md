# Локальная разработка на macOS

Инструкция для запуска CryptoSignalsBot **на Mac** — код на машине, PostgreSQL и Redis в Docker.

Production-деплой на VPS: [DEPLOY.md](DEPLOY.md).

---

## Что понадобится

| Инструмент | Зачем |
|------------|--------|
| **macOS** 12+ | — |
| **Git** | клонировать репозиторий |
| **Docker Desktop** | PostgreSQL + Redis в контейнерах |
| **Python 3.11+** | bot и worker |
| **Telegram-бот** | токен от @BotFather |

Установка недостающего через [Homebrew](https://brew.sh):

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install git python@3.11
brew install --cask docker
```

После установки Docker Desktop — **запустите приложение** (иконка кита в menu bar).

Проверка:

```bash
git --version
python3 --version    # нужен 3.11+
docker compose version
```

---

## Шаг 1. Клонировать проект

```bash
cd ~/Projects   # или любая папка
git clone https://github.com/ВАШ_ЛОГИН/CryptoSignalsBot.git
cd CryptoSignalsBot
```

---

## Шаг 2. Виртуальное окружение Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

При каждом новом терминале перед работой:

```bash
cd ~/Projects/CryptoSignalsBot
source .venv/bin/activate
```

---

## Шаг 3. Файл `.env`

```bash
cp .env.example .env
```

Откройте `.env` в редакторе и заполните:

```env
BOT_TOKEN=7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ADMIN_TELEGRAM_IDS=123456789
POSTGRES_PASSWORD=app

# Важно для Mac: localhost, не postgres!
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/cryptobot
REDIS_URL=redis://localhost:6379/0

# Опционально — для теста оплаты
CRYPTO_PAY_TOKEN=
XROCKET_PAY_TOKEN=
```

| Переменная | Откуда |
|------------|--------|
| `BOT_TOKEN` | @BotFather → `/newbot` |
| `ADMIN_TELEGRAM_IDS` | @userinfobot → ваш Id |
| `DATABASE_URL` | Собираете сами: пользователь `app`, пароль = `POSTGRES_PASSWORD`, хост **`localhost`** (бот на Mac, БД в Docker) |
| `REDIS_URL` | `redis://localhost:6379/0` |

> **Почему `localhost`, а не `postgres`?**  
> `postgres` — имя контейнера внутри Docker-сети. Python у вас запускается **на Mac**, поэтому хост — `localhost`, а порты проброшены через `docker-compose.dev.yml`.

---

## Шаг 4. Конфиг для удобной разработки

### Каналы — отключить на время отладки

В `config/app.yaml`:

```yaml
required_channels: []
```

Иначе нужен реальный канал и бот-админ в нём.

### Цены и ссылки

- `config/pricing.yaml` — цены подписки  
- `config/app.yaml` — telegra.ph, support (можно оставить заглушки)

---

## Шаг 5. Запустить PostgreSQL и Redis

Из корня проекта:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres redis
```

Проверка:

```bash
docker compose ps
```

Оба сервиса в статусе **Up**. Порты `5432` и `6379` доступны на Mac.

Остановить:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml down
```

Данные БД сохраняются в Docker volume `pgdata`. Полный сброс:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml down -v
```

---

## Шаг 6. Миграции базы

```bash
source .venv/bin/activate
alembic upgrade head
```

При ошибке подключения — проверьте `DATABASE_URL` (`localhost`) и что postgres запущен.

---

## Шаг 7. Запуск bot и worker

Нужны **два терминала** (в обоих — `source .venv/bin/activate`).

**Терминал 1 — бот:**

```bash
python -m bot.main
```

В логе: `Bot starting...`

**Терминал 2 — worker (сигналы + рассылка):**

```bash
python -m worker.main
```

В логе: `Worker started`, `Universe refreshed`.

В Telegram откройте бота → `/start`.

---

## Шаг 8. Быстрые проверки

| Действие | Как |
|----------|-----|
| Админ-меню | `/admin` |
| Выдать себе paid | `/grant ВАШ_TELEGRAM_ID 30` |
| Статистика | `/stats` |
| Логи worker | смотреть терминал 2 |

Сигналы приходят не постоянно — только при срабатывании правил Bybit. Free — **10 базовых** пар, задержка доставки ~1 мин; paid — до 100 пар.

---

## Альтернатива: всё в Docker (как на VPS)

Если не хотите venv на Mac — поднимите bot и worker тоже в контейнерах:

```bash
cp .env.example .env
# заполните BOT_TOKEN, ADMIN_TELEGRAM_IDS, POSTGRES_PASSWORD
# DATABASE_URL можно не трогать — compose подставит postgres:5432 сам

docker compose up -d --build
docker compose exec bot alembic upgrade head
docker compose logs -f bot worker
```

В этом режиме `DATABASE_URL` с хостом `postgres` — правильный (внутри Docker-сети).

---

## Metabase локально (опционально)

```bash
docker compose --profile analytics up -d metabase
docker compose exec -T postgres psql -U app -d cryptobot < docs/sql/analytics_views.sql
```

Откройте http://localhost:3000

---

## Полезные команды

```bash
# Новая миграция после изменения моделей
alembic revision --autogenerate -m "описание"
alembic upgrade head

# Подключиться к БД вручную
docker compose exec postgres psql -U app -d cryptobot

# Redis CLI
docker compose exec redis redis-cli

# Пересборка после изменения requirements.txt
pip install -r requirements.txt
```

---

## Частые проблемы на Mac

### `Connection refused` к PostgreSQL

- Docker Desktop запущен?
- Используете `docker-compose.dev.yml` (проброс портов)?
- В `.env` хост **`localhost`**, не `postgres`.

### Бот молчит

- В `.env` верный `BOT_TOKEN`?
- Только один процесс `bot.main` (второй экземпляр вызовет conflict)?

### `ModuleNotFoundError`

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Запускайте из **корня** репозитория: `python -m bot.main`.

### Порт 5432 занят

На Mac иногда занят локальным PostgreSQL:

```bash
brew services stop postgresql@16   # если ставили через brew
```

Или смените порт в `docker-compose.dev.yml`: `"5433:5432"` и в `.env`: `@localhost:5433/`.

### Apple Silicon (M1/M2/M3)

Docker Desktop и образы работают нативно. Если сборка падает — обновите Docker Desktop.

---

## Отличия dev (Mac) и prod (VPS)

| | Mac (dev) | VPS (prod) |
|---|-----------|------------|
| bot/worker | Python на Mac или Docker | Docker |
| DATABASE_URL | `@localhost:5432` | `@postgres:5432` (в compose) |
| Postgres/Redis | Docker + dev ports | Docker |
| Metabase | опционально | опционально |
| Домен / SSL | не нужен | по желанию |

---

## Шпаргалка «каждый день»

```bash
cd ~/Projects/CryptoSignalsBot
source .venv/bin/activate
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres redis
# терминал 1
python -m bot.main
# терминал 2
python -m worker.main
```

Готово — можно разрабатывать и тестировать в Telegram.
