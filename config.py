import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
FRED_API_KEY = os.getenv("FRED_API_KEY", "")

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

# --- Schedule ---
SCHEDULED_TIME = "08:00"
