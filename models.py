from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

Base = declarative_base()

class User(Base):
    """Модель пользователя"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    referrer_id = Column(Integer, ForeignKey('users.user_id'))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связь с реферером
    referrer = relationship("User", remote_side=[user_id])
    # Связь с подписками
    subscriptions = relationship("Subscription", back_populates="user")
    
    # Индекс для ускорения поиска по user_id
    __table_args__ = (Index('ix_users_user_id', 'user_id'),)

class Subscription(Base):
    """Модель подписки на отслеживание цен"""
    __tablename__ = 'subscriptions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    origin_code = Column(String(10), nullable=False)
    dest_code = Column(String(10), nullable=False)
    origin_name = Column(String(100), nullable=False)
    dest_name = Column(String(100), nullable=False)
    departure_date = Column(String(20), nullable=False)
    return_date = Column(String(20))
    passengers = Column(Integer, default=1)
    last_price = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связь с пользователем
    user = relationship("User", back_populates="subscriptions")
    
    # Уникальный индекс для предотвращения дубликатов
    __table_args__ = (
        Index('ix_subscriptions_unique', 
              'user_id', 'origin_code', 'dest_code', 
              'departure_date', 'return_date', unique=True),
    )

class AnalyticsEvent(Base):
    """Модель для хранения аналитических событий"""
    __tablename__ = 'analytics_events'
    
    id = Column(Integer, primary_key=True)
    event_type = Column(String(50), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey('users.user_id'))
    utm_source = Column(String(100))
    utm_medium = Column(String(100))
    utm_campaign = Column(String(100))
    referrer_id = Column(Integer)
    additional_data = Column(String(500))
    
    # Связь с пользователем
    user = relationship("User")
    
    # Индексы для ускорения аналитических запросов
    __table_args__ = (
        Index('ix_analytics_event_type', 'event_type'),
        Index('ix_analytics_timestamp', 'timestamp'),
        Index('ix_analytics_user_id', 'user_id'),
    )

class BotVersion(Base):
    """Модель для хранения информации о версиях бота"""
    __tablename__ = 'bot_versions'
    
    id = Column(Integer, primary_key=True)
    version = Column(String(20), nullable=False)
    commit_hash = Column(String(40), nullable=False)
    release_date = Column(DateTime, default=datetime.utcnow)
    changelog = Column(String(1000))
    is_current = Column(Boolean, default=False)
    
    # Уникальный индекс для версии
    __table_args__ = (Index('ix_bot_versions_version', 'version', unique=True),)

# Создание сессии
def create_session(db_path: str = 'flights_bot.db'):
    """Создание сессии SQLAlchemy"""
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()