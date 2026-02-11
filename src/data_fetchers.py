import logging
from datetime import datetime, timedelta

import requests
import yfinance as yf
from newsapi import NewsApiClient

from config import (
    AI_NEWS_KEYWORDS,
    FRED_API_KEY,
    GITHUB_KEYWORDS,
    GITHUB_LANGUAGES,
    GITHUB_TOP_N,
    NEWSAPI_KEY,
    STOCK_TICKERS,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stock prices
# ---------------------------------------------------------------------------

def fetch_stock_prices() -> dict:
    """Fetch current prices for all configured tickers via yfinance."""
    results = {}
    for ticker_symbol in STOCK_TICKERS:
        try:
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.fast_info
            current = info.last_price
            previous = info.previous_close
            change_abs = current - previous
            change_pct = (change_abs / previous) * 100 if previous else 0.0

            results[ticker_symbol] = {
                "current_price": round(current, 2),
                "previous_price": round(previous, 2),
                "change_percent": round(change_pct, 2),
                "change_absolute": round(change_abs, 2),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as exc:
            logger.error("Failed to fetch %s: %s", ticker_symbol, exc)
            results[ticker_symbol] = None
    return results


def get_yesterday_stock_data() -> dict:
    """Fetch previous trading day's closing data for comparison."""
    results = {}
    end = datetime.now()
    start = end - timedelta(days=5)  # buffer for weekends / holidays

    for ticker_symbol in STOCK_TICKERS:
        try:
            hist = yf.Ticker(ticker_symbol).history(start=start, end=end)
            if len(hist) < 2:
                results[ticker_symbol] = None
                continue

            yesterday = hist.iloc[-2]
            day_before = hist.iloc[-3] if len(hist) >= 3 else hist.iloc[-2]
            close = float(yesterday["Close"])
            prev_close = float(day_before["Close"])
            change_abs = close - prev_close
            change_pct = (change_abs / prev_close) * 100 if prev_close else 0.0

            results[ticker_symbol] = {
                "current_price": round(close, 2),
                "previous_price": round(prev_close, 2),
                "change_percent": round(change_pct, 2),
                "change_absolute": round(change_abs, 2),
                "timestamp": yesterday.name.isoformat(),
            }
        except Exception as exc:
            logger.error("Failed to fetch yesterday data for %s: %s", ticker_symbol, exc)
            results[ticker_symbol] = None
    return results


# ---------------------------------------------------------------------------
# AI news
# ---------------------------------------------------------------------------

def fetch_ai_news() -> list[dict]:
    """Fetch recent AI-related articles from NewsAPI (last 24 hours)."""
    if not NEWSAPI_KEY:
        logger.warning("NEWSAPI_KEY not set — skipping news fetch")
        return []

    try:
        client = NewsApiClient(api_key=NEWSAPI_KEY)
        query = " OR ".join(AI_NEWS_KEYWORDS)
        from_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        response = client.get_everything(
            q=query,
            from_param=from_date,
            language="en",
            sort_by="publishedAt",
            page_size=50,
        )

        articles = []
        for article in response.get("articles", []):
            articles.append({
                "headline": article.get("title", ""),
                "source": article.get("source", {}).get("name", "Unknown"),
                "url": article.get("url", ""),
                "published_at": article.get("publishedAt", ""),
                "description": article.get("description", ""),
            })
        logger.info("Fetched %d AI news articles", len(articles))
        return articles

    except Exception as exc:
        logger.error("NewsAPI fetch failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# GitHub trending
# ---------------------------------------------------------------------------

def fetch_github_trending() -> list[dict]:
    """Fetch trending AI/ML repos from GitHub Search API (last 7 days)."""
    since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    keyword_query = " OR ".join(GITHUB_KEYWORDS)
    language_query = " ".join(f"language:{lang}" for lang in GITHUB_LANGUAGES)
    query = f"{keyword_query} {language_query} created:>{since}"

    url = "https://api.github.com/search/repositories"
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": GITHUB_TOP_N,
    }
    headers = {"Accept": "application/vnd.github.v3+json"}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        repos = []
        for item in data.get("items", [])[:GITHUB_TOP_N]:
            repos.append({
                "name": item.get("full_name", ""),
                "description": item.get("description", ""),
                "stars": item.get("stargazers_count", 0),
                "language": item.get("language", ""),
                "url": item.get("html_url", ""),
                "topics": item.get("topics", []),
            })
        logger.info("Fetched %d trending GitHub repos", len(repos))
        return repos

    except Exception as exc:
        logger.error("GitHub trending fetch failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Economic indicators (FRED)
# ---------------------------------------------------------------------------

def fetch_economic_indicators() -> dict | None:
    """Fetch unemployment and inflation rates from FRED API."""
    if not FRED_API_KEY:
        logger.warning("FRED_API_KEY not set — returning fallback values")
        return {
            "unemployment_rate": None,
            "inflation_rate": None,
            "last_updated": datetime.now().isoformat(),
            "source": "unavailable",
        }

    base_url = "https://api.stlouisfed.org/fred/series/observations"
    indicators = {}

    series_map = {
        "unemployment_rate": "UNRATE",
        "inflation_rate": "CPIAUCSL",
    }

    for key, series_id in series_map.items():
        try:
            params = {
                "series_id": series_id,
                "api_key": FRED_API_KEY,
                "file_type": "json",
                "limit": 1,
                "sort_order": "desc",
            }
            resp = requests.get(base_url, params=params, timeout=15)
            resp.raise_for_status()
            observations = resp.json().get("observations", [])
            if observations:
                indicators[key] = float(observations[0]["value"])
            else:
                indicators[key] = None
        except Exception as exc:
            logger.error("FRED fetch failed for %s: %s", series_id, exc)
            indicators[key] = None

    indicators["last_updated"] = datetime.now().isoformat()
    indicators["source"] = "FRED"
    return indicators
