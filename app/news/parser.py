"""News item enrichment pipeline: classify, extract promo/route and bilingual fields."""

from __future__ import annotations

from app.news.classifier import classify_news, extract_promo_code, extract_sale_dates
from app.news.deduplicator import build_content_hash
from app.news.route_extractor import extract_route_names
from app.news.translator import prepare_bilingual_text


def enrich_item(item, source: dict) -> dict:
    text = "\n".join(filter(None, [item.title, item.summary, item.content]))
    classification = classify_news(item.title, item.summary, item.content)
    dates = extract_sale_dates(text) if classification.category in {"discount_sale", "promo_code"} else {"sale_end_at": None, "travel_start_at": None, "travel_end_at": None}
    route = extract_route_names(text)
    bilingual = prepare_bilingual_text(item.title, item.summary, item.language_code or source.get("language_code"))
    return {
        "category": classification.category,
        "title_original": item.title,
        "summary_original": item.summary,
        "content_original": item.content,
        **bilingual,
        "source_url": item.link,
        "image_url": item.image_url,
        "published_at": item.published_at,
        "external_id": item.external_id,
        "content_hash": build_content_hash(item.title, item.link, item.published_at, source.get("airline_name") or ""),
        "related_origin_name": route.origin_name,
        "related_destination_name": route.destination_name,
        "related_origin_iata": route.origin_iata,
        "related_destination_iata": route.destination_iata,
        "promo_code": extract_promo_code(text),
        **dates,
    }
