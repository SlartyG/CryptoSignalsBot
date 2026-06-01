## Бот крипто-сигналов

Идея - бот анализирует ситуацию на крипторынке иотправляет сигналы о важных событиях. 

### Что за сигналы?
Бот отправляет **алерты о рыночных аномалиях**, а не прямые указания «купи/продай». Данные — публичное API Bybit (V5), топ-100 USDT-пар по объёму (список обновляется раз в сутки).

**MVP (4 типа сигналов):**

| Сигнал | Суть |
|--------|------|
| Funding Extreme | Экстремальный funding rate — перекос long/short на перпах |
| OI + Price | Изменение open interest вместе с движением цены |
| Liquidation Spike | Крупный всплеск ликвидаций за короткое окно |
| Volume Spike | Объём часовой свечи сильно выше нормы |

Подробности — пороги, API endpoints, cooldown, архитектура: [docs/MVP_SIGNALS.md](docs/MVP_SIGNALS.md).

План реализации: [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md).

### Быстрый старт (разработка)

Подробно для Mac: [docs/DEV_MAC.md](docs/DEV_MAC.md).

```bash
cp .env.example .env   # BOT_TOKEN, ADMIN_TELEGRAM_IDS; DATABASE_URL с localhost
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres redis
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m bot.main      # terminal 1
python -m worker.main   # terminal 2
```

Production: [docs/DEPLOY.md](docs/DEPLOY.md)

**Тарифы:** free — 10 базовых рынков, задержка доставки 1 мин, подписка на каналы при старте; paid — до 100 рынков (по умолчанию 10), мгновенная доставка. Доставка — только в личные сообщения бота.

### Монетизация
Подписочная модель ($25/мес). Один paid-тариф: 1 мес / 3 мес (−25%) / 12 мес (−50%). Оплата USDT, TON, BTC через Crypto Pay API.

Полное ТЗ: [docs/PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md).

### Платежка 
Crypto Pay API в тг. 
Документация https://help.send.tg/en/articles/10279948-crypto-pay-api

### Данные
PostgreSQL (пользователи, подписки, платежи, логи сигналов) + Redis (очередь, cooldown).

### Мониторинг
Внутренний дашборд Metabase (сигналы, MRR, conversion, uptime collectors).

### Админ-функционал
Админ-фичи для тестирвоания и кастомных доступов. Рассылки

### Личный кабинет
Профиль пользователя с его данными и его подпиской

### FAQ и поддержка
Блок с частыми вопросами (формат статьи в telegra.ph) и контакты саппорта

### Документы
Согласие с политикой конфидекциальности и публичной оффертой при старте. Документы - формат статьи в telegra.ph

### Уведомления
Истечение подписки (напоминание за неделю, три дня, день), новости 

## Мультиязычность 
RU + EN + UA (интерфейс, сигналы, уведомления).
