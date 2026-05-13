# AviaTicketSearchBot

**Версия:** 1.4.0

Асинхронный Telegram-бот на `aiogram 3.x` для поиска авиабилетов, показа нескольких предложений, подписок на изменение цены и администрирования через Telegram.

> Важно: бот использует **Aviasales Data API** от Travelpayouts. Этот API возвращает кешированные данные, сформированные на основе поисков пользователей Aviasales. Это не real-time Flights Search API; перед покупкой пользователь должен проверить итоговую цену по ссылке Aviasales.

## Основные функции

- `/start` — первый запуск с выбором языка RU/EN, затем локализованное главное меню.
- `/search` — пошаговый поиск билетов: откуда → куда → тип поездки → интерактивный календарь → пассажиры → подтверждение.
- Естественный поиск обычной фразой без команды: бот извлекает маршрут, даты, тип поездки и пассажиров.
- Мультиязычность RU/EN через `locales/ru.json` и `locales/en.json`; язык можно менять в настройках.
- Мультивалютность RUB/USD/EUR; валюта и market пользователя передаются в Aviasales Data API.
- Поиск локаций через Aviasales Autocomplete API с `locale=ru/en`, с локальным fallback по IATA-коду, названию города или аэропорта.
- Уточнение локации inline-кнопками при неоднозначном вводе, например `Москва` → `MOW`, `SVO`, `DME`, `VKO`, `ZIA`.
- Вывод нескольких предложений с ценой, временем, пересадками, авиакомпанией, номером рейса и ссылкой Aviasales.
- Просмотр цен рядом с выбранной датой через сгруппированные цены Data API.
- `/popular` — популярные направления из выбранного города.
- `/subscriptions` — подписки на изменение цены, ручная проверка и удаление.
- Фоновая проверка цен по активным подпискам.
- `/admin` — админ-панель: версия, обновления, логи, статистика, пользователи, состояние системы, рестарт, рассылка.

## Aviasales / Travelpayouts API

Проект фиксирует три внешних интеграционных слоя:

1. **Aviasales Data API** — основной источник поиска билетов, дешёвых цен, популярных направлений, календарных цен и фоновых проверок подписок.
2. **Aviasales Autocomplete API** (`https://autocomplete.travelpayouts.com/places2`) — поиск городов и аэропортов по русским/английским названиям и IATA-кодам с передачей `locale`.
3. **Travelpayouts партнёрские ссылки** — монетизация переходов на покупку через Aviasales search URL с marker/market.

Клиент работает с актуальными v3-эндпоинтами Aviasales Data API:

- `/aviasales/v3/prices_for_dates` — основной поиск дешёвых билетов на даты и популярные направления из города (`unique=true`, `sorting=route`).
- `/aviasales/v3/get_latest_prices` — дополнительный источник предложений за период, если основной запрос вернул мало вариантов.
- `/aviasales/v3/grouped_prices` — календарные/сгруппированные цены по датам.
- `/aviasales/v3/get_popular_directions` — сервисная обёртка для входящих популярных направлений к городу.
- `/aviasales/v3/search_by_price_range` — сервисная обёртка для будущего поиска по диапазону цен.

Старые методы `/v1/city-directions`, `/v1/prices/cheap`, `/v1/prices/direct`, `/v1/prices/calendar`, `/v1/prices/monthly`, `/v2/prices/latest` и `/v2/prices/calendar` в коде не используются.

Токен передаётся через заголовок `X-Access-Token`, а не в URL. Для ускорения ответа клиент отправляет `Accept-Encoding: gzip, deflate`.

## Структура проекта

```text
config.py                    # чтение .env и валидация обязательных настроек
api.py                       # совместимый публичный API-клиент Aviasales Data API v3
services/aviasales_api.py     # целевая точка импорта API-клиента для новых модулей
services/location_resolver.py # целевая точка импорта резолвера локаций
services/autocomplete.py      # Aviasales Autocomplete API + локальный fallback
services/i18n.py              # JSON-локализация и пользовательские настройки языка
services/calendar_keyboard.py # интерактивный Telegram-календарь
services/natural_search_parser.py # RU/EN parser естественных поисковых запросов
services/search_models.py     # единая FlightSearchRequest модель
db.py                        # SQLite-схема, миграции на старте и CRUD
main.py                      # entrypoint aiogram-приложения
handlers/                    # пользовательские, поисковые, подписочные и админские хендлеры
keyboards/                   # inline-клавиатуры
services/                    # бизнес-сервисы: обновления, логи, подписки, статистика, система
states/                      # FSM-состояния
utils/                       # валидаторы, форматтеры, admin access, update state
migrations/                  # SQL-миграции для SQLite
update.sh                    # self-update через Git/systemd
install.sh                   # установка на сервер с systemd
logs/                        # runtime-логи при серверном запуске
runtime/                     # lock/status файлы обновления
```

## Быстрый старт локально

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
python main.py
```

Минимально обязательные переменные:

```env
BOT_TOKEN=ваш_telegram_токен
TRAVELPAYOUTS_TOKEN=ваш_travelpayouts_токен
ADMIN_IDS=123456789
```

## Мультиязычность, валюты и умный поиск

При первом `/start` бот предлагает выбрать язык:

- 🇷🇺 Русский → `language_code=ru`, `currency_code=RUB`, `market_code=ru`;
- 🇬🇧 English → `language_code=en`, `currency_code=USD`, `market_code=us`.

Пользователь может изменить язык и валюту в меню **Settings / Настройки**. Поддерживаемые валюты первого этапа: `RUB`, `USD`, `EUR`. Цены форматируются как `12 500 ₽`, `$125`, `€119`.

Пошаговый поиск использует inline-календарь Telegram: нельзя выбрать прошедшую дату, а дата возвращения не может быть раньше даты вылета. После выбора даты вылета можно сразу искать one-way билет или выбрать дату обратного рейса. Количество пассажиров выбирается inline-кнопками `+ / -` для взрослых, детей и младенцев; младенцы сохранены архитектурно для будущих API-возможностей.

Примеры естественных запросов:

```text
Найди мне билеты из Москвы в Казань с 15 мая по 26 мая для 2 взрослых и 1 ребенка
Москва Сочи 20 июня 2 взрослых
Билет из Питера в Ереван на 10 августа
Find flights from Amsterdam to London on July 15 for 1 adult
Tickets from Moscow to Dubai from June 10 to June 20 for 2 adults and 1 child
Search flights Berlin Paris August 3
```

Если бот распознал не все параметры, он спрашивает только недостающий параметр, а не перезапускает весь сценарий. Оба режима собирают единую модель `FlightSearchRequest` с IATA-кодами, display-name, датами, типом поездки, пассажирами, языком, валютой и market.

## Основные настройки `.env`

```env
TRAVELPAYOUTS_BASE_URL=https://api.travelpayouts.com
CURRENCY=rub
MARKET=ru
LOCALE=ru
REQUEST_TIMEOUT=15
API_RETRY_ATTEMPTS=2
DATABASE_PATH=avia_bot.sqlite3
LOG_LEVEL=INFO
BOT_SERVICE_NAME=avia-ticket-search-bot.service
BOT_UPDATE_SCRIPT=/opt/Bots/AviaTicketSearchBot/update.sh
BOT_UPDATE_LOG_PATH=/opt/Bots/AviaTicketSearchBot/logs/update.log
BOT_UPDATE_STATUS_PATH=/opt/Bots/AviaTicketSearchBot/runtime/update_status.json
```

Полный пример находится в `.env.example`.

## Установка на сервер

```bash
sudo bash install.sh
sudo nano /opt/Bots/AviaTicketSearchBot/.env
sudo systemctl restart avia-ticket-search-bot.service
sudo systemctl status avia-ticket-search-bot.service
```

`install.sh` создаёт системного пользователя `avia-bot`, виртуальное окружение, каталоги `logs/` и `runtime/`, systemd unit с `EnvironmentFile` и делает `update.sh` исполняемым.

## Systemd и права

Рекомендуемый сервис запускает бота не от root, а от отдельного пользователя:

```ini
[Service]
User=avia-bot
WorkingDirectory=/opt/Bots/AviaTicketSearchBot
EnvironmentFile=-/opt/Bots/AviaTicketSearchBot/.env
ExecStart=/opt/Bots/AviaTicketSearchBot/.venv/bin/python /opt/Bots/AviaTicketSearchBot/main.py
Restart=always
```

Проверьте владельца файлов:

```bash
sudo chown -R avia-bot:avia-bot /opt/Bots/AviaTicketSearchBot
chmod +x /opt/Bots/AviaTicketSearchBot/update.sh
```

Если обновление запускается из бота и должно перезапускать systemd-сервис, выдайте точечное sudoers-право только на нужные команды:

```bash
command -v systemctl
sudo visudo -f /etc/sudoers.d/avia-ticket-search-bot
```

Пример для `/usr/bin/systemctl`:

```sudoers
avia-bot ALL=(root) NOPASSWD: /usr/bin/systemctl restart avia-ticket-search-bot.service, /usr/bin/systemctl is-active avia-ticket-search-bot.service
```

Не выдавайте `NOPASSWD: ALL` пользователю бота.

## Обновление через Telegram

1. Администратор открывает `/admin`.
2. Нажимает `🔍 Проверить обновления`.
3. При наличии новых коммитов нажимает `⬆️ Обновить бота` и подтверждает действие.
4. Бот пишет статус `in_progress` в `BOT_UPDATE_STATUS_PATH` и запускает `update.sh` отдельным процессом.
5. `update.sh` создаёт lock, пишет подробный лог в `BOT_UPDATE_LOG_PATH`, выполняет `git fetch`, `git pull --ff-only`, установку зависимостей, миграции БД и перезапуск сервиса.
6. После рестарта бот читает status-файл и отправляет администратору результат.

`update.sh` учитывает:

- неверный рабочий каталог;
- отсутствие `.git`;
- `fatal: detected dubious ownership in repository` через безопасный `safe.directory` только для каталога проекта;
- отсутствие нужной ветки и fallback на текущую/HEAD ветку origin;
- отсутствие `sudo`, `systemctl` или неверное имя сервиса;
- невозможность записи логов/status/lock.

## Просмотр логов

- Лог бота: `BOT_LOG_PATH`.
- Лог ошибок: `BOT_ERROR_LOG_PATH`.
- Лог обновлений: `BOT_UPDATE_LOG_PATH`.

Админ-панель показывает последние строки логов. Если файл отсутствует, недоступен или слишком большой, бот отправляет понятное сообщение и ограниченный хвост лога, чтобы не превысить лимиты Telegram.

## Проверки разработки

```bash
python -m ruff check .
python -m compileall -q .
python -m unittest discover -s tests
bash -n update.sh && bash -n install.sh
```

## Релиз 1.5.0

- Полная архитектура RU/EN локализации через JSON locale-файлы и DB-предпочтения пользователя.
- Валюты RUB/USD/EUR и per-user market/currency в запросах Aviasales Data API.
- Aviasales Autocomplete API для поиска городов/аэропортов на RU/EN.
- Inline-календарь Telegram для выбора дат с запретом прошедших и некорректных return-дней.
- Inline-выбор пассажиров и единая модель `FlightSearchRequest`.
- Rule-based parser естественных запросов на русском и английском.

## Релиз 1.4.0

- Перевод API-клиента на актуальные Aviasales Data API v3.
- Передача Travelpayouts-токена через `X-Access-Token`.
- Отказ от старых `/v1` и `/v2` ценовых эндпоинтов.
- Безопасное чтение логов обновления в админке.
- Устойчивый self-update через `update.sh` с lock/status/logging и обработкой Git/systemd ошибок.
- Исправление сценария календарных цен рядом с датой.


## Модуль «Авиа-новости и акции»

В проект добавлена подсистема `app.news` для официальных новостей авиакомпаний, акций, промокодов и новых направлений. Она включает локальный реестр авиакомпаний, синхронизацию со справочником Travelpayouts/Aviasales, учёт авиакомпаний из выдачи билетов, RSS/Atom и HTML-сборщики, дедупликацию, rule-based классификацию, RU/EN карточки, админскую модерацию, пользовательские подписки и дайджесты.

Новые таблицы SQLite создаются безопасно и идемпотентно при `db.init_db()`:

- `airlines`;
- `airline_news_sources`;
- `airline_news`;
- `user_news_subscriptions`;
- `user_news_deliveries`.

Админский запуск: **⚙️ Административная панель → 📰 Новости**. Пользовательский раздел: **📰 Новости и акции** в главном меню. Подробная документация находится в [`docs/news_module.md`](docs/news_module.md).
