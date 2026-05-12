import logging
import os
from logging.handlers import RotatingFileHandler

# Настройка логирования в файл
def setup_logging():
    """Настройка логирования в файл с ротацией."""
    # Создаем директорию для логов, если ее нет
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Основной логгер
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Форматтер
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Handler для файла с ротацией (максимум 10 файлов по 5MB)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'bot.log'),
        maxBytes=5*1024*1024,
        backupCount=10
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    
    # Handler для консоли
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Добавляем handlers к логгеру
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger