# Техническое задание: CryptoSignalsBot

Версия: 1.0 · Greenfield · MVP = полный продукт v1

---

## 1. Обзор продукта

**Продукт:** Telegram-бот, который в личные сообщения отправляет алерты о рыночных аномалиях на криптодеривативах (Bybit).

**Аудитория:** активные трейдеры — им нужны конкретные метрики (funding, OI, ликвидации, объём), а не «купи/продай».

**Отличие от конкурентов:** доступная цена + публичный бренд (прозрачность, единый стиль сообщений, открытая политика тарифов).

**Языки:** RU + EN (интерфейс бота, сигналы, уведомления, FAQ-ссылки).

**Доставка:** только приватные DM от бота. Публичный канал не используется.

---

## 2. Тарифы и монетизация

### 2.1 Тарифная сетка

| Тариф | Рынки | Очередь рассылки | Реклама |
|-------|--------|-------------------|---------|
| **Free** | Только BTCUSDT | Низкий приоритет | Да (ручные рассылки админа) |
| **Paid** | Топ-10 USDT linear | Высокий приоритет | Нет |

Один paid-тариф «Полный доступ». Периоды:

| Период | Скидка от базовой месячной цены |
|--------|----------------------------------|
| 1 месяц | 0% |
| 3 месяца | 25% |
| 12 месяцев | 50% |

Цены в **USDT / TON / BTC** — в конфиге (`config/pricing.yaml`), без хардкода в коде.

### 2.2 Оплата

- **Crypto Pay API** (Telegram): создание invoice, webhook/polling статуса, активация подписки.
- Документация: https://help.send.tg/en/articles/10279948-crypto-pay-api

### 2.3 Очередь рассылки (приоритет, не задержка)

**Как это работает:**

1. Signal Engine генерирует **одно** событие сигнала.
2. Фильтруются получатели: тариф, настройки пользователя (вкл/выкл типы, пары).
3. Каждый получатель попадает в очередь Redis с приоритетом:
   - `priority=1` — paid
   - `priority=2` — free
4. Worker отправляет сообщения с учётом лимита Telegram (~25–28 msg/s на бота).
5. Paid получают сигнал **первыми**; free — сразу после, без искусственной паузы.

**При ≤100 пользователях** (ваш масштаб):

| Сценарий | Paid | Free | Время до последнего free |
|----------|------|------|--------------------------|
| 20 paid + 50 free | 20 msg | 50 msg | ~3 с после paid |
| 5 paid + 80 free | 5 msg | 80 msg | ~4 с после paid |

Разница — **секунды**, не минуты. Это и есть «приоритет»: трейдер на paid видит сигнал раньше в ленте, free — чуть позже в той же волне.

**Не делать:** искусственную задержку 10–15 мин для free — это устаревшая модель из раннего README.

**При росте >500 пользователей:** пересмотреть batch size и, при необходимости, добавить soft-delay для free (опционально, v2).

---

## 3. Сигналы

Спецификация порогов, API, cooldown: [MVP_SIGNALS.md](MVP_SIGNALS.md).

### 3.1 Типы (v1)

| # | Тип | Источник |
|---|-----|----------|
| 1 | Funding Extreme | Bybit REST |
| 2 | OI + Price | Bybit REST |
| 3 | Liquidation Spike | Bybit WebSocket |
| 4 | Volume Spike | Bybit REST |

### 3.2 Universe рынков

- Топ-10 linear USDT по `turnover24h`, обновление 00:00 UTC.
- BTCUSDT и ETHUSDT всегда в списке.

### 3.3 Настройки пользователя (Settings)

- Вкл/выкл каждый тип сигнала (default: все вкл).
- Paid: выбор пар из universe (default: все 10).
- Free: только BTCUSDT, настройка пар недоступна.

---

## 4. Telegram-бот (пользовательский функционал)

Стек: **Python 3.11+**, **aiogram 3.x**.

### 4.1 Онбординг

1. `/start`
2. Выбор языка (RU / EN)
3. Принятие оферты и privacy (ссылки telegra.ph) — блокирует доступ без согласия
4. Главное меню (inline)

### 4.2 Главное меню (inline)

| Раздел | Содержание |
|--------|------------|
| **Профиль** | Telegram ID, username, язык, дата регистрации, тариф |
| **Подписка** | Статус, срок, кнопки «Купить» (1/3/12 мес), история платежей |
| **Настройки** | Типы сигналов, пары (paid), язык |
| **FAQ** | Ссылки telegra.ph |
| **Поддержка** | Контакт саппорта (username / email из конфига) |

### 4.3 Уведомления

| Событие | Когда |
|---------|-------|
| Подписка истекает | за 7 дн, 3 дн, 1 дн |
| Подписка истекла | в день окончания |
| Новости | по команде админа (broadcast) |

### 4.4 i18n

- Файлы локализации: `locales/ru.yaml`, `locales/en.yaml`
- Язык сигналов = язык пользователя
- Fallback: EN

---

## 5. Админ (только Telegram-команды)

Доступ: whitelist `ADMIN_TELEGRAM_IDS` в конфиге.

| Команда / действие | Назначение |
|--------------------|------------|
| `/admin` | Меню админа |
| Выдача paid | `grant <user_id> <days>` — тест, промо |
| Отзыв paid | `revoke <user_id>` |
| Broadcast | `broadcast <free\|paid\|all>` + текст (реклама, анонсы) |
| Логи сигналов | последние N сигналов, фильтр по типу/паре |
| Логи collectors | ошибки, последний heartbeat |
| Ban / unban | блокировка пользователя |
| Статистика | активные подписки, free/paid, MRR snapshot |

Все админ-действия пишутся в audit log (БД).

---

## 6. Внутренний аналитический дашборд

**Рекомендация:** **Metabase** + **PostgreSQL** (read-only user).

Почему Metabase:
- Быстрый старт на VPS, SQL поверх вашей БД
- Не нужен отдельный frontend
- Подходит для бизнес-метрик (MRR, conversion, churn)
- Бесплатный, self-hosted в Docker

**Ops-метрики** (uptime collectors, latency Bybit): писать в таблицы `collector_metrics`, `api_latency` из Python; визуализация — те же дашборды Metabase.

### 6.1 Дашборды v1

**Signals**
- Кол-во сигналов по типу / паре / дню
- Распределение confidence (medium/high)

**Business**
- Активные подписчики (free / paid)
- MRR (эквивалент в USDT)
- Conversion free → paid (cohort по неделям)
- Churn (% не продливших за период)

**Operations**
- Collector uptime (% успешных циклов)
- Bybit API latency (p50, p95)
- Очередь рассылки: avg time paid vs free
- Ошибки Telegram API (rate limit, blocked users)

---

## 7. Техническая архитектура

### 7.1 Стек (предложение greenfield)

| Слой | Технология |
|------|------------|
| Bot + handlers | aiogram 3, asyncio |
| Signal collectors | asyncio workers (отдельный процесс) |
| Notification queue | Redis (sorted set / list по priority) |
| БД | PostgreSQL 16 |
| Кэш / cooldown / queue | Redis 7 |
| Миграции | Alembic |
| Config | YAML + env (secrets) |
| Payments | Crypto Pay API (httpx/aiohttp) |
| Analytics UI | Metabase (Docker) |
| Reverse proxy | Caddy или nginx (Metabase + webhook endpoint) |
| Orchestration | Docker Compose |
| Monitoring | healthcheck endpoints + логи в JSON |

### 7.2 Процессы (Docker Compose)

```
┌─────────────────────────────────────────────────────────────┐
│                        VPS (EU North)                        │
├─────────────┬──────────────┬──────────────┬─────────────────┤
│   bot       │  collectors  │  notifier    │  metabase       │
│  (aiogram)  │  (asyncio)   │  (worker)    │  (dashboard)    │
└──────┬──────┴──────┬───────┴──────┬───────┴────────┬────────┘
       │             │              │                │
       └─────────────┴──────────────┴────────────────┘
                          │
              ┌───────────┴───────────┐
              │  PostgreSQL  │  Redis │
              └───────────────────────┘
```

| Сервис | Назначение |
|--------|------------|
| `bot` | Telegram handlers, payments webhook, admin |
| `collectors` | Bybit REST polling + WS liquidations, signal engine |
| `notifier` | Priority queue → Telegram send |
| `postgres` | Persistent data |
| `redis` | Queue, cooldown, session FSM (optional) |
| `metabase` | Internal analytics |

### 7.3 Поток данных

```
Bybit API ──► collectors ──► signal_engine ──► signals (PG)
                                    │
                                    └──► enqueue(notifier, priority)
                                              │
                                              └──► Telegram DM
```

### 7.4 Модель данных (основные сущности)

```
users
  id, telegram_id, username, language, tier (free|paid),
  banned, consented_at, created_at

subscriptions
  id, user_id, plan (1m|3m|12m), starts_at, ends_at,
  source (payment|admin_grant), status

payments
  id, user_id, crypto_pay_invoice_id, amount, currency,
  status, created_at, paid_at

user_signal_settings
  user_id, signal_type, enabled, symbols[] (paid)

signals_log
  id, type, symbol, payload_json, confidence, created_at

delivery_log
  id, signal_id, user_id, priority, sent_at, error

admin_audit
  id, admin_id, action, payload, created_at

collector_metrics
  collector_name, success, latency_ms, error, ts

market_universe
  symbol, rank, active_from, active_to
```

---

## 8. Нефункциональные требования

| Параметр | Значение |
|----------|----------|
| Пользователи | до 100 на старте |
| Регион VPS | Северная Европа (Hetzner FI/SE, или аналог) |
| Доступность | 99% (best effort, один VPS) |
| RTO | < 4 ч (ручной redeploy) |
| Backup БД | daily pg_dump, retention 7 дней |
| Secrets | env vars, не в git |
| Логи | structured JSON, rotation 14 дней |

---

## 9. Юридическое и контент

| Элемент | Формат |
|---------|--------|
| Privacy policy | telegra.ph (RU + EN версии) |
| Public offer | telegra.ph (RU + EN) |
| FAQ | telegra.ph (RU + EN) |
| Disclaimer в каждом сигнале | «Не финансовая рекомендация» |

Согласие обязательно до первого сигнала и до оплаты.

---

## 10. Конфигурация

```
config/
  pricing.yaml      # цены 1m/3m/12m в USDT, TON, BTC
  signals.yaml      # пороги из MVP_SIGNALS.md
  app.yaml          # admin ids, support contact, telegra.ph urls
.env                # BOT_TOKEN, DATABASE_URL, REDIS_URL,
                    # CRYPTO_PAY_TOKEN, WEBHOOK_SECRET
```

---

## 11. План реализации (MVP = v1)

Все перечисленные фичи входят в первый релиз. Оценка: **6–8 недель** (1 разработчик).

### Sprint 1 (1–1.5 нед): Фундамент
- [ ] Docker Compose, PostgreSQL, Redis
- [ ] Alembic, модели users / subscriptions
- [ ] aiogram: /start, язык, согласие, главное меню
- [ ] i18n RU/EN

### Sprint 2 (1.5 нед): Сигналы
- [ ] Collectors: funding, OI, volume (REST)
- [ ] Liquidation WS listener
- [ ] Signal engine + cooldown + signals_log
- [ ] Market universe job

### Sprint 3 (1 нед): Рассылка
- [ ] Priority queue (Redis)
- [ ] Notifier worker
- [ ] User settings (типы, пары)
- [ ] Фильтрация free (BTC) / paid (top-10)

### Sprint 4 (1 нед): Монетизация
- [ ] Crypto Pay: invoice, webhook
- [ ] Планы 1m/3m/12m, активация подписки
- [ ] Экран «Подписка» + история платежей
- [ ] Уведомления об истечении

### Sprint 5 (1 нед): Админ
- [ ] Admin commands: grant/revoke, ban, broadcast
- [ ] Логи сигналов и collectors
- [ ] Admin audit log
- [ ] Статистика в боте (краткая)

### Sprint 6 (0.5–1 нед): Аналитика
- [ ] collector_metrics, api_latency
- [ ] Metabase setup + дашборды (signals, business, ops)
- [ ] delivery_log для метрик очереди

### Sprint 7 (0.5 нед): Контент и polish
- [ ] FAQ / support / telegra.ph links
- [ ] Тестирование на staging
- [ ] Production deploy EU VPS

---

## 12. Структура репозитория (предложение)

```
CryptoSignalsBot/
├── bot/
│   ├── handlers/       # user, admin, payments
│   ├── keyboards/
│   ├── middlewares/
│   └── main.py
├── collectors/
│   ├── funding.py
│   ├── open_interest.py
│   ├── liquidations.py
│   ├── volume.py
│   └── universe.py
├── engine/
│   ├── signal_engine.py
│   └── rules/
├── notifier/
│   └── worker.py
├── db/
│   ├── models/
│   └── migrations/
├── locales/
│   ├── ru.yaml
│   └── en.yaml
├── config/
│   ├── pricing.yaml
│   ├── signals.yaml
│   └── app.yaml
├── docker-compose.yml
├── docs/
│   ├── MVP_SIGNALS.md
│   └── PRODUCT_SPEC.md
└── README.md
```

---

## 13. Риски и митигация

| Риск | Митигация |
|------|-----------|
| Rate limit Telegram | Priority queue, backoff, delivery_log errors |
| Bybit API downtime | Retry, alert в admin, skip cycle |
| Crypto Pay webhook miss | Polling fallback каждые 5 min |
| Пользователь заблокировал бота | Помечать в delivery_log, не retry |
| Мало paid при старте | Grant promo, публичный бренд, прозрачные цены |

---

## 14. Открытые решения (зафиксировать до Sprint 4)

1. **Базовая месячная цена** в USDT (остальное из скидок считается автоматически).
2. **Webhook vs polling** для Crypto Pay (рекомендация: webhook + nginx/Caddy).
3. **Точные URL** telegra.ph для оферты, privacy, FAQ (RU + EN).
4. **Список ADMIN_TELEGRAM_IDS**.

---

## 15. Связанные документы

- [README.md](../README.md) — обзор продукта
- [MVP_SIGNALS.md](MVP_SIGNALS.md) — детали сигналов, пороги, API
