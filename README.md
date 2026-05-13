# AviaTicketSearchBot

**Версия:** 1.4.0

Асинхронный Telegram-бот на `aiogram 3.x` для поиска авиабилетов, показа нескольких предложений, подписок на изменение цены и администрирования через Telegram.

> Важно: бот использует **Aviasales Data API** от Travelpayouts. Этот API возвращает кешированные данные, сформированные на основе поисков пользователей Aviasales. Это не real-time Flights Search API; перед покупкой пользователь должен проверить итоговую цену по ссылке Aviasales.

## Основные функции

- `/start` — главное меню.
- `/search` — пошаговый поиск билетов: откуда → куда → тип поездки → дата → пассажиры.
- Поиск локаций по IATA-коду, русскому названию города или названию аэропорта.
- Уточнение локации inline-кнопками при неоднозначном вводе, например `Москва` → `MOW`, `SVO`, `DME`, `VKO`, `ZIA`.
- Вывод нескольких предложений с ценой, временем, пересадками, авиакомпанией, номером рейса и ссылкой Aviasales.
- Просмотр цен рядом с выбранной датой через сгруппированные цены Data API.
- `/popular` — популярные направления из выбранного города.
- `/subscriptions` — подписки на изменение цены, ручная проверка и удаление.
- Фоновая проверка цен по активным подпискам.
- `/admin` — админ-панель: версия, обновления, логи, статистика, пользователи, состояние системы, рестарт, рассылка.

## Aviasales / Travelpayouts API

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

## Релиз 1.4.0

- Перевод API-клиента на актуальные Aviasales Data API v3.
- Передача Travelpayouts-токена через `X-Access-Token`.
- Отказ от старых `/v1` и `/v2` ценовых эндпоинтов.
- Безопасное чтение логов обновления в админке.
- Устойчивый self-update через `update.sh` с lock/status/logging и обработкой Git/systemd ошибок.
- Исправление сценария календарных цен рядом с датой.
