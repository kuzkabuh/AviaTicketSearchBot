"""APScheduler integration for airline news collection."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.news.airline_sync_service import AirlineSyncService
from app.news.service import NewsCollectionService

logger = logging.getLogger(__name__)


class NewsScheduler:
    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self.collection_service = NewsCollectionService()

    def start(self) -> None:
        if self.scheduler.running:
            return
        self.scheduler.add_job(self.collection_service.collect_due_sources, "interval", minutes=15, id="news_collect_due", max_instances=1, coalesce=True)
        self.scheduler.add_job(AirlineSyncService().sync, "interval", hours=24, id="airline_sync_daily", max_instances=1, coalesce=True)
        self.scheduler.start()
        logger.info("News scheduler started")

    async def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("News scheduler stopped")
