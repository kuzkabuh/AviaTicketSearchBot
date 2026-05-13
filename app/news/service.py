"""High-level airline news collection and moderation services."""

from __future__ import annotations

import asyncio
import logging

from app.news.fetchers.airline_specific_fetchers import SPECIFIC_FETCHERS
from app.news.fetchers.html_fetcher import HtmlNewsFetcher
from app.news.fetchers.rss_fetcher import RssNewsFetcher
from app.news.parser import enrich_item
from app.news.repository import NewsRepository, NewsSourceRepository, connect, ensure_news_schema
from services.admin_alerts_service import AdminAlertsService

logger = logging.getLogger(__name__)


class NewsCollectionService:
    def __init__(self) -> None:
        self.rss_fetcher = RssNewsFetcher()
        self.html_fetcher = HtmlNewsFetcher()
        self._source_locks: set[int] = set()

    def _fetcher_for(self, source: dict):
        parser_key = source.get("parser_key")
        if parser_key and parser_key in SPECIFIC_FETCHERS:
            return SPECIFIC_FETCHERS[parser_key]()
        return self.rss_fetcher if source.get("source_type") in {"rss", "atom"} else self.html_fetcher

    async def collect_source(self, source_id: int) -> dict[str, int | str]:
        if source_id in self._source_locks:
            return {"source_id": source_id, "status": "skipped_locked", "fetched": 0, "created": 0}
        self._source_locks.add(source_id)
        try:
            with connect() as connection:
                ensure_news_schema(connection)
                source = NewsSourceRepository(connection).get_by_id(source_id)
            if not source:
                return {"source_id": source_id, "status": "not_found", "fetched": 0, "created": 0}
            logger.info("News source collection started id=%s url=%s", source_id, source.get("source_url"))
            try:
                items = await self._fetcher_for(source).fetch(source)
                created = 0
                with connect() as connection:
                    ensure_news_schema(connection)
                    news_repo = NewsRepository(connection)
                    source_repo = NewsSourceRepository(connection)
                    for item in items:
                        data = {
                            "source_id": source["id"],
                            "airline_id": source["airline_id"],
                            "airline_code": source.get("airline_code"),
                            "airline_name": source.get("airline_name"),
                            **enrich_item(item, source),
                        }
                        _, is_new = news_repo.create_news(data)
                        created += int(is_new)
                    source_repo.mark_checked(source_id, True)
                    healed_source = source_repo.get_by_id(source_id) or source
                    pending_count = len(news_repo.get_pending(limit=1000))
                    connection.commit()
                if int(source.get("consecutive_errors") or 0) > 0:
                    await AdminAlertsService().news_source_recovered(healed_source)
                if created:
                    await AdminAlertsService().news_pending(pending_count)
                logger.info("News source collection finished id=%s fetched=%s created=%s", source_id, len(items), created)
                return {"source_id": source_id, "status": "ok", "fetched": len(items), "created": created}
            except Exception as error:  # noqa: BLE001
                logger.exception("News source collection failed id=%s", source_id)
                with connect() as connection:
                    ensure_news_schema(connection)
                    source_repo = NewsSourceRepository(connection)
                    source_repo.mark_checked(source_id, False, str(error))
                    broken_source = source_repo.get_by_id(source_id) or source
                    connection.commit()
                if int(broken_source.get("consecutive_errors") or 0) >= 3:
                    await AdminAlertsService().news_source_broken(broken_source)
                return {"source_id": source_id, "status": "error", "error": str(error), "fetched": 0, "created": 0}
        finally:
            self._source_locks.discard(source_id)

    async def collect_due_sources(self, limit: int = 20, concurrency: int = 3) -> list[dict[str, int | str]]:
        def _sources() -> list[dict]:
            with connect() as connection:
                ensure_news_schema(connection)
                return NewsSourceRepository(connection).get_active_sources(due_only=True)[:limit]
        sources = await asyncio.to_thread(_sources)
        semaphore = asyncio.Semaphore(concurrency)
        async def run(source: dict):
            async with semaphore:
                return await self.collect_source(int(source["id"]))
        return await asyncio.gather(*(run(source) for source in sources)) if sources else []

    async def publish_news(self, news_id: int, comment: str | None = None) -> dict | None:
        def _publish() -> dict | None:
            with connect() as connection:
                ensure_news_schema(connection)
                repo = NewsRepository(connection)
                repo.update_status(news_id, "published", comment)
                row = repo.get_by_id(news_id)
                connection.commit()
                return row
        return await asyncio.to_thread(_publish)
