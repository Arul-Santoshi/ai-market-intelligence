"""AI Market Intelligence — entry point.

Usage:
    python -m src.main           # start the 8:00 AM scheduler
    python -m src.main --test    # run the pipeline immediately (once)
"""

import argparse
import logging
import os
import sys
import time
from logging.handlers import TimedRotatingFileHandler

from config import LOGS_FOLDER
from src.database_handler import init_database
from src.scheduler import run_daily_report, start_scheduler, stop_scheduler


def _setup_logging() -> None:
    """Configure root logger: console + rotating file."""
    os.makedirs(LOGS_FOLDER, exist_ok=True)
    log_path = os.path.join(LOGS_FOLDER, "scheduler.log")

    fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    # File handler — rotate daily, keep 30 days
    file_handler = TimedRotatingFileHandler(
        log_path, when="midnight", backupCount=30, encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    console_handler.setLevel(logging.INFO)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console_handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Market Intelligence")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run the daily report pipeline immediately instead of waiting for the scheduled time.",
    )
    args = parser.parse_args()

    _setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Initialising database...")
    init_database()

    if args.test:
        logger.info("--test flag detected — running pipeline now")
        status = run_daily_report()
        logger.info("Pipeline finished. Status: %s", status)
        print("\nPhase 3 complete! Scheduler is live. Reports will run daily at 8:00 AM.")
        return

    scheduler = start_scheduler()
    print("Scheduler running. Press Ctrl+C to stop.")
    print("Phase 3 complete! Scheduler is live. Reports will run daily at 8:00 AM.")

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown requested")
        stop_scheduler(scheduler)
        print("\nScheduler stopped. Goodbye!")


if __name__ == "__main__":
    main()
