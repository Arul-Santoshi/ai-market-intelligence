import logging

logger = logging.getLogger(__name__)

# Module-level cache so the model is loaded once per process
_classifier = None


def _load_model():
    """Load the DistilBERT sentiment pipeline (cached after first call)."""
    global _classifier
    if _classifier is not None:
        return _classifier

    try:
        from transformers import pipeline

        logger.info("Loading DistilBERT sentiment model...")
        _classifier = pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english",
        )
        logger.info("Sentiment model loaded successfully")
        return _classifier
    except Exception as exc:
        logger.error("Failed to load sentiment model: %s", exc)
        return None


def _normalize_score(label: str, score: float) -> tuple[str, float]:
    """Map HuggingFace POSITIVE/NEGATIVE labels to positive/negative/neutral."""
    if label == "POSITIVE":
        if score >= 0.7:
            return "positive", score
        return "neutral", score
    else:  # NEGATIVE
        if score >= 0.7:
            return "negative", 1.0 - score
        return "neutral", 1.0 - score


def analyze_ai_news_sentiment(articles: list[dict]) -> dict:
    """Run sentiment analysis on a list of news articles.

    Args:
        articles: List of article dicts (must contain 'headline' key).

    Returns:
        Dict with overall sentiment score, category counts, and per-article
        sentiment results.
    """
    if not articles:
        return {
            "overall_sentiment": 0.5,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "articles_with_sentiment": [],
        }

    classifier = _load_model()
    if classifier is None:
        logger.warning("Sentiment model unavailable — returning neutral defaults")
        neutral_articles = [
            {
                "headline": a["headline"],
                "sentiment_label": "neutral",
                "sentiment_score": 0.5,
            }
            for a in articles
        ]
        return {
            "overall_sentiment": 0.5,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": len(articles),
            "articles_with_sentiment": neutral_articles,
        }

    positive_count = 0
    negative_count = 0
    neutral_count = 0
    scores = []
    articles_with_sentiment = []

    for article in articles:
        headline = article.get("headline", "")
        if not headline:
            continue

        try:
            # Truncate to model max length
            result = classifier(headline[:512])[0]
            label, score = _normalize_score(result["label"], result["score"])

            if label == "positive":
                positive_count += 1
            elif label == "negative":
                negative_count += 1
            else:
                neutral_count += 1

            scores.append(score)
            articles_with_sentiment.append({
                "headline": headline,
                "sentiment_label": label,
                "sentiment_score": round(score, 4),
            })
        except Exception as exc:
            logger.error("Sentiment analysis failed for headline: %s", exc)
            articles_with_sentiment.append({
                "headline": headline,
                "sentiment_label": "neutral",
                "sentiment_score": 0.5,
            })
            neutral_count += 1
            scores.append(0.5)

    overall = round(sum(scores) / len(scores), 4) if scores else 0.5

    logger.info(
        "Sentiment analysis complete — pos: %d, neg: %d, neutral: %d, overall: %.4f",
        positive_count, negative_count, neutral_count, overall,
    )

    return {
        "overall_sentiment": overall,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "neutral_count": neutral_count,
        "articles_with_sentiment": articles_with_sentiment,
    }
