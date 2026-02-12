import os
from dotenv import load_dotenv

load_dotenv(override=True)

# --- API Keys ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
FRED_API_KEY = os.getenv("FRED_API_KEY", "")

# --- Claude Model ---
DEFAULT_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
AVAILABLE_MODELS = [
    "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5-20251001",
    "claude-opus-4-6",
]

# --- Stock Tickers ---
STOCK_TICKERS = ["^GSPC", "^IXIC", "NVDA", "MSFT", "AMZN"]

# --- News Keywords ---
AI_NEWS_KEYWORDS = [
    "AI",
    "artificial intelligence",
    "machine learning",
    "GPT",
    "LLM",
    "neural network",
]

# --- GitHub Trending Filters ---
GITHUB_LANGUAGES = ["Python", "Go", "Rust", "JavaScript"]
GITHUB_KEYWORDS = ["machine-learning", "ai", "llm", "vector-database", "rag"]
GITHUB_TOP_N = 15

# --- Paths ---
REPORT_FOLDER = "reports/"
LOGS_FOLDER = "logs/"
DATABASE_PATH = "market_data.db"

# --- Trusted News Sources (weighted higher in sentiment scoring) ---
TRUSTED_NEWS_SOURCES = {
    "reuters", "bloomberg", "associated press", "cnbc",
    "the wall street journal", "financial times", "the new york times",
    "bbc news", "techcrunch", "the verge", "ars technica", "wired",
    "mit technology review",
}

# --- Email Recipients ---
# Comma-separated list of email addresses.  GMAIL_EMAIL is always included
# as a fallback so existing single-recipient setups keep working.
_raw_recipients = os.getenv("EMAIL_RECIPIENTS", "")
EMAIL_RECIPIENTS: list[str] = [
    addr.strip()
    for addr in _raw_recipients.split(",")
    if addr.strip()
]
# Ensure the primary Gmail address is always in the list
if GMAIL_EMAIL and GMAIL_EMAIL not in EMAIL_RECIPIENTS:
    EMAIL_RECIPIENTS.insert(0, GMAIL_EMAIL)

# --- Feature Flags ---
# Toggle individual pipeline steps on/off.  Each key maps to a boolean
# that can be overridden via environment variables (e.g. FEATURE_STOCKS=0).
FEATURES: dict[str, bool] = {
    "stocks":    os.getenv("FEATURE_STOCKS", "1") == "1",
    "news":      os.getenv("FEATURE_NEWS", "1") == "1",
    "github":    os.getenv("FEATURE_GITHUB", "1") == "1",
    "economic":  os.getenv("FEATURE_ECONOMIC", "1") == "1",
    "sentiment": os.getenv("FEATURE_SENTIMENT", "1") == "1",
    "claude":    os.getenv("FEATURE_CLAUDE", "1") == "1",
    "email":     os.getenv("FEATURE_EMAIL", "1") == "1",
}

# --- Schedule ---
SCHEDULED_TIME = "08:00"
