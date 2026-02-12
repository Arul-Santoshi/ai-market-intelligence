import json
import logging
import math
import os
from datetime import datetime

from config import REPORT_FOLDER

logger = logging.getLogger(__name__)


import re


_REDUNDANT_TITLES = re.compile(
    r"^\*{0,2}(executive\s+summary|market\s+analysis(\s+summary)?|key\s+insights"
    r"|summary|overview)\*{0,2}\s*$",
    re.IGNORECASE,
)


def _strip_claude_headers(text: str) -> str:
    """Remove markdown headers and redundant title lines from Claude output.

    Claude sometimes wraps its response in headers like '# Market Analysis'
    or '## Executive Summary'. We strip header markup entirely and also
    remove lines that are just a bare section title (since the report
    already has its own headings).
    """
    lines = text.strip().splitlines()
    cleaned = []
    for line in lines:
        # Strip markdown header prefix
        stripped = re.sub(r"^#{1,3}\s+", "", line).strip()
        # Drop lines that are just a redundant section title
        if _REDUNDANT_TITLES.match(stripped):
            continue
        # Drop blank bold-only title lines like "**Executive Summary**"
        bare = stripped.strip("*").strip()
        if _REDUNDANT_TITLES.match(bare):
            continue
        cleaned.append(line if not re.match(r"^#{1,3}\s+", line) else stripped)
    return "\n".join(cleaned)


def _direction_arrow(change: float | None) -> str:
    if change is None:
        return ""
    return "▲" if change >= 0 else "▼"


def _format_change(change: float | None) -> str:
    if change is None:
        return "N/A"
    sign = "+" if change >= 0 else ""
    return f"{sign}{change}%"


def generate_markdown_report(
    aggregated_data: dict,
    comparison_data: dict | None,
    insights: str,
    summary: str,
) -> str:
    """Build a full Markdown daily report from all data sources."""
    date_str = datetime.now().strftime("%B %d, %Y")
    lines: list[str] = []

    # ── Header ──────────────────────────────────────────────────────────
    lines.append(f"# Daily AI Market Intelligence Report")
    lines.append(f"**{date_str}**\n")

    # ── Executive Summary ───────────────────────────────────────────────
    lines.append("## Executive Summary")
    lines.append(f"{_strip_claude_headers(summary)}\n")

    # ── Stock Market Overview ───────────────────────────────────────────
    lines.append("## Stock Market Overview")
    lines.append("")
    lines.append("| Ticker | Price | Change | Direction |")
    lines.append("|--------|------:|-------:|:---------:|")

    stocks = aggregated_data.get("stocks", {})
    display_names = {
        "^GSPC": "S&P 500",
        "^IXIC": "NASDAQ",
        "NVDA": "NVDA",
        "MSFT": "MSFT",
        "AMZN": "AMZN",
    }
    for ticker, info in stocks.items():
        name = display_names.get(ticker, ticker)
        if info is None:
            lines.append(f"| {name} | — | — | — |")
            continue
        arrow = _direction_arrow(info["change_percent"])
        change = _format_change(info["change_percent"])
        lines.append(
            f"| {name} | ${info['current_price']:,.2f} | {change} | {arrow} |"
        )
    lines.append("")

    # ── AI News & Sentiment ─────────────────────────────────────────────
    lines.append("## AI News & Sentiment")
    sentiment = aggregated_data.get("sentiment", {})
    overall = sentiment.get("overall_sentiment", 0.5)
    pos = sentiment.get("positive_count", 0)
    neg = sentiment.get("negative_count", 0)
    neu = sentiment.get("neutral_count", 0)

    lines.append(f"- **Overall Sentiment Score:** {overall:.1%}")
    lines.append(f"- Positive: {pos} | Negative: {neg} | Neutral: {neu}")
    lines.append("")

    # Top 5 headlines
    articles = sentiment.get("articles_with_sentiment", [])[:5]
    if articles:
        lines.append("### Top Headlines")
        lines.append("")
        for a in articles:
            label = a.get("sentiment_label", "neutral")
            emoji = {"positive": "+", "negative": "-", "neutral": "~"}.get(label, "~")
            lines.append(f"- [{emoji}] **{a['headline']}**")
        lines.append("")

    # ── GitHub Trending AI Projects ─────────────────────────────────────
    lines.append("## GitHub Trending AI Projects")
    lines.append("")
    repos = aggregated_data.get("github_trends", {}).get("repos", [])[:5]
    if repos:
        lines.append("| Repo | Stars | Language | Description |")
        lines.append("|------|------:|----------|-------------|")
        for r in repos:
            name = r.get("name", "")
            url = r.get("url", "")
            display = f"[{name}]({url})" if url else name
            desc = (r.get("description") or "")[:80]
            lines.append(
                f"| {display} | {r.get('stars', 0):,} "
                f"| {r.get('language', '—')} | {desc} |"
            )
        lines.append("")
    else:
        lines.append("_No trending repos found._\n")

    # ── Economic Context ────────────────────────────────────────────────
    lines.append("## Economic Context")
    economic = aggregated_data.get("economic") or {}
    unemp = economic.get("unemployment_rate")
    infl = economic.get("inflation_rate")
    lines.append(f"- **Unemployment Rate:** {f'{unemp}%' if unemp is not None else 'N/A'}")
    lines.append(f"- **Inflation Rate (CPI):** {f'{infl}%' if infl is not None else 'N/A'}")
    lines.append("")

    # ── Key Insights (Claude) ───────────────────────────────────────────
    lines.append("## Key Insights")
    lines.append(f"{_strip_claude_headers(insights)}\n")

    # ── Comparison to Yesterday ─────────────────────────────────────────
    lines.append("## Comparison to Yesterday")
    if comparison_data:
        # Stock changes
        stock_cmp = comparison_data.get("stocks", {})
        if stock_cmp:
            lines.append("")
            lines.append("| Ticker | Yesterday | Today | Change | Direction |")
            lines.append("|--------|----------:|------:|-------:|:---------:|")
            for ticker, cmp in stock_cmp.items():
                name = display_names.get(ticker, ticker)
                yp = cmp.get("yesterday_price")
                tp = cmp.get("today_price")
                cp = cmp.get("change_percent")
                d = cmp.get("direction", "—")
                arrow = _direction_arrow(cp)
                lines.append(
                    f"| {name} "
                    f"| {'$' + f'{yp:,.2f}' if yp is not None else '—'} "
                    f"| {'$' + f'{tp:,.2f}' if tp is not None else '—'} "
                    f"| {_format_change(cp)} | {arrow} |"
                )
            lines.append("")

        # Sentiment change
        sent_cmp = comparison_data.get("sentiment", {})
        if sent_cmp.get("yesterday_sentiment") is not None:
            change = sent_cmp.get("change")
            direction = "improved" if change and change > 0 else "declined"
            lines.append(
                f"- **Sentiment:** {direction} "
                f"({sent_cmp.get('yesterday_sentiment', 0):.1%} → "
                f"{sent_cmp.get('today_sentiment', 0):.1%})"
            )
        else:
            lines.append("- **Sentiment:** No previous data for comparison")

        # New / dropped repos (cap at 5 for readability)
        gh_cmp = comparison_data.get("github", {})
        new_repos = gh_cmp.get("new_repos", [])[:5]
        dropped = gh_cmp.get("dropped_repos", [])[:5]
        if new_repos:
            lines.append(f"- **New trending repos:** {', '.join(new_repos)}")
        if dropped:
            lines.append(f"- **Dropped from trending:** {', '.join(dropped)}")
    else:
        lines.append("_No previous day data available for comparison._")
    lines.append("")

    # ── Notable Anomalies ───────────────────────────────────────────────
    lines.append("## Notable Anomalies")
    anomalies = _detect_anomalies(aggregated_data, comparison_data)
    if anomalies:
        for a in anomalies:
            lines.append(f"- {a}")
    else:
        lines.append("_No significant anomalies detected today._")
    lines.append("")

    # ── Footer ──────────────────────────────────────────────────────────
    lines.append("---")
    lines.append(
        f"*Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
        f"by AI Market Intelligence*"
    )

    return "\n".join(lines)


# Fallback thresholds used when not enough historical data for volatility calc
_INDEX_TICKERS = {"^GSPC", "^IXIC"}
_FALLBACK_THRESHOLD_INDEX = 1.5   # indices are less volatile
_FALLBACK_THRESHOLD_STOCK = 3.0   # individual stocks swing more


def _detect_anomalies(
    aggregated_data: dict,
    comparison_data: dict | None = None,
) -> list[str]:
    """Flag unusual stock moves, sentiment extremes, correlated moves, and shifts.

    Uses historical volatility from the database when available (>= 5 data
    points).  Falls back to calibrated flat thresholds for indices vs
    individual stocks when history is too short.
    """
    flags: list[str] = []

    # --- Load historical volatility (best-effort) -------------------------
    try:
        from src.database_handler import get_historical_stock_volatility
        hist = get_historical_stock_volatility(30)
    except Exception:
        hist = {}

    # --- Per-ticker anomaly detection -------------------------------------
    stocks = aggregated_data.get("stocks", {})
    display_names = {
        "^GSPC": "S&P 500", "^IXIC": "NASDAQ",
        "NVDA": "NVDA", "MSFT": "MSFT", "AMZN": "AMZN",
    }

    up_count = 0
    down_count = 0

    for ticker, info in stocks.items():
        if info is None:
            continue
        change = info.get("change_percent", 0)
        abs_change = abs(change)
        direction = "gain" if change > 0 else "drop"
        name = display_names.get(ticker, ticker)

        history = hist.get(ticker, [])

        if len(history) >= 5:
            # Volatility-based detection: flag moves > 1.5 standard deviations
            mean = sum(history) / len(history)
            variance = sum((x - mean) ** 2 for x in history) / len(history)
            std = math.sqrt(variance) if variance > 0 else 0.0

            if std > 0:
                sigma = abs(change - mean) / std
                if sigma >= 1.5:
                    flags.append(
                        f"**{name}** had a significant {direction} of "
                        f"{change:+.2f}% ({sigma:.1f} sigma)"
                    )
            elif abs_change >= 1.0:
                # Zero std (all identical history) but still moved
                flags.append(
                    f"**{name}** had a significant {direction} of {change:+.2f}%"
                )
        else:
            # Fallback: calibrated flat thresholds
            threshold = (
                _FALLBACK_THRESHOLD_INDEX if ticker in _INDEX_TICKERS
                else _FALLBACK_THRESHOLD_STOCK
            )
            if abs_change >= threshold:
                flags.append(
                    f"**{name}** had a significant {direction} of {change:+.2f}%"
                )

        # Track direction for correlated-move check
        if change > 1.0:
            up_count += 1
        elif change < -1.0:
            down_count += 1

    # --- Correlated move detection ----------------------------------------
    total_tracked = len([t for t, i in stocks.items() if i is not None])
    if total_tracked >= 3:
        if up_count >= 3:
            flags.append(
                f"Broad market rally: {up_count}/{total_tracked} tracked "
                f"assets gained > 1%"
            )
        elif down_count >= 3:
            flags.append(
                f"Broad market selloff: {down_count}/{total_tracked} tracked "
                f"assets dropped > 1%"
            )

    # --- Sentiment anomalies ----------------------------------------------
    sentiment = aggregated_data.get("sentiment", {})
    overall = sentiment.get("overall_sentiment", 0.5)
    if overall >= 0.85:
        flags.append("AI news sentiment is unusually positive today")
    elif overall <= 0.25:
        flags.append("AI news sentiment is unusually negative today")

    # Sentiment shift from yesterday
    if comparison_data:
        sent_cmp = comparison_data.get("sentiment", {})
        yesterday_sent = sent_cmp.get("yesterday_sentiment")
        today_sent = sent_cmp.get("today_sentiment", overall)
        if yesterday_sent is not None:
            shift = today_sent - yesterday_sent
            if abs(shift) >= 0.15:
                direction = "surged" if shift > 0 else "dropped"
                flags.append(
                    f"Sentiment {direction} sharply vs yesterday "
                    f"({yesterday_sent:.0%} -> {today_sent:.0%})"
                )

    return flags


def save_report(report_markdown: str, aggregated_data: dict, date: str | None = None) -> tuple[str, str]:
    """Persist report as Markdown and raw data as JSON.

    Args:
        report_markdown: The formatted report text.
        aggregated_data: Raw aggregated data dict.
        date: Date string (YYYY-MM-DD). Defaults to today.

    Returns:
        Tuple of (markdown_path, json_path).
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    os.makedirs(REPORT_FOLDER, exist_ok=True)
    md_path = os.path.join(REPORT_FOLDER, f"daily_report_{date}.md")
    json_path = os.path.join(REPORT_FOLDER, f"daily_report_{date}.json")

    try:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(report_markdown)
        logger.info("Markdown report saved to %s", md_path)
    except Exception as exc:
        logger.error("Failed to save markdown report: %s", exc)
        md_path = ""

    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(aggregated_data, f, indent=2, default=str)
        logger.info("JSON data saved to %s", json_path)
    except Exception as exc:
        logger.error("Failed to save JSON data: %s", exc)
        json_path = ""

    return md_path, json_path
