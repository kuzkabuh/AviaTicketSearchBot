"""Deduplication helpers for airline news."""

from __future__ import annotations

import hashlib
import re

_WS_RE = re.compile(r"\s+")


def normalize_text(value: str | None) -> str:
    """Normalize text fragments before hash and duplicate comparison."""
    return _WS_RE.sub(" ", (value or "").strip().lower())


def build_content_hash(title: str, source_url: str, published_at: str | None, airline_name: str) -> str:
    """Build stable hash from normalized news identity fields."""
    payload = "|".join(
        [
            normalize_text(title),
            normalize_text(source_url).rstrip("/"),
            normalize_text(published_at),
            normalize_text(airline_name),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
