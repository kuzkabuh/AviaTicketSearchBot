# AviaTicketSearchBot

Асинхронный Telegram-бот для поиска авиабилетов через реальные эндпоинты Aviasales / Travelpayouts API.

## Что внутри

- `aiogram 3.x` и `Router` для команд и сообщений.
- FSM (`FSMContext`) для сценариев поиска: откуда → куда → дата → количество билетов.
- Поиск пункта отправления и назначения по IATA-коду, названию города или аэропорта.
- Inline-выбор локации при неоднозначном вводе, например `Москва` → `MOW`, `SVO`, `DME`, `VKO`, `ZIA`.
- Вывод нескольких разных вариантов перелета с подробной информацией и кнопкой подписки.
- SQLite-хранилище подписок и защита от дублей активных подписок.
- Фоновая проверка изменения цены и уведомления пользователю.
- Раздел `🔔 Мои подписки` с ручной проверкой и удалением подписок.

## Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Заполните `.env`:

```env
BOT_TOKEN=ваш_telegram_токен
TRAVELPAYOUTS_TOKEN=ваш_travelpayouts_токен
MARKER=ваш_маркер_если_есть
CURRENCY=rub
DATABASE_PATH=avia_bot.sqlite3
TICKET_RESULTS_LIMIT=5
MIN_TICKET_RESULTS=5
PRICE_TRACKING_ENABLED=true
PRICE_CHECK_INTERVAL_MINUTES=60
SUBSCRIPTION_NOT_FOUND_NOTIFY_INTERVAL_HOURS=24
DUPLICATE_NOTIFICATION_COOLDOWN_MINUTES=30
```

Запуск:

```bash
python main.py
```

При старте бот автоматически создаст таблицу `subscriptions`. SQL-миграция для ручного применения находится в `migrations/001_create_subscriptions.sql`.

## Команды

- `/start` — приветствие и кнопки быстрого запуска.
- `/help` — справка по формату ввода.
- `/search` — пошаговый поиск билетов по городу, аэропорту или IATA-коду.
- `/popular` — популярные направления из выбранного города.
- `/subscriptions` — просмотр и управление подписками.
- `/cancel` — отмена текущего FSM-сценария.

## Сценарий поиска

1. Пользователь запускает `/search` или кнопку `🔎 Найти билет`.
2. Бот спрашивает пункт отправления: город, аэропорт или IATA-код.
3. Если найдено несколько вариантов, бот показывает inline-кнопки выбора.
4. Бот спрашивает пункт назначения и при необходимости снова предлагает выбор.
5. Пользователь вводит дату вылета в формате `YYYY-MM-DD`.
6. Бот спрашивает количество билетов и принимает только положительное целое число.
7. Бот показывает до `TICKET_RESULTS_LIMIT` вариантов и кнопку `🔔 Отслеживать цену` для каждого.

## Архитектура

```text
config.py                         # чтение .env и новых настроек
api.py                            # aiohttp-клиент Travelpayouts и нормализация предложений
db.py                             # SQLite-схема и CRUD подписок
main.py                           # Bot, Dispatcher, init DB, routers, price tracking
handlers/start.py                 # /start, /help, /cancel и кнопки меню
handlers/search.py                # FSM поиска, выбор локаций, количество билетов, выдача вариантов
handlers/subscriptions.py         # создание, просмотр, ручная проверка и удаление подписок
services/locations.py             # справочник и поиск городов/аэропортов
services/tickets.py               # поиск билетов и сопоставление рейса подписки
services/subscriptions.py         # бизнес-логика подписок и проверки цены
services/price_tracking.py        # фоновая периодическая проверка цен
states/search_states.py           # состояния TicketSearchState и PopularDirectionState
keyboards/inline.py               # inline-клавиатуры
utils/validators.py               # проверка дат, IATA и количества билетов
utils/formatters.py               # форматирование билетов, подписок и уведомлений
migrations/001_create_subscriptions.sql # SQL-схема подписок
```
