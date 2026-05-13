# Поиск туда-обратно

Для `/aviasales/v3/prices_for_dates` бот строит запросы строго так:

- one-way: `departure_at`, `one_way=true`, без `return_at`;
- round-trip: `departure_at`, `return_at`, `one_way=false`.

В debug-лог пишутся параметры без токена: origin, destination, departure_at, return_at, one_way, currency, market, limit, sorting.

## Интерпретация ответа

Round-trip предложение считается корректным только если item Data API содержит `return_at`. Если пользователь искал туда-обратно, но Data API вернул item без `return_at`, бот не показывает его как round-trip и не называет его цену ценой туда-обратно.

Карточка round-trip показывает:

- маршрут туда и обратно;
- дату/время вылета;
- дату/время возвращения;
- пересадки туда и обратно (`transfers`, `return_transfers`);
- длительность туда/обратно (`duration_to`, `duration_back`);
- общую длительность (`duration`);
- честную пометку, что Data API может отдавать агрегированные данные.

Если корректных round-trip item нет, бот сообщает: «В доступном кэше Aviasales не найдено корректных предложений туда-обратно на эти даты» и даёт ссылку на поиск Aviasales туда-обратно.
