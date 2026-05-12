from sqlalchemy.orm import sessionmaker
from models import Base, User, Subscription, AnalyticsEvent, BotVersion, create_session
from datetime import datetime
import logging

class DatabaseManager:
    """Менеджер базы данных с использованием SQLAlchemy"""
    
    def __init__(self, db_path: str = 'flights_bot.db'):
        self.db_path = db_path
        self.Session = sessionmaker(bind=create_engine(f'sqlite:///{db_path}'))
        
    def init_db(self):
        """Инициализация базы данных"""
        try:
            engine = create_engine(f'sqlite:///{self.db_path}')
            Base.metadata.create_all(engine)
            
            # Создаем запись о текущей версии, если ее нет
            session = self.Session()
            try:
                # Проверяем, есть ли уже записи о версиях
                version_count = session.query(BotVersion).count()
                if version_count == 0:
                    # Добавляем начальную версию
                    initial_version = BotVersion(
                        version='5.0',
                        commit_hash='initial',
                        changelog='Initial version',
                        is_current=True
                    )
                    session.add(initial_version)
                    session.commit()
                    logging.info("Добавлена начальная версия бота в базу данных")
            finally:
                session.close()
                
            logging.info(f"База данных инициализирована: {self.db_path}")
            return True
        except Exception as e:
            logging.error(f"Ошибка инициализации базы данных: {e}")
            return False
    
    def register_user(self, user_id: int, username: str, first_name: str, 
                     last_name: str, referrer_id: int = None) -> bool:
        """Регистрация пользователя"""
        session = self.Session()
        try:
            # Проверяем, существует ли пользователь
            user = session.query(User).filter(User.user_id == user_id).first()
            
            if user:
                # Обновляем существующего пользователя
                user.username = username
                user.first_name = first_name
                user.last_name = last_name
                if referrer_id and not user.referrer_id:
                    user.referrer_id = referrer_id
            else:
                # Создаем нового пользователя
                user = User(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    referrer_id=referrer_id
                )
                session.add(user)
            
            session.commit()
            return True
        except Exception as e:
            logging.error(f"Ошибка регистрации пользователя {user_id}: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def add_referral(self, user_id: int, referrer_id: int) -> bool:
        """Добавление реферала"""
        if user_id == referrer_id:
            return False
            
        session = self.Session()
        try:
            # Проверяем, есть ли уже реферер у пользователя
            user = session.query(User).filter(User.user_id == user_id).first()
            if user and not user.referrer_id:
                user.referrer_id = referrer_id
                session.commit()
                return True
            return False
        except Exception as e:
            logging.error(f"Ошибка добавления реферала {user_id} для {referrer_id}: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def get_user_referrals_count(self, user_id: int) -> int:
        """Получение количества рефералов пользователя"""
        session = self.Session()
        try:
            count = session.query(User).filter(User.referrer_id == user_id).count()
            return count
        except Exception as e:
            logging.error(f"Ошибка получения количества рефералов для {user_id}: {e}")
            return 0
        finally:
            session.close()
    
    def get_user_info(self, user_id: int) -> User:
        """Получение информации о пользователе"""
        session = self.Session()
        try:
            user = session.query(User).filter(User.user_id == user_id).first()
            return user
        except Exception as e:
            logging.error(f"Ошибка получения информации о пользователе {user_id}: {e}")
            return None
        finally:
            session.close()
    
    def add_subscription(self, user_id: int, o_code: str, d_code: str, 
                        o_name: str, d_name: str, dep: str, ret: str, 
                        psng: int, price: int) -> bool:
        """Добавление новой подписки"""
        session = self.Session()
        try:
            # Проверяем, существует ли уже такая подписка
            existing = session.query(Subscription).filter(
                Subscription.user_id == user_id,
                Subscription.origin_code == o_code,
                Subscription.dest_code == d_code,
                Subscription.departure_date == dep,
                Subscription.return_date == ret
            ).first()
            
            if existing:
                # Обновляем цену, если новая цена ниже
                if price < existing.last_price:
                    existing.last_price = price
                    session.commit()
                return False  # Дубликат, не добавляем как новую
            
            # Создаем новую подписку
            subscription = Subscription(
                user_id=user_id,
                origin_code=o_code,
                dest_code=d_code,
                origin_name=o_name,
                dest_name=d_name,
                departure_date=dep,
                return_date=ret,
                passengers=psng,
                last_price=price
            )
            session.add(subscription)
            session.commit()
            return True
        except Exception as e:
            logging.error(f"Ошибка добавления подписки: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def delete_subscription(self, sub_id: int) -> bool:
        """Удаление подписки по ID"""
        session = self.Session()
        try:
            subscription = session.query(Subscription).filter(Subscription.id == sub_id).first()
            if subscription:
                session.delete(subscription)
                session.commit()
                return True
            return False
        except Exception as e:
            logging.error(f"Ошибка удаления подписки {sub_id}: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def get_user_subscriptions(self, user_id: int) -> list:
        """Получение подписок пользователя"""
        session = self.Session()
        try:
            subscriptions = session.query(Subscription).filter(
                Subscription.user_id == user_id
            ).all()
            return subscriptions
        except Exception as e:
            logging.error(f"Ошибка получения подписок пользователя {user_id}: {e}")
            return []
        finally:
            session.close()
    
    def get_all_subscriptions(self) -> list:
        """Получение всех подписок"""
        session = self.Session()
        try:
            subscriptions = session.query(Subscription).all()
            return subscriptions
        except Exception as e:
            logging.error(f"Ошибка получения всех подписок: {e}")
            return []
        finally:
            session.close()
    
    def update_subscription_price(self, sub_id: int, new_price: int) -> bool:
        """Обновление цены подписки"""
        session = self.Session()
        try:
            subscription = session.query(Subscription).filter(Subscription.id == sub_id).first()
            if subscription and new_price < subscription.last_price:
                subscription.last_price = new_price
                session.commit()
                return True
            return False
        except Exception as e:
            logging.error(f"Ошибка обновления цены подписки {sub_id}: {e}")
            session.rollback()
            return False
        finally:
            session.close()
    
    def track_event(self, event_type: str, user_id: int = None, 
                   utm_source: str = None, utm_medium: str = None, 
                   utm_campaign: str = None, referrer_id: int = None,
                   additional_data: str = None):
        """Отслеживание аналитического события"""
        session = self.Session()
        try:
            event = AnalyticsEvent(
                event_type=event_type,
                user_id=user_id,
                utm_source=utm_source,
                utm_medium=utm_medium,
                utm_campaign=utm_campaign,
                referrer_id=referrer_id,
                additional_data=additional_data
            )
            session.add(event)
            session.commit()
        except Exception as e:
            logging.error(f"Ошибка отслеживания события {event_type}: {e}")
            session.rollback()
        finally:
            session.close()
    
    def get_stats(self) -> dict:
        """Получение статистики по основным метрикам"""
        session = self.Session()
        try:
            # Общее количество событий по типам
            events_count = session.query(
                AnalyticsEvent.event_type, 
                func.count(AnalyticsEvent.id)
            ).group_by(AnalyticsEvent.event_type).all()
            
            stats = {event_type: count for event_type, count in events_count}
            
            # Количество уникальных пользователей
            unique_users = session.query(func.count(func.distinct(AnalyticsEvent.user_id))).scalar()
            stats['unique_users'] = unique_users
            
            # Топ UTM источников
            utm_sources = session.query(
                AnalyticsEvent.utm_source, 
                func.count(AnalyticsEvent.id)
            ).filter(AnalyticsEvent.utm_source.isnot(None))\
             .group_by(AnalyticsEvent.utm_source)\
             .order_by(func.count(AnalyticsEvent.id).desc())\
             .limit(10).all()
            
            stats['utm_sources'] = {source: count for source, count in utm_sources}
            
            return stats
        except Exception as e:
            logging.error(f"Ошибка получения статистики: {e}")
            return {}
        finally:
            session.close()
    
    def get_recent_events(self, limit: int = 20) -> list:
        """Получение последних событий"""
        session = self.Session()
        try:
            events = session.query(AnalyticsEvent)\
                .order_by(AnalyticsEvent.timestamp.desc())\
                .limit(limit).all()
            return events
        except Exception as e:
            logging.error(f"Ошибка получения последних событий: {e}")
            return []
        finally:
            session.close()
    
    def get_current_version(self) -> BotVersion:
        """Получение текущей версии бота"""
        session = self.Session()
        try:
            version = session.query(BotVersion).filter(BotVersion.is_current == True).first()
            return version
        except Exception as e:
            logging.error(f"Ошибка получения текущей версии: {e}")
            return None
        finally:
            session.close()
    
    def update_current_version(self, version: str, commit_hash: str, 
                              changelog: str) -> bool:
        """Обновление информации о текущей версии"""
        session = self.Session()
        try:
            # Снимаем флаг is_current со всех версий
            session.query(BotVersion).update({BotVersion.is_current: False})
            
            # Проверяем, существует ли уже версия
            existing_version = session.query(BotVersion).filter(
                BotVersion.version == version
            ).first()
            
            if existing_version:
                existing_version.commit_hash = commit_hash
                existing_version.changelog = changelog
                existing_version.release_date = datetime.utcnow()
                existing_version.is_current = True
            else:
                # Создаем новую запись о версии
                new_version = BotVersion(
                    version=version,
                    commit_hash=commit_hash,
                    changelog=changelog,
                    is_current=True
                )
                session.add(new_version)
            
            session.commit()
            return True
        except Exception as e:
            logging.error(f"Ошибка обновления версии {version}: {e}")
            session.rollback()
            return False
        finally:
            session.close()