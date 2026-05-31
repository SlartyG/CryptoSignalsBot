# Запуск CryptoSignalsBot с нуля

Инструкция для **production на VPS**.  
Локальная разработка на Mac: [DEV_MAC.md](DEV_MAC.md).  
Предполагается, что кода на компьютере нет — всё делается на сервере через SSH.

**Время:** 1–2 часа при первом запуске.

**Минимальный VPS:** 2 vCPU, 4 GB RAM, Ubuntu 22.04 (Hetzner, Timeweb, DigitalOcean и т.п.).

---

## Что получится в итоге

На сервере будут работать:

- **bot** — Telegram-бот (ответы, оплата, админ)
- **worker** — сбор сигналов Bybit и рассылка в личку
- **postgres** + **redis** — база и очередь

Metabase (аналитика) — опционально, можно подключить позже.

---

## Шаг 0. Чеклист «что подготовить»

| # | Что | Обязательно? |
|---|-----|--------------|
| 1 | VPS с Ubuntu, root или sudo | Да |
| 2 | SSH-доступ к VPS (IP + пароль или ключ) | Да |
| 3 | Ссылка на GitHub-репозиторий | Да |
| 4 | Telegram-бот (токен от @BotFather) | Да |
| 5 | Ваш Telegram ID (для админки) | Да |
| 6 | Telegram-канал(ы) для free-пользователей | Да*, если нужна проверка подписки |
| 7 | Crypto Pay токен (@CryptoBot → Crypto Pay) | Для приёма оплаты |
| 8 | Статьи на telegra.ph (оферта, privacy, FAQ) | Желательно до prod |

\* Если каналы не нужны — в конфиге можно отключить проверку (см. шаг 8).

---

## Шаг 1. Создайте Telegram-бота

1. Откройте Telegram, найдите **@BotFather**.
2. Отправьте `/newbot`.
3. Придумайте имя и username (должен заканчиваться на `bot`, например `MySignalsBot`).
4. BotFather пришлёт **токен** вида `7123456789:AAH...` — **сохраните**, это `BOT_TOKEN`.

Дополнительно в BotFather (рекомендуется):

- `/setdescription` — описание бота
- `/setabouttext` — короткий текст «О боте»

---

## Шаг 2. Узнайте свой Telegram ID

1. Напишите боту **@userinfobot** или **@getmyid_bot**.
2. Он пришлёт ваш **Id** — число, например `123456789`.  
   Это значение для `ADMIN_TELEGRAM_IDS` (вы будете админом).

---

## Шаг 3. Crypto Pay (если нужна оплата)

1. Откройте **@CryptoBot** → **Crypto Pay** → создайте приложение.
2. Скопируйте **API Token** — это `CRYPTO_PAY_TOKEN`.

Без токена бот всё равно запустится, но кнопки «Купить подписку» выдадут ошибку.  
Paid можно выдавать вручную: `/grant <telegram_id> <дней>`.

---

## Шаг 4. Подключитесь к VPS

На **вашем компьютере** (Mac/Linux/Windows с терминалом):

```bash
ssh root@ВАШ_IP_СЕРВЕРА
```

Пример: `ssh root@95.217.123.45`

При первом входе система спросит подтверждение — напишите `yes`.

Дальше все команды выполняются **на сервере**, если не указано иное.

---

## Шаг 5. Установите Docker

```bash
apt update
apt install -y docker.io docker-compose-plugin git nano
```

Проверка:

```bash
docker --version
docker compose version
```

---

## Шаг 6. Скачайте проект с GitHub

```bash
cd /opt
git clone https://github.com/ВАШ_ЛОГИН/CryptoSignalsBot.git
cd CryptoSignalsBot
```

**Если репозиторий приватный:**

1. На GitHub: Settings → Developer settings → Personal access tokens → создайте token с правом `repo`.
2. На сервере:

```bash
git clone https://ВАШ_ЛОГИН:ВАШ_TOKEN@github.com/ВАШ_ЛОГИН/CryptoSignalsBot.git
```

---

## Шаг 7. Создайте файл `.env`

```bash
cp .env.example .env
nano .env
```

Заполните **все строки** (пример — подставьте свои значения):

```env
BOT_TOKEN=7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
CRYPTO_PAY_TOKEN=
ADMIN_TELEGRAM_IDS=123456789
POSTGRES_PASSWORD=MyStr0ngP@ssw0rd2024
```

Важно:

- **`BOT_TOKEN`** — без кавычек, без пробелов вокруг `=`.
- **`ADMIN_TELEGRAM_IDS`** — ваш ID из шага 2.
- **`POSTGRES_PASSWORD`** — придумайте пароль; `DATABASE_URL` и `REDIS_URL` для VPS **можно не писать** — Docker Compose подставит их сам.

Проверка файла:

```bash
grep BOT_TOKEN .env
cat .env
```

Сохранить в nano: `Ctrl+O`, Enter, выход: `Ctrl+X`.

---

## Шаг 8. Настройте `config/app.yaml`

```bash
nano config/app.yaml
```

### 8.1. Каналы для free (подписка при старте)

```yaml
required_channels:
  - id: "@my_signals_channel"
    title: "Наш канал сигналов"
    url: "https://t.me/my_signals_channel"
```

**Обязательно после деплоя:**

1. Создайте канал в Telegram (или используйте существующий).
2. Добавьте **вашего бота** в канал как **администратора** (можно без лишних прав, но статус admin нужен).
3. `id` — публичный `@username` канала или числовой id `-100...`.

**Отключить проверку каналов** (бот сразу пустит к оферте):

```yaml
required_channels: []
```

### 8.2. Ссылки на документы

Замените заглушки на реальные статьи telegra.ph (или временно оставьте как есть для теста):

```yaml
links:
  offer_ru: "https://telegra.ph/..."
  privacy_ru: "https://telegra.ph/..."
  faq_ru: "https://telegra.ph/..."
  # ... en, ua аналогично
```

### 8.3. Поддержка

```yaml
support_contact: "@your_support_username"
```

---

## Шаг 9. Настройте цены

```bash
nano config/pricing.yaml
```

```yaml
month_usdt: 15      # цена за 1 месяц в USDT
month_ton: 0        # 0 = не используется, считается из USDT
month_btc: 0

discounts:
  3m: 0.25          # скидка 25% на 3 месяца
  12m: 0.50         # скидка 50% на год
```

---

## Шаг 10. Запустите бота

```bash
cd /opt/CryptoSignalsBot
docker compose up -d --build
```

При старте контейнеры **сами применяют миграции** (`alembic upgrade head`).

Проверить миграции вручную (опционально):

```bash
docker compose exec bot alembic current
docker compose exec bot printenv BOT_TOKEN
```

`alembic current` должен показать `006_channels_verified (head)` или последнюю ревизию.  
`printenv BOT_TOKEN` — не пустой.

Проверьте, что контейнеры работают:

```bash
docker compose ps
```

Должны быть **Up**: `postgres`, `redis`, `bot`, `worker`.

---

## Шаг 11. Проверьте, что всё живо

Логи бота (ошибок быть не должно, в конце — `Bot starting...`):

```bash
docker compose logs bot --tail 50
```

Логи worker:

```bash
docker compose logs worker --tail 50
```

Должно быть что-то вроде `Worker started`, `Universe refreshed`.

---

## Шаг 12. Пройдите бота в Telegram

1. Найдите бота по username из BotFather.
2. Нажмите **Start** / `/start`.
3. Выберите язык.
4. Если настроены каналы — подпишитесь, нажмите **«Проверить подписку»**.
5. Примите оферту.
6. Должно открыться **главное меню**.

Вы как админ можете проверить:

```
/admin
/stats
```

---

## Шаг 13. Проверка сигналов (может занять время)

Сигналы не приходят каждую минуту — только при аномалиях на Bybit.

- Free-пользователь получает только **BTC**.
- Paid — топ-10 пар (нужна подписка или `/grant`).

Выдать себе paid на 30 дней для теста:

```
/grant ВАШ_TELEGRAM_ID 30
```

(Команду пишете боту в личку, будучи в `ADMIN_TELEGRAM_IDS`.)

---

## Шаг 14. Metabase (аналитика, можно позже)

Когда бот уже работает:

```bash
docker compose --profile analytics up -d metabase
```

Подключите SQL-views:

```bash
docker compose exec -T postgres psql -U app -d cryptobot < docs/sql/analytics_views.sql
```

Откройте в браузере: `http://IP_СЕРВЕРА:3000`  
**Не оставляйте порт 3000 открытым для всего интернета** — закройте firewall или настройте VPN.

---

## Шаг 15. Бэкапы (рекомендуется)

```bash
mkdir -p /backups
crontab -e
```

Добавьте строку:

```cron
0 3 * * * cd /opt/CryptoSignalsBot && docker compose exec -T postgres pg_dump -U app cryptobot | gzip > /backups/cryptobot_$(date +\%Y\%m\%d).sql.gz
```

---

## Как обновить бота после изменений в GitHub

```bash
cd /opt/CryptoSignalsBot
git pull
docker compose up -d --build
docker compose exec bot alembic upgrade head
```

---

## Частые проблемы

### `BOT_TOKEN is not set`

Файл `.env` на VPS пустой или без токена:

```bash
nano /opt/CryptoSignalsBot/.env
# добавьте: BOT_TOKEN=7123...:AAH...
docker compose up -d --force-recreate bot worker
docker compose exec bot printenv BOT_TOKEN
```

### `relation "collector_metrics" does not exist`

Не применены миграции 002+:

```bash
docker compose exec bot alembic upgrade head
docker compose exec bot alembic current
docker compose restart worker
```

### Бот не отвечает

```bash
docker compose logs bot --tail 100
```

- Проверьте `BOT_TOKEN` в `.env`.
- Перезапуск: `docker compose restart bot`.

### «Вы не подписаны на канал»

- Бот добавлен в канал как **администратор**?
- В `config/app.yaml` правильный `@username` канала?
- Вы реально подписались на **все** каналы из списка?

### Нет сигналов в личку

```bash
docker compose logs worker --tail 100
```

- Worker должен быть Up.
- Для free — только BTC, события на рынке могут быть редкими.
- Вы прошли онбординг до конца (оферта принята)?

### Ошибка при `docker compose up`

- Мало RAM? Нужно минимум 4 GB.
- Занят порт? `docker compose ps`, проверьте конфликты.

### Забыли пароль PostgreSQL

Он только в `.env`. Если меняете — нужно совпадение в `POSTGRES_PASSWORD` и `DATABASE_URL`.

---

## Краткая шпаргалка команд

| Действие | Команда |
|----------|---------|
| Статус | `docker compose ps` |
| Логи бота | `docker compose logs -f bot` |
| Логи worker | `docker compose logs -f worker` |
| Перезапуск всего | `docker compose restart` |
| Остановить | `docker compose down` |
| Запустить снова | `docker compose up -d` |

---

## Минимальный путь «запустить за 15 минут»

Если нужно просто увидеть работающего бота:

1. VPS + SSH  
2. Docker + git clone  
3. `.env` с `BOT_TOKEN`, `ADMIN_TELEGRAM_IDS`, паролем БД  
4. `required_channels: []` в `app.yaml`  
5. `docker compose up -d --build`  
6. `docker compose exec bot alembic upgrade head`  
7. `/start` в Telegram  

Оплату, каналы, telegra.ph и Metabase — докрутите перед публичным запуском.
