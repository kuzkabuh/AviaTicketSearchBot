"""
============================================================
Файл: handlers/start.py
Версия: 2.0.0
Дата изменения: 12.05.2026
Описание:
 Стартовые команды бота.
============================================================
"""

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import Message

# Инициализация роутера для обработки сообщений
router = Router()

@router.message(Command("start"))
async def start_command(message: Message):
    """
    Обработчик команды /start.
    Выводит приветственное сообщение и список доступных команд.
    """
    text = (
        "Добро пожаловать в AviaTicketSearchBot!\n\n"
        "Доступные команды:\n"
        "/search — поиск авиабилетов\n"
        "/popular — популярные направления\n"
    )
    
    # Отправка сообщения пользователю
    await message.answer(text)