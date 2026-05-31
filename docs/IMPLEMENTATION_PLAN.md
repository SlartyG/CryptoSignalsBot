# План реализации CryptoSignalsBot

Пошаговый план для реализации v1 на **одном VPS** (Docker Compose).

**Статус:** MVP implementation complete. Deploy with [DEPLOY.md](DEPLOY.md).

---

## Phase 0: Документация ✅

- [x] PRODUCT_SPEC.md
- [x] MVP_SIGNALS.md
- [x] IMPLEMENTATION_PLAN.md
- [x] DEPLOY.md
- [x] docs/sql/analytics_views.sql

---

## Phase 1: Фундамент ✅

- [x] Docker Compose, PostgreSQL, Redis, bot, worker
- [x] SQLAlchemy models, Alembic migrations 001–005
- [x] aiogram: /start, язык, согласие, меню
- [x] i18n RU/EN/UA

---

## Phase 2: Сигналы ✅

- [x] Bybit client, collectors (funding, OI, volume, liquidations WS)
- [x] Signal engine, cooldown, signals_log, collector_metrics
- [x] market_universe job

---

## Phase 3: Рассылка ✅

- [x] Redis priority queue, notifier worker
- [x] delivery_log, recipient filtering, message formatter

---

## Phase 4: Личный кабинет ✅

- [x] Profile, Settings (types + pairs), Subscription UI
- [x] locales/ua.yaml

---

## Phase 5: Монетизация ✅

- [x] payments model, Crypto Pay, plan selection
- [x] Payment poller in worker, subscription reminders

---

## Phase 6: Админ ✅

- [x] /admin commands: grant, revoke, ban, broadcast, logs, stats
- [x] admin_audit

---

## Phase 7: Аналитика ✅

- [x] SQL views for Metabase
- [x] Metabase in docker-compose profile `analytics`

---

## Phase 8: Deploy ✅

- [x] DEPLOY.md + smoke checklist

---

## Быстрый старт

```bash
cp .env.example .env
docker compose up -d postgres redis
pip install -r requirements.txt
alembic upgrade head
python -m bot.main          # terminal 1
python -m worker.main         # terminal 2
```

Production: см. [DEPLOY.md](DEPLOY.md).
