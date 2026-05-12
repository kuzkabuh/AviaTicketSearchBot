import sqlite3
from typing import Optional, Tuple

class DatabaseManager:
    """Менеджер базы данных для работы с пользователями и подписками."""
    
    def __init__(self, db_name: str = 'flights_bot.db'):
        self.db_name = db_name
    
    def init_db(self):
        """Инициализация базы данных."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                origin_code TEXT,
                dest_code TEXT,
                origin_name TEXT,
                dest_name TEXT,
                departure_date TEXT,
                return_date TEXT,
                passengers INTEGER,
                last_price INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, origin_code, dest_code, departure_date, return_date)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                referrer_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                utm_source TEXT,
                utm_medium TEXT,
                utm_campaign TEXT,
                referrer_id INTEGER,
                additional_data TEXT
            )
        ''')
        conn.commit()
        conn.close()
    
    def register_user(self, user_id: int, username: str, first_name: str, 
                     last_name: str, referrer_id: Optional[int] = None):
        """Регистрация пользователя."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO users 
                (user_id, username, first_name, last_name, referrer_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name, referrer_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"Ошибка регистрации пользователя {user_id}: {e}")
            return False
        finally:
            conn.close()
    
    def add_referral(self, user_id: int, referrer_id: int) -> bool:
        """Добавление реферала."""
        # Проверяем, не является ли пользователь своим собственным реферером
        if user_id == referrer_id:
            return False
            
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        try:
            # Проверяем, есть ли уже реферер у пользователя
            cursor.execute('SELECT referrer_id FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            
            if result is None or result[0] is None:
                # Обновляем реферера
                cursor.execute('''
                    UPDATE users SET referrer_id = ? WHERE user_id = ?
                ''', (referrer_id, user_id))
                conn.commit()
                return cursor.rowcount > 0
            return False
        except Exception as e:
            print(f"Ошибка добавления реферала {user_id} для {referrer_id}: {e}")
            return False
        finally:
            conn.close()
    
    def get_user_referrals_count(self, user_id: int) -> int:
        """Получение количества рефералов пользователя."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT COUNT(*) FROM users WHERE referrer_id = ?', (user_id,))
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            print(f"Ошибка получения количества рефералов для {user_id}: {e}")
            return 0
        finally:
            conn.close()
    
    def get_user_info(self, user_id: int) -> Optional[Tuple]:
        """Получение информации о пользователе."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT user_id, username, first_name, last_name, referrer_id, created_at 
                FROM users WHERE user_id = ?
            ''', (user_id,))
            return cursor.fetchone()
        except Exception as e:
            print(f"Ошибка получения информации о пользователе {user_id}: {e}")
            return None
        finally:
            conn.close()
    
    def add_subscription(self, user_id: int, o_code: str, d_code: str, 
                        o_name: str, d_name: str, dep: str, ret: str, 
                        psng: int, price: int) -> bool:
        """Добавление новой подписки (игнорирует дубли)."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO subscriptions 
                (user_id, origin_code, dest_code, origin_name, dest_name, 
                 departure_date, return_date, passengers, last_price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, o_code, d_code, o_name, d_name, dep, ret, psng, price))
            conn.commit()
            return cursor.rowcount > 0  # True если добавлено
        except Exception as e:
            print(f"Ошибка добавления подписки: {e}")
            return False
        finally:
            conn.close()
    
    def delete_subscription(self, sub_id: int):
        """Удаление подписки по ID."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM subscriptions WHERE id = ?', (sub_id,))
        conn.commit()
        conn.close()
    
    def get_user_subscriptions(self, user_id: int) -> list:
        """Получение подписок пользователя."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT id, origin_name, dest_name, departure_date, return_date, last_price 
                FROM subscriptions WHERE user_id = ?
            ''', (user_id,))
            return cursor.fetchall()
        except Exception as e:
            print(f"Ошибка получения подписок пользователя {user_id}: {e}")
            return []
        finally:
            conn.close()
    
    def get_all_subscriptions(self) -> list:
        """Получение всех подписок."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT id, user_id, origin_code, dest_code, origin_name, dest_name, 
                       departure_date, return_date, passengers, last_price 
                FROM subscriptions
            ''')
            return cursor.fetchall()
        except Exception as e:
            print(f"Ошибка получения всех подписок: {e}")
            return []
        finally:
            conn.close()