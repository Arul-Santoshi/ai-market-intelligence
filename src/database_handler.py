import logging
import sqlite3
from datetime import datetime, timedelta

from config import DATABASE_PATH

logger = logging.getLogger(__name__)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def init_database() -> sqlite3.Connection:
    """Create all tables if they don't already exist. Returns the connection."""
    conn = _connect()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_reports (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            date            DATE    UNIQUE NOT NULL,
            markdown_content TEXT,
            summary         TEXT,
            overall_sentiment REAL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS stock_prices (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            date            DATE    NOT NULL,
            ticker          TEXT    NOT NULL,
            price           REAL,
            change_percent  REAL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, ticker)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sentiment_scores (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            date            DATE    UNIQUE NOT NULL,
            overall_sentiment REAL,
            positive_count  INTEGER,
            negative_count  INTEGER,
            neutral_count   INTEGER,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS github_trends (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            date            DATE    NOT NULL,
            repo_name       TEXT,
            stars           INTEGER,
            language        TEXT,
            url             TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, repo_name)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS economic_data (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            date            DATE    UNIQUE NOT NULL,
            unemployment_rate REAL,
            inflation_rate  REAL,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    logger.info("Database initialised at %s", DATABASE_PATH)
    return conn


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

def store_daily_data(
    date: str,
    aggregated_data: dict,
    report_markdown: str,
    summary: str,
) -> bool:
    """Insert (or update) all tables for a given date.

    Args:
        date: YYYY-MM-DD string.
        aggregated_data: Output of data_processor.aggregate_data().
        report_markdown: Full markdown report text.
        summary: Executive summary text.

    Returns:
        True on success, False on error.
    """
    try:
        conn = _connect()
        cur = conn.cursor()

        # -- daily_reports --
        overall_sentiment = (
            aggregated_data.get("sentiment", {}).get("overall_sentiment")
        )
        cur.execute(
            """
            INSERT INTO daily_reports (date, markdown_content, summary, overall_sentiment)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                markdown_content  = excluded.markdown_content,
                summary           = excluded.summary,
                overall_sentiment = excluded.overall_sentiment,
                created_at        = CURRENT_TIMESTAMP
            """,
            (date, report_markdown, summary, overall_sentiment),
        )

        # -- stock_prices --
        stocks = aggregated_data.get("stocks", {})
        for ticker, info in stocks.items():
            if info is None:
                continue
            cur.execute(
                """
                INSERT INTO stock_prices (date, ticker, price, change_percent)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(date, ticker) DO UPDATE SET
                    price          = excluded.price,
                    change_percent = excluded.change_percent,
                    created_at     = CURRENT_TIMESTAMP
                """,
                (date, ticker, info["current_price"], info["change_percent"]),
            )

        # -- sentiment_scores --
        sentiment = aggregated_data.get("sentiment", {})
        cur.execute(
            """
            INSERT INTO sentiment_scores
                (date, overall_sentiment, positive_count, negative_count, neutral_count)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                overall_sentiment = excluded.overall_sentiment,
                positive_count    = excluded.positive_count,
                negative_count    = excluded.negative_count,
                neutral_count     = excluded.neutral_count,
                created_at        = CURRENT_TIMESTAMP
            """,
            (
                date,
                sentiment.get("overall_sentiment"),
                sentiment.get("positive_count", 0),
                sentiment.get("negative_count", 0),
                sentiment.get("neutral_count", 0),
            ),
        )

        # -- github_trends --
        repos = aggregated_data.get("github_trends", {}).get("repos", [])
        for r in repos:
            cur.execute(
                """
                INSERT INTO github_trends (date, repo_name, stars, language, url)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(date, repo_name) DO UPDATE SET
                    stars      = excluded.stars,
                    language   = excluded.language,
                    url        = excluded.url,
                    created_at = CURRENT_TIMESTAMP
                """,
                (date, r.get("name"), r.get("stars"), r.get("language"), r.get("url")),
            )

        # -- economic_data --
        economic = aggregated_data.get("economic") or {}
        cur.execute(
            """
            INSERT INTO economic_data (date, unemployment_rate, inflation_rate)
            VALUES (?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                unemployment_rate = excluded.unemployment_rate,
                inflation_rate    = excluded.inflation_rate,
                created_at        = CURRENT_TIMESTAMP
            """,
            (date, economic.get("unemployment_rate"), economic.get("inflation_rate")),
        )

        conn.commit()
        conn.close()
        logger.info("Stored daily data for %s", date)
        return True

    except Exception as exc:
        logger.error("Failed to store daily data for %s: %s", date, exc)
        return False


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def get_historical_data(days: int = 30) -> dict:
    """Return the last *days* of stock prices, sentiment, and economic data.

    Returns:
        {
            "stock_prices":  [rows],
            "sentiment":     [rows],
            "economic":      [rows],
        }
    """
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _connect()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM stock_prices WHERE date >= ? ORDER BY date", (since,)
    )
    stock_rows = [dict(r) for r in cur.fetchall()]

    cur.execute(
        "SELECT * FROM sentiment_scores WHERE date >= ? ORDER BY date", (since,)
    )
    sentiment_rows = [dict(r) for r in cur.fetchall()]

    cur.execute(
        "SELECT * FROM economic_data WHERE date >= ? ORDER BY date", (since,)
    )
    economic_rows = [dict(r) for r in cur.fetchall()]

    conn.close()
    return {
        "stock_prices": stock_rows,
        "sentiment": sentiment_rows,
        "economic": economic_rows,
    }


def get_yesterday_data() -> dict | None:
    """Return yesterday's aggregated data reconstructed from the database."""
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    conn = _connect()
    cur = conn.cursor()

    # Report
    cur.execute("SELECT * FROM daily_reports WHERE date = ?", (yesterday,))
    report_row = cur.fetchone()
    if report_row is None:
        conn.close()
        return None

    # Stocks
    cur.execute("SELECT * FROM stock_prices WHERE date = ?", (yesterday,))
    stock_rows = cur.fetchall()
    stocks = {}
    for row in stock_rows:
        stocks[row["ticker"]] = {
            "current_price": row["price"],
            "previous_price": None,
            "change_percent": row["change_percent"],
            "change_absolute": None,
            "timestamp": row["date"],
        }

    # Sentiment
    cur.execute("SELECT * FROM sentiment_scores WHERE date = ?", (yesterday,))
    sent_row = cur.fetchone()
    sentiment = {}
    if sent_row:
        sentiment = {
            "overall_sentiment": sent_row["overall_sentiment"],
            "positive_count": sent_row["positive_count"],
            "negative_count": sent_row["negative_count"],
            "neutral_count": sent_row["neutral_count"],
            "articles_with_sentiment": [],
        }

    # GitHub
    cur.execute("SELECT * FROM github_trends WHERE date = ?", (yesterday,))
    gh_rows = cur.fetchall()
    repos = [
        {
            "name": r["repo_name"],
            "stars": r["stars"],
            "language": r["language"],
            "url": r["url"],
            "description": "",
            "topics": [],
        }
        for r in gh_rows
    ]

    # Economic
    cur.execute("SELECT * FROM economic_data WHERE date = ?", (yesterday,))
    econ_row = cur.fetchone()
    economic = None
    if econ_row:
        economic = {
            "unemployment_rate": econ_row["unemployment_rate"],
            "inflation_rate": econ_row["inflation_rate"],
            "last_updated": econ_row["date"],
        }

    conn.close()

    return {
        "timestamp": yesterday,
        "stocks": stocks,
        "news": {"article_count": 0, "articles": []},
        "sentiment": sentiment,
        "github_trends": {"repo_count": len(repos), "repos": repos},
        "economic": economic,
    }


def get_historical_stock_volatility(days: int = 30) -> dict[str, list[float]]:
    """Return recent change_percent values grouped by ticker for volatility calc.

    Args:
        days: How many days of history to pull. Defaults to 30.

    Returns:
        Dict mapping ticker symbols to lists of change_percent values,
        e.g. ``{"^GSPC": [-0.12, 0.45, ...], "NVDA": [1.2, -2.3, ...]}``.
    """
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT ticker, change_percent FROM stock_prices "
        "WHERE date >= ? AND change_percent IS NOT NULL ORDER BY date",
        (since,),
    )
    rows = cur.fetchall()
    conn.close()

    result: dict[str, list[float]] = {}
    for row in rows:
        ticker = row["ticker"]
        result.setdefault(ticker, []).append(row["change_percent"])
    return result


def get_report_by_date(date: str) -> str | None:
    """Return the markdown report for *date* (YYYY-MM-DD), or None."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT markdown_content FROM daily_reports WHERE date = ?", (date,))
    row = cur.fetchone()
    conn.close()
    if row:
        return row["markdown_content"]
    return None
