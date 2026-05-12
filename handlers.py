from aiogram import types
from api_client import get_tickets

async def send_welcome(message: types.Message):
    """Отправка приветственного сообщения."""
    await message.reply(
        "Привет! Я помогу найти авиабилеты.\n\n"
        "Отправь запрос в формате:\n"
        "Откуда - Куда (например: MOW - LED)"
    )

async def search_handler(message: types.Message):
    """Обработка текстового запроса пользователя."""
    text = message.text.split("-")
    
    # Простая проверка формата сообщения
    if len(text) != 2:
        await message.answer("Пожалуйста, используйте формат: 'Откуда - Куда' (например: MOW - LED)")
        return

    origin = text[0].strip()
    destination = text[1].strip()

    await message.answer(f"Ищу билеты {origin} ✈️ {destination}...")

    tickets = get_tickets(origin, destination)

    if tickets is None:
        await message.answer("Произошла ошибка при подключении к сервису поиска. Попробуйте позже.")
    elif not tickets:
        await message.answer("К сожалению, билетов по вашему направлению не найдено.")
    else:
        # Формируем список найденных билетов
        for ticket in tickets:
            price = ticket.get("price")
            airline = ticket.get("airline")
            link = f"https://www.aviasales.ru{ticket.get('link')}"
            
            res_msg = (
                f"🎫 Билет найден!\n"
                f"Цена: {price} руб.\n"
                f"Авиакомпания: {airline}\n"
                f"🔗 [Купить билет]({link})"
            )
            await message.answer(res_msg, parse_mode="Markdown")