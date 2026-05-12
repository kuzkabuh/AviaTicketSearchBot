import git
import logging
import os
import subprocess
import sys
from typing import Optional, Tuple
from datetime import datetime

class BotUpdater:
    """Класс для управления обновлением бота из Git-репозитория"""
    
    def __init__(self, repo_path: str = '.', repo_url: str = 'https://gitverse.ru/kuzkabuh/AviaTicketSearchBot.git'):
        """Инициализация updater'а
        
        Args:
            repo_path: Путь к локальному репозиторию
            repo_url: URL удаленного репозитория
        """
        self.repo_path = repo_path
        self.repo_url = repo_url
        self.repo = None
        
    def initialize_repo(self) -> bool:
        """Инициализация репозитория (клонирование или открытие существующего)"""
        try:
            # Проверяем, существует ли .git директория
            if os.path.exists(os.path.join(self.repo_path, '.git')):
                # Открываем существующий репозиторий
                self.repo = git.Repo(self.repo_path)
                logging.info(f"Открыт существующий репозиторий: {self.repo_path}")
            else:
                # Клонируем репозиторий
                logging.info(f"Клонирование репозитория из {self.repo_url}...")
                self.repo = git.Repo.clone_from(self.repo_url, self.repo_path)
                logging.info(f"Репозиторий успешно склонирован в {self.repo_path}")
            
            # Убедимся, что установлен правильный удаленный репозиторий
            try:
                origin = self.repo.remote('origin')
                if origin.url != self.repo_url:
                    origin.set_url(self.repo_url)
            except ValueError:
                # Если remote 'origin' не существует, создаем его
                self.repo.create_remote('origin', self.repo_url)
            
            return True
            
        except Exception as e:
            logging.error(f"Ошибка инициализации репозитория: {e}")
            return False
    
    def check_for_updates(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """Проверка наличия обновлений в удаленном репозитории
        
        Returns:
            Кортеж из (есть_обновления, новая_версия, сообщение_коммита)
        """
        if not self.repo:
            if not self.initialize_repo():
                return False, None, None
        
        try:
            # Получаем информацию о текущей ветке
            current_branch = self.repo.active_branch
            logging.info(f"Текущая ветка: {current_branch}")
            
            # Получаем удаленный репозиторий
            origin = self.repo.remote('origin')
            
            # Получаем информацию о коммитах ДО fetch
            local_commit = self.repo.head.commit
            
            # Забираем обновления из удаленного репозитория
            logging.info("Проверка обновлений...")
            origin.fetch()
            
            # Получаем информацию о коммитах ПОСЛЕ fetch
            remote_commit = origin.refs[current_branch].commit
            
            # Сравниваем коммиты
            if local_commit != remote_commit:
                # Есть обновления
                new_version = self._get_version_from_commit(remote_commit)
                commit_message = remote_commit.message.strip()
                
                logging.info(f"Найдено обновление: {new_version} ({commit_message})")
                return True, new_version, commit_message
            else:
                logging.info("Обновлений не найдено")
                return False, None, None
                
        except Exception as e:
            logging.error(f"Ошибка проверки обновлений: {e}")
            return False, None, None
    
    def _get_version_from_commit(self, commit) -> str:
        """Получение версии из коммита (по тегу или хешу)"""
        try:
            # Пытаемся найти тег для коммита
            tags = self.repo.tags
            for tag in tags:
                if tag.commit == commit:
                    return f"v{tag.name}"
            
            # Если тегов нет, используем первые 8 символов хеша коммита
            return f"{commit.hexsha[:8]}"
        except:
            return "unknown"
    
    def pull_updates(self) -> bool:
        """Загрузка и применение обновлений"""
        if not self.repo:
            if not self.initialize_repo():
                return False
        
        try:
            # Получаем активную ветку
            current_branch = self.repo.active_branch
            origin = self.repo.remote('origin')
            
            # Выполняем pull
            logging.info(f"Загрузка обновлений с ветки {current_branch}...")
            origin.pull()
            
            logging.info("Обновления успешно загружены")
            return True
            
        except Exception as e:
            logging.error(f"Ошибка загрузки обновлений: {e}")
            return False
    
    def get_current_version(self) -> str:
        """Получение текущей версии бота"""
        if not self.repo:
            if not self.initialize_repo():
                return "unknown"
        
        try:
            # Получаем текущий коммит
            current_commit = self.repo.head.commit
            
            # Пытаемся найти тег для коммита
            tags = self.repo.tags
            for tag in tags:
                if tag.commit == current_commit:
                    return f"v{tag.name}"
            
            # Если тегов нет, используем хеш коммита
            return f"{current_commit.hexsha[:8]}"
            
        except Exception as e:
            logging.error(f"Ошибка получения текущей версии: {e}")
            return "unknown"
    
    def get_last_commit_message(self) -> str:
        """Получение сообщения последнего коммита"""
        if not self.repo:
            if not self.initialize_repo():
                return "unknown"
        
        try:
            current_commit = self.repo.head.commit
            return current_commit.message.strip()
            
        except Exception as e:
            logging.error(f"Ошибка получения сообщения коммита: {e}")
            return "unknown"