# AviaTicketSearchBot

Асинхронный Telegram-бот для поиска авиабилетов через реальные эндпоинты Aviasales / Travelpayouts API.

## Что внутри

- `aiogram 3.x` и `Router` для команд и сообщений.
- FSM (`FSMContext`) вместо `telebot.register_next_step_handler`.
- `aiohttp` вместо `requests` для всех HTTP-запросов к Travelpayouts.
- Реальные эндпоинты:
  - `/v1/prices/cheap` — поиск дешевых билетов;
  - `/v1/city-directions` — популярные направления;
  - `/v2/prices/calendar` — календарь цен.
- Inline-кнопки через `InlineKeyboardBuilder`.

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
```

Запуск:

```bash
python main.py
```

## Команды

- `/start` — приветствие и кнопки быстрого запуска.
- `/help` — справка по формату ввода.
- `/search` — пошаговый поиск билетов: откуда → куда → дата.
- `/popular` — популярные направления из выбранного города.
- `/cancel` — отмена текущего FSM-сценария.

## Структура

```text
config.py                  # чтение переменных окружения
api.py                     # aiohttp-клиент Travelpayouts
main.py                    # Bot, Dispatcher, подключение Router-ов
handlers/start.py          # /start, /help, /cancel и кнопки меню
handlers/search.py         # FSM поиска и популярных направлений
states/search_states.py    # состояния TicketSearchState и PopularDirectionState
keyboards/inline.py        # InlineKeyboardBuilder-клавиатуры
utils/validators.py        # проверка IATA-кодов и дат
```
