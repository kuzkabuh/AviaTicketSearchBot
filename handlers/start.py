from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Приветственное сообщение с краткой инструкцией."""
    await message.answer(
        "✈️ Привет! Я бот для поиска дешёвых авиабилетов.\n"
        "Чтобы найти билеты, используй команду /search.\n"
        "Ты также можешь посмотреть популярные направления из твоего города с помощью /popular."
    )