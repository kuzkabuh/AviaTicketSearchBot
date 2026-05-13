# Модуль «Авиа-новости, акции и новые направления»

## Назначение

Модуль `app.news` — самостоятельная подсистема AviaTicketSearchBot для сбора, хранения, модерации и публикации официальных новостей авиакомпаний: акций, промокодов, новых маршрутов, возобновлений рейсов и сезонных расписаний.

## Реестр авиакомпаний

Локальный реестр хранится в таблице `airlines`. В нём есть IATA/ICAO-коды, названия RU/EN, страна, признак российской авиакомпании, статус активности из справочника Aviasales/Travelpayouts, официальный сайт, статус источника новостей и статистика появления авиакомпании в результатах поиска билетов.

Реестр расширяемый:

- первично заполняется seed-набором крупных российских и двух международных авиакомпаний;
- синхронизируется со справочником Travelpayouts/Aviasales;
- дополняется кодами авиакомпаний, реально встреченными в выдаче Aviasales Data API;
- ручные настройки источников не затираются при повторной синхронизации.

## Синхронизация Aviasales / Travelpayouts

`app/news/airline_sync_service.py` загружает `https://api.travelpayouts.com/data/airlines.json`, нормализует поля `name`, `code`/IATA, `icao`, `country`, `is_active` и сохраняет записи в `airlines` с `source_origin='aviasales_reference'`.

Российские авиакомпании определяются по `country_code='RU'` или названию страны `Russia` / `Russian Federation` / `Россия`.

Запуск:

- автоматически раз в сутки через `NewsScheduler`;
- вручную из админки: **📰 Новости → 🔁 Синхронизировать авиакомпании Aviasales**;
- при первом развёртывании таблица seed-ится, если пуста.

## Учёт авиакомпаний из билетов

`services/tickets.py` после каждого поиска вызывает `record_airlines_from_offers()`. Сервис извлекает `airline` / `airline_code` из нормализованных офферов и обновляет:

- `first_seen_in_ticket_results_at`;
- `last_seen_in_ticket_results_at`;
- `ticket_results_count`.

Если код не найден в локальном реестре, создаётся минимальная запись с `source_origin='aviasales_search_results'`.

## Стартовые авиакомпании

Seed-реестр содержит 21 авиакомпанию, включая 19 российских:

- Аэрофлот;
- Победа;
- Россия;
- S7 Airlines;
- Уральские авиалинии;
- Utair;
- Nordwind Airlines;
- Smartavia;
- Red Wings;
- Азимут;
- Aurora;
- NordStar;
- Ямал;
- Якутия;
- Икар / Pegas Fly;
- ИрАэро;
- UVT Aero;
- РусЛайн;
- Алроса;
- Qatar Airways;
- Emirates.

## Стартовые официальные источники

Сразу настроены официальные HTML-источники для 18 авиакомпаний:

- Aeroflot — `https://www.aeroflot.ru/ru-ru/news`;
- Pobeda — `https://www.pobeda.aero/information/news`;
- Rossiya — `https://www.rossiya-airlines.ru/about/news/`;
- S7 — `https://www.s7.ru/ru/about/news/`;
- Ural Airlines — `https://www.uralairlines.ru/about/news/`;
- Utair — `https://www.utair.ru/about/news/`;
- Nordwind — `https://nordwindairlines.ru/ru/news`;
- Smartavia — `https://flysmartavia.com/about/news/`;
- Red Wings — `https://flyredwings.com/about/news/`;
- Азимут — `https://azimuth.aero/ru/about/news/`;
- Aurora — `https://flyaurora.ru/about/news/`;
- NordStar — `https://www.nordstar.ru/about/news/`;
- Ямал — `https://yamal.aero/news/`;
- Якутия — `https://www.yakutia.aero/about/news/`;
- ИрАэро — `https://iraero.ru/about/news/`;
- UVT Aero — `https://uvtaero.ru/about/news/`;
- Qatar Airways — `https://www.qatarairways.com/press-releases/en-WW`;
- Emirates — `https://www.emirates.com/media-centre/`.

Икар / Pegas Fly, РусЛайн и Алроса добавлены в реестр со статусом `requires_manual_setup`, чтобы администратор мог позже уточнить источник.

## RSS / Atom и HTML сбор

- RSS/Atom: `app/news/fetchers/rss_fetcher.py` извлекает title, link, description/summary, published date и GUID.
- HTML: `app/news/fetchers/html_fetcher.py` безопасно собирает ссылки с официальной страницы, фильтрует новостные пути и не падает при отсутствующих полях.
- Сложные сайты можно подключать через `parser_key` и `app/news/fetchers/airline_specific_fetchers.py`.

Интервалы:

- RSS/Atom — 180 минут;
- HTML — 360 минут;
- общий планировщик проверяет due-источники каждые 15 минут, ограничивая параллелизм.

## Дедупликация

`app/news/deduplicator.py` строит `content_hash` из нормализованных полей:

- заголовок;
- URL;
- дата публикации;
- авиакомпания.

Перед сохранением проверяются:

1. `external_id + source_id`;
2. `source_url`;
3. `content_hash`.

## Модерация

Все новости создаются со статусом `pending`. Администратор открывает **📰 Новости → ⏳ На модерации**, смотрит карточку и может:

- одобрить и опубликовать;
- отклонить;
- позже повторить классификацию / перевод / извлечение маршрута через расширяемые сервисы.

Публикация переводит статус в `published` и заполняет `published_to_users_at`.

## Категории

Rule-based классификатор поддерживает RU/EN ключевые слова для:

- `discount_sale`;
- `promo_code`;
- `new_route`;
- `route_resumed`;
- `frequency_increase`;
- `seasonal_schedule`;
- `general_news`.

Для акций и промокодов извлекаются `promo_code`, `sale_end_at`, `travel_start_at`, `travel_end_at`, если они найдены регулярными выражениями.

## RU / EN тексты

`translator.py` — заменяемый слой подготовки коротких карточек. Сейчас он не имитирует машинный перевод: заполняет оригинальный язык и оставляет второй язык пустым для будущего AI/LLM-провайдера. Форматтеры безопасно падают обратно на оригинальный текст.

## Подписки и доставки

`user_news_subscriptions` хранит подписки:

- на категорию;
- на авиакомпанию;
- на все российские авиакомпании;
- на все новости;
- персонализированные.

`user_news_deliveries` защищает от повторной доставки одной новости в одном режиме.

## Дайджесты и подборки

`digest_service.py` умеет формировать:

- «Главные авиаакции дня»;
- «Новые маршруты недели»;
- персональную подборку «Для вас».

Персонализация на первом этапе считает score по истории поисков, активным подпискам на цены, совпадениям origin/destination и авиакомпании.

## Связь новости с поиском билетов

`route_extractor.py` пытается выделить маршрут из RU/EN текста регулярными выражениями. При доступе к Aviasales Autocomplete API можно валидировать названия и заполнить IATA-коды.

Если у опубликованной новости есть destination или полный маршрут, в карточке появляется кнопка **✈️ Найти билеты / Search flights**. Она запускает существующий сценарий поиска билетов с предзаполненным маршрутом и сохраняет существующую генерацию партнёрских ссылок Travelpayouts.

## Как добавить авиакомпанию

1. Добавить запись через админский интерфейс будущей формы или напрямую в `airlines`.
2. Указать IATA-код, название, страну, `is_russian`, официальный сайт.
3. Если источник пока неизвестен — поставить `news_source_status='requires_manual_setup'`.

## Как добавить источник

1. Создать запись в `airline_news_sources`.
2. Указать `airline_id`, тип (`rss`, `atom`, `html`), URL, роль, язык и интервал.
3. Для HTML можно заполнить `selectors_json` или добавить адаптер в `airline_specific_fetchers.py` и указать `parser_key`.
4. Перезапустить сбор вручную из админки или дождаться планировщика.
