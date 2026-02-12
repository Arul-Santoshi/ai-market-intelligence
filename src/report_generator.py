import json
import logging
import os
from datetime import datetime

from config import REPORT_FOLDER

logger = logging.getLogger(__name__)


import re


def _strip_claude_headers(text: str) -> str:
    """Remove markdown headers that Claude adds to its own output.

    Claude sometimes wraps its response in headers like '# Market Analysis'
    or '## Executive Summary'. These clash with the report's own structure,
    so we strip any leading H1/H2/H3 lines.
    """
    lines = text.strip().splitlines()
    cleaned = []
    for line in lines:
        if re.match(r"^#{1,3}\s+", line):
            # Keep the text content but drop the header markup
            cleaned.append(re.sub(r"^#{1,3}\s+", "**", line) + "**")
        else:
            cleaned.append(line)
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
    anomalies = _detect_anomalies(aggregated_data)
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


def _detect_anomalies(aggregated_data: dict) -> list[str]:
    """Flag large stock moves or extreme sentiment."""
    flags: list[str] = []
    stocks = aggregated_data.get("stocks", {})
    for ticker, info in stocks.items():
        if info is None:
            continue
        pct = abs(info.get("change_percent", 0))
        if pct >= 2.0:
            direction = "gain" if info["change_percent"] > 0 else "drop"
            flags.append(f"**{ticker}** had a significant {direction} of {info['change_percent']}%")

    sentiment = aggregated_data.get("sentiment", {})
    overall = sentiment.get("overall_sentiment", 0.5)
    if overall >= 0.85:
        flags.append("AI news sentiment is unusually positive today")
    elif overall <= 0.25:
        flags.append("AI news sentiment is unusually negative today")

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
