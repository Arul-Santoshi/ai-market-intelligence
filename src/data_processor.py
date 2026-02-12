import json
import logging
import os
from datetime import datetime, timedelta

from config import REPORT_FOLDER

logger = logging.getLogger(__name__)


def aggregate_data(
    stock_data: dict,
    news_data: list[dict],
    sentiment_data: dict,
    github_data: list[dict],
    economic_data: dict | None,
) -> dict:
    """Combine all data sources into a single structured payload."""
    now = datetime.now().isoformat()

    # Build fetch-time map from whatever timestamps each source provides
    stock_ts = None
    for info in stock_data.values():
        if info and "timestamp" in info:
            stock_ts = info["timestamp"]
            break

    fetch_timestamps = {
        "stocks": stock_ts or now,
        "news": now,
        "github": now,
        "economic": (economic_data or {}).get("last_updated", now),
        "sentiment": now,
        "aggregated_at": now,
    }

    return {
        "timestamp": now,
        "stocks": stock_data,
        "news": {
            "article_count": len(news_data),
            "articles": news_data,
        },
        "sentiment": sentiment_data,
        "github_trends": {
            "repo_count": len(github_data),
            "repos": github_data,
        },
        "economic": economic_data,
        "fetch_timestamps": fetch_timestamps,
    }


def compare_to_yesterday(today_data: dict, yesterday_data: dict | None) -> dict:
    """Produce a day-over-day comparison dict.

    Args:
        today_data: Today's aggregated data (from aggregate_data).
        yesterday_data: Yesterday's aggregated data, or None if unavailable.

    Returns:
        Comparison dict covering stocks, sentiment, and GitHub trends.
    """
    if yesterday_data is None:
        return {
            "stocks": {},
            "sentiment": {
                "today_sentiment": today_data.get("sentiment", {}).get("overall_sentiment", 0.5),
                "yesterday_sentiment": None,
                "change": None,
            },
            "github": {
                "new_repos": [r["name"] for r in today_data.get("github_trends", {}).get("repos", [])],
                "dropped_repos": [],
            },
        }

    # --- Stock comparison ---
    stock_comparison = {}
    today_stocks = today_data.get("stocks", {})
    yesterday_stocks = yesterday_data.get("stocks", {})

    for ticker, today_info in today_stocks.items():
        if today_info is None:
            continue
        yesterday_info = yesterday_stocks.get(ticker)
        today_price = today_info["current_price"]
        if yesterday_info:
            yesterday_price = yesterday_info["current_price"]
            change = today_price - yesterday_price
            change_pct = (change / yesterday_price) * 100 if yesterday_price else 0.0
        else:
            yesterday_price = None
            change = None
            change_pct = None

        stock_comparison[ticker] = {
            "today_price": today_price,
            "yesterday_price": yesterday_price,
            "change_percent": round(change_pct, 2) if change_pct is not None else None,
            "direction": ("up" if change > 0 else "down") if change is not None else None,
        }

    # --- Sentiment comparison ---
    today_sentiment = today_data.get("sentiment", {}).get("overall_sentiment", 0.5)
    yesterday_sentiment = yesterday_data.get("sentiment", {}).get("overall_sentiment", 0.5)
    sentiment_comparison = {
        "today_sentiment": today_sentiment,
        "yesterday_sentiment": yesterday_sentiment,
        "change": round(today_sentiment - yesterday_sentiment, 4),
    }

    # --- GitHub comparison ---
    today_repos = {r["name"] for r in today_data.get("github_trends", {}).get("repos", [])}
    yesterday_repos = {r["name"] for r in yesterday_data.get("github_trends", {}).get("repos", [])}
    github_comparison = {
        "new_repos": sorted(today_repos - yesterday_repos),
        "dropped_repos": sorted(yesterday_repos - today_repos),
    }

    return {
        "stocks": stock_comparison,
        "sentiment": sentiment_comparison,
        "github": github_comparison,
    }


def load_yesterday_data_from_file() -> dict | None:
    """Load yesterday's aggregated JSON data from the reports folder."""
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    path = os.path.join(REPORT_FOLDER, f"{yesterday}.json")

    if not os.path.exists(path):
        logger.info("No report found for %s", yesterday)
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info("Loaded yesterday's data from %s", path)
        return data
    except Exception as exc:
        logger.error("Failed to load %s: %s", path, exc)
        return None


def save_today_data(aggregated_data: dict) -> str:
    """Persist today's aggregated data as JSON for future comparison."""
    os.makedirs(REPORT_FOLDER, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(REPORT_FOLDER, f"{today}.json")

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(aggregated_data, f, indent=2, default=str)
        logger.info("Saved today's data to %s", path)
        return path
    except Exception as exc:
        logger.error("Failed to save today's data: %s", exc)
        return ""
