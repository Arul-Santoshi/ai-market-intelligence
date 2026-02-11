import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config import GMAIL_EMAIL, SCHEDULED_TIME
from src.claude_analyzer import generate_insights, generate_summary
from src.data_fetchers import (
    fetch_ai_news,
    fetch_economic_indicators,
    fetch_github_trending,
    fetch_stock_prices,
)
from src.data_processor import aggregate_data, compare_to_yesterday
from src.database_handler import (
    get_yesterday_data,
    init_database,
    store_daily_data,
)
from src.email_sender import send_report_email, setup_gmail_credentials
from src.report_generator import generate_markdown_report, save_report
from src.sentiment_analyzer import analyze_ai_news_sentiment

logger = logging.getLogger(__name__)


def run_daily_report() -> dict:
    """Execute the full daily pipeline.

    Steps:
        1. Fetch data (stocks, news, GitHub, economic)
        2. Analyse sentiment
        3. Load yesterday's data from DB
        4. Aggregate and compare
        5. Generate Claude insights + summary
        6. Build Markdown report
        7. Persist to database + files
        8. Send email

    Returns:
        Dict mapping step names to "success" / error message.
    """
    status: dict[str, str] = {}
    today = datetime.now().strftime("%Y-%m-%d")
    logger.info("===== Starting daily report for %s =====", today)

    # 1 — Fetch data --------------------------------------------------------
    try:
        stock_data = fetch_stock_prices()
        status["fetch_stocks"] = "success"
        logger.info("Stocks fetched")
    except Exception as exc:
        stock_data = {}
        status["fetch_stocks"] = str(exc)
        logger.error("Stock fetch failed: %s", exc)

    try:
        news_data = fetch_ai_news()
        status["fetch_news"] = "success"
        logger.info("News fetched (%d articles)", len(news_data))
    except Exception as exc:
        news_data = []
        status["fetch_news"] = str(exc)
        logger.error("News fetch failed: %s", exc)

    try:
        github_data = fetch_github_trending()
        status["fetch_github"] = "success"
        logger.info("GitHub trends fetched (%d repos)", len(github_data))
    except Exception as exc:
        github_data = []
        status["fetch_github"] = str(exc)
        logger.error("GitHub fetch failed: %s", exc)

    try:
        economic_data = fetch_economic_indicators()
        status["fetch_economic"] = "success"
        logger.info("Economic indicators fetched")
    except Exception as exc:
        economic_data = None
        status["fetch_economic"] = str(exc)
        logger.error("Economic fetch failed: %s", exc)

    # 2 — Sentiment ----------------------------------------------------------
    try:
        sentiment_data = analyze_ai_news_sentiment(news_data)
        status["sentiment"] = "success"
        logger.info("Sentiment analysis complete")
    except Exception as exc:
        sentiment_data = {
            "overall_sentiment": 0.5,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "articles_with_sentiment": [],
        }
        status["sentiment"] = str(exc)
        logger.error("Sentiment analysis failed: %s", exc)

    # 3 — Yesterday's data ---------------------------------------------------
    try:
        yesterday_data = get_yesterday_data()
        status["load_yesterday"] = "success" if yesterday_data else "no data"
        logger.info("Yesterday data: %s", "found" if yesterday_data else "not found")
    except Exception as exc:
        yesterday_data = None
        status["load_yesterday"] = str(exc)
        logger.error("Failed to load yesterday's data: %s", exc)

    # 4 — Aggregate & compare ------------------------------------------------
    try:
        aggregated = aggregate_data(
            stock_data, news_data, sentiment_data, github_data, economic_data
        )
        comparison = compare_to_yesterday(aggregated, yesterday_data)
        status["aggregate"] = "success"
        logger.info("Data aggregated and compared")
    except Exception as exc:
        aggregated = {}
        comparison = None
        status["aggregate"] = str(exc)
        logger.error("Aggregation failed: %s", exc)

    # 5 — Claude insights ----------------------------------------------------
    try:
        insights = generate_insights(aggregated, comparison)
        summary = generate_summary(aggregated, insights)
        status["claude_analysis"] = "success"
        logger.info("Claude analysis complete")
    except Exception as exc:
        insights = "_Insights unavailable._"
        summary = "_Summary unavailable._"
        status["claude_analysis"] = str(exc)
        logger.error("Claude analysis failed: %s", exc)

    # 6 — Report -------------------------------------------------------------
    try:
        report_md = generate_markdown_report(aggregated, comparison, insights, summary)
        save_report(report_md, aggregated, today)
        status["report"] = "success"
        logger.info("Report generated and saved")
    except Exception as exc:
        report_md = ""
        status["report"] = str(exc)
        logger.error("Report generation failed: %s", exc)

    # 7 — Database -----------------------------------------------------------
    try:
        init_database()
        stored = store_daily_data(today, aggregated, report_md, summary)
        status["database"] = "success" if stored else "store returned False"
        logger.info("Database storage: %s", status["database"])
    except Exception as exc:
        status["database"] = str(exc)
        logger.error("Database storage failed: %s", exc)

    # 8 — Email --------------------------------------------------------------
    try:
        if GMAIL_EMAIL and report_md:
            sent = send_report_email(GMAIL_EMAIL, report_md, today)
            status["email"] = "success" if sent else "send returned False"
        else:
            status["email"] = "skipped (no GMAIL_EMAIL or empty report)"
        logger.info("Email step: %s", status["email"])
    except Exception as exc:
        status["email"] = str(exc)
        logger.error("Email send failed: %s", exc)

    logger.info("===== Daily report finished for %s =====", today)
    logger.info("Status: %s", status)
    return status


# ---------------------------------------------------------------------------
# Scheduler management
# ---------------------------------------------------------------------------

_scheduler: BackgroundScheduler | None = None


def schedule_daily_job() -> BackgroundScheduler:
    """Create a BackgroundScheduler with the daily report job."""
    global _scheduler
    hour, minute = (int(p) for p in SCHEDULED_TIME.split(":"))

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        run_daily_report,
        trigger=CronTrigger(hour=hour, minute=minute),
        id="daily_report",
        name="Daily AI Market Intelligence Report",
        replace_existing=True,
    )
    return _scheduler


def start_scheduler() -> BackgroundScheduler:
    """Start the background scheduler and log the next run time."""
    scheduler = schedule_daily_job()
    scheduler.start()

    next_run = get_next_run_time(scheduler)
    logger.info("Scheduler started. Next run: %s", next_run)
    return scheduler


def stop_scheduler(scheduler: BackgroundScheduler | None = None) -> None:
    """Gracefully shut down the scheduler."""
    sched = scheduler or _scheduler
    if sched and sched.running:
        sched.shutdown(wait=False)
        logger.info("Scheduler stopped")


def get_next_run_time(scheduler: BackgroundScheduler | None = None) -> datetime | None:
    """Return the next scheduled execution time."""
    sched = scheduler or _scheduler
    if sched is None:
        return None
    job = sched.get_job("daily_report")
    if job is None:
        return None
    return job.next_run_time
