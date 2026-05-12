import sqlite3
import datetime
from typing import Dict, List, Tuple

class AnalyticsTracker:
    """Класс для отслеживания аналитики использования бота."""
    
    def __init__(self, db_name: str = 'flights_bot.db'):
        self.db_name = db_name
        self.init_db()
    
    def init_db(self):
        """Инициализация таблицы для аналитики."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
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
    
    def track_event(self, event_type: str, user_id: int = None, 
                   utm_source: str = None, utm_medium: str = None, 
                   utm_campaign: str = None, referrer_id: int = None,
                   additional_data: str = None):
        """Отслеживание события."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO analytics 
            (event_type, user_id, utm_source, utm_medium, utm_campaign, referrer_id, additional_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (event_type, user_id, utm_source, utm_medium, utm_campaign, referrer_id, additional_data))
        conn.commit()
        conn.close()
    
    def get_stats(self) -> Dict[str, int]:
        """Получение статистики по основным метрикам."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Общее количество событий по типам
        cursor.execute('''
            SELECT event_type, COUNT(*) as count 
            FROM analytics 
            GROUP BY event_type
        ''')
        stats = dict(cursor.fetchall())
        
        # Количество уникальных пользователей
        cursor.execute('''
            SELECT COUNT(DISTINCT user_id) as unique_users 
            FROM analytics 
            WHERE user_id IS NOT NULL
        ''')
        unique_users = cursor.fetchone()[0]
        stats['unique_users'] = unique_users
        
        # Топ UTM источников
        cursor.execute('''
            SELECT utm_source, COUNT(*) as count 
            FROM analytics 
            WHERE utm_source IS NOT NULL
            GROUP BY utm_source
            ORDER BY count DESC
            LIMIT 10
        ''')
        stats['utm_sources'] = dict(cursor.fetchall())
        
        conn.close()
        return stats
    
    def get_recent_events(self, limit: int = 20) -> List[Tuple]:
        """Получение последних событий."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT event_type, timestamp, user_id, utm_source, utm_medium, utm_campaign, referrer_id
            FROM analytics 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        events = cursor.fetchall()
        conn.close()
        return events