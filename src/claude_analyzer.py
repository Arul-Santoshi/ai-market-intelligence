import json
import logging

import anthropic

from config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_INSIGHTS = (
    "You are a financial and tech market analyst. Analyze the provided market data, "
    "AI news sentiment, GitHub trends, and economic indicators. Provide concise "
    "insights about: 1) What drove market movements today, 2) What's driving AI "
    "sector sentiment, 3) Emerging tech trends on GitHub, 4) Any notable anomalies "
    "or risks. Use bold text for sub-section labels. Keep it to 2-3 paragraphs max. "
    "IMPORTANT: Do NOT include any markdown headers (no # or ## lines). Do NOT start "
    "with a title like 'Market Analysis Summary'. Jump straight into the analysis."
)

SYSTEM_PROMPT_SUMMARY = (
    "Summarize today's market and tech landscape in 2-3 sentences for an executive "
    "summary. Focus on: overall market direction, AI sector health, key tech trends. "
    "IMPORTANT: Do NOT include any title or header. Do NOT start with 'Executive Summary'. "
    "Just write the 2-3 sentence summary directly."
)


def _format_data_for_prompt(aggregated_data: dict, comparison_data: dict | None = None) -> str:
    """Convert aggregated data into a readable string for Claude."""
    parts = []

    # Stocks
    stocks = aggregated_data.get("stocks", {})
    if stocks:
        parts.append("## Stock Prices")
        for ticker, info in stocks.items():
            if info is None:
                parts.append(f"- {ticker}: unavailable")
                continue
            direction = "up" if info["change_percent"] >= 0 else "down"
            parts.append(
                f"- {ticker}: ${info['current_price']} "
                f"({direction} {info['change_percent']}%)"
            )

    # Sentiment
    sentiment = aggregated_data.get("sentiment", {})
    if sentiment:
        parts.append("\n## AI News Sentiment")
        parts.append(f"- Overall score: {sentiment.get('overall_sentiment', 'N/A')}")
        parts.append(f"- Positive: {sentiment.get('positive_count', 0)}")
        parts.append(f"- Negative: {sentiment.get('negative_count', 0)}")
        parts.append(f"- Neutral: {sentiment.get('neutral_count', 0)}")

    # Top news headlines
    news = aggregated_data.get("news", {})
    articles = news.get("articles", [])[:10]
    if articles:
        parts.append("\n## Top AI Headlines")
        for a in articles:
            parts.append(f"- {a.get('headline', '')} ({a.get('source', '')})")

    # GitHub trends
    github = aggregated_data.get("github_trends", {})
    repos = github.get("repos", [])[:10]
    if repos:
        parts.append("\n## Trending GitHub AI/ML Repos")
        for r in repos:
            parts.append(
                f"- {r['name']} ({r.get('language', '?')}, "
                f"{r.get('stars', 0)} stars): {r.get('description', '')}"
            )

    # Economic indicators
    economic = aggregated_data.get("economic")
    if economic:
        parts.append("\n## Economic Indicators")
        parts.append(f"- Unemployment rate: {economic.get('unemployment_rate', 'N/A')}")
        parts.append(f"- Inflation rate (CPI): {economic.get('inflation_rate', 'N/A')}")

    # Day-over-day comparison
    if comparison_data:
        parts.append("\n## Day-over-Day Changes")
        stock_cmp = comparison_data.get("stocks", {})
        for ticker, cmp in stock_cmp.items():
            if cmp.get("change_percent") is not None:
                parts.append(
                    f"- {ticker}: {cmp['direction']} {cmp['change_percent']}% "
                    f"(${cmp.get('yesterday_price')} -> ${cmp.get('today_price')})"
                )
        sent_cmp = comparison_data.get("sentiment", {})
        if sent_cmp.get("change") is not None:
            parts.append(
                f"- Sentiment change: {sent_cmp['change']:+.4f} "
                f"({sent_cmp['yesterday_sentiment']} -> {sent_cmp['today_sentiment']})"
            )
        gh_cmp = comparison_data.get("github", {})
        new_repos = gh_cmp.get("new_repos", [])
        if new_repos:
            parts.append(f"- New trending repos: {', '.join(new_repos)}")

    return "\n".join(parts)


def generate_insights(aggregated_data: dict, comparison_data: dict | None = None) -> str:
    """Ask Claude to produce market insights from today's data."""
    if not ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set — returning placeholder insights")
        return "_Claude insights unavailable (no API key configured)._"

    user_content = _format_data_for_prompt(aggregated_data, comparison_data)

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1000,
            system=SYSTEM_PROMPT_INSIGHTS,
            messages=[{"role": "user", "content": user_content}],
        )
        text = message.content[0].text
        logger.info("Claude insights generated (%d chars)", len(text))
        return text
    except Exception as exc:
        logger.error("Claude API call failed (insights): %s", exc)
        return "_Claude insights unavailable due to an API error._"


def generate_summary(aggregated_data: dict, insights: str) -> str:
    """Ask Claude for a short executive summary."""
    if not ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set — returning placeholder summary")
        return "_Executive summary unavailable (no API key configured)._"

    user_content = (
        f"Here is today's data:\n\n"
        f"{_format_data_for_prompt(aggregated_data)}\n\n"
        f"And here are the detailed insights:\n\n{insights}"
    )

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=200,
            system=SYSTEM_PROMPT_SUMMARY,
            messages=[{"role": "user", "content": user_content}],
        )
        text = message.content[0].text
        logger.info("Claude summary generated (%d chars)", len(text))
        return text
    except Exception as exc:
        logger.error("Claude API call failed (summary): %s", exc)
        return "_Executive summary unavailable due to an API error._"
