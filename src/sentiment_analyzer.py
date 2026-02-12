import logging

from config import TRUSTED_NEWS_SOURCES

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


def _source_weight(source_name: str) -> float:
    """Return a credibility multiplier for the article source.

    Trusted major outlets (Reuters, Bloomberg, etc.) get a 1.5x weight.
    All other sources get 1.0x (no penalty, just no bonus).
    """
    if source_name.lower() in TRUSTED_NEWS_SOURCES:
        return 1.5
    return 1.0


def analyze_ai_news_sentiment(articles: list[dict]) -> dict:
    """Run sentiment analysis on a list of news articles.

    Uses a weighted scoring system where each article's contribution to the
    overall score is scaled by:
      - **Model confidence:** Higher confidence predictions carry more weight.
      - **Source credibility:** Articles from trusted outlets (Reuters,
        Bloomberg, etc.) are weighted 1.5x.

    Args:
        articles: List of article dicts (must contain 'headline' key;
                  'source' key is used for credibility weighting).

    Returns:
        Dict with overall weighted sentiment score, category counts, and
        per-article sentiment results.
    """
    if not articles:
        return {
            "overall_sentiment": 0.5,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "articles_with_sentiment": [],
            "weighting_method": "confidence_source",
        }

    classifier = _load_model()
    if classifier is None:
        logger.warning("Sentiment model unavailable — returning neutral defaults")
        neutral_articles = [
            {
                "headline": a["headline"],
                "url": a.get("url", ""),
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
            "weighting_method": "confidence_source",
        }

    positive_count = 0
    negative_count = 0
    neutral_count = 0
    weighted_scores: list[float] = []
    total_weight = 0.0
    articles_with_sentiment = []

    for article in articles:
        headline = article.get("headline", "")
        if not headline:
            continue

        source = article.get("source", "Unknown")

        try:
            # Truncate to model max length
            result = classifier(headline[:512])[0]
            raw_confidence = result["score"]  # model's raw confidence (0-1)
            label, normalized_score = _normalize_score(result["label"], raw_confidence)

            if label == "positive":
                positive_count += 1
            elif label == "negative":
                negative_count += 1
            else:
                neutral_count += 1

            # Weighted contribution: confidence * source credibility
            confidence_weight = raw_confidence
            src_weight = _source_weight(source)
            weight = confidence_weight * src_weight

            weighted_scores.append(normalized_score * weight)
            total_weight += weight

            articles_with_sentiment.append({
                "headline": headline,
                "url": article.get("url", ""),
                "sentiment_label": label,
                "sentiment_score": round(normalized_score, 4),
            })

            logger.debug(
                "Sentiment: [%s] %.4f (weight=%.2f, src=%s, conf=%.2f)",
                label, normalized_score, weight, source, raw_confidence,
            )
        except Exception as exc:
            logger.error("Sentiment analysis failed for headline: %s", exc)
            articles_with_sentiment.append({
                "headline": headline,
                "url": article.get("url", ""),
                "sentiment_label": "neutral",
                "sentiment_score": 0.5,
            })
            neutral_count += 1
            # Fallback: neutral with default weight
            weighted_scores.append(0.5 * 1.0)
            total_weight += 1.0

    overall = round(sum(weighted_scores) / total_weight, 4) if total_weight > 0 else 0.5

    logger.info(
        "Sentiment analysis complete — pos: %d, neg: %d, neutral: %d, "
        "overall (weighted): %.4f",
        positive_count, negative_count, neutral_count, overall,
    )

    return {
        "overall_sentiment": overall,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "neutral_count": neutral_count,
        "articles_with_sentiment": articles_with_sentiment,
        "weighting_method": "confidence_source",
    }
