"""Simple personalization scoring for airline news."""

from __future__ import annotations

import sqlite3
from typing import Any


def score_news_for_user(connection: sqlite3.Connection, user_id: int, news: dict[str, Any]) -> int:
    score = 0
    if news.get("related_origin_iata") or news.get("related_destination_iata"):
        route_rows = connection.execute(
            "SELECT origin_code, destination_code, COUNT(*) c FROM search_history WHERE telegram_user_id = ? GROUP BY origin_code, destination_code",
            (user_id,),
        ).fetchall()
        for row in route_rows:
            if news.get("related_origin_iata") == row[0]:
                score += 2 * int(row[2])
            if news.get("related_destination_iata") == row[1]:
                score += 3 * int(row[2])
    sub_rows = connection.execute("SELECT origin_code, destination_code, airline FROM subscriptions WHERE telegram_user_id = ? AND status = 'active'", (user_id,)).fetchall()
    for row in sub_rows:
        if news.get("related_origin_iata") == row[0]:
            score += 2
        if news.get("related_destination_iata") == row[1]:
            score += 3
        if news.get("airline_code") and news.get("airline_code") == row[2]:
            score += 4
    return score
