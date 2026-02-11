# AI Market Intelligence

Automated daily AI market intelligence reports combining stock data, news sentiment, GitHub trends, and economic indicators with Claude AI analysis. Delivered via email and an interactive Streamlit dashboard.

## What It Does

Every day the pipeline runs an 8-step process:

1. **Fetches stock prices** for S&P 500, NASDAQ, NVDA, MSFT, and AMZN via Yahoo Finance
2. **Pulls AI/ML news** (up to 50 articles) from NewsAPI using keyword filters
3. **Scrapes trending GitHub repos** in Python, Go, Rust, and JavaScript filtered by AI/ML topics
4. **Gets economic indicators** (unemployment rate, CPI inflation) from the FRED API
5. **Runs sentiment analysis** on every headline using a DistilBERT model (cached in memory after first load)
6. **Sends all data to Claude** which generates market insights and an executive summary
7. **Builds a formatted Markdown report** with stock tables, sentiment breakdown, GitHub trends, day-over-day comparisons, and anomaly flags
8. **Stores everything in SQLite**, saves report files, and emails the report via Gmail

## Features

### Data Sources
- **Stock Tracking** — real-time and historical prices for S&P 500 (`^GSPC`), NASDAQ (`^IXIC`), NVDA, MSFT, AMZN
- **AI News Aggregation** — top headlines matching "AI", "artificial intelligence", "machine learning", "GPT", "LLM", "neural network"
- **GitHub Trends** — top 15 trending repos by stars (last 7 days) for keywords: machine-learning, ai, llm, vector-database, rag
- **Economic Indicators** — unemployment rate and CPI inflation from the Federal Reserve (FRED)

### Analysis
- **Sentiment Analysis** — DistilBERT (`distilbert-base-uncased-finetuned-sst-2-english`) classifies each headline as positive/negative/neutral with a confidence score
- **Claude AI Insights** — Claude Sonnet analyzes all data and produces market insights, executive summary, and anomaly flags
- **Day-over-Day Comparison** — automatically compares today's data to yesterday's across all metrics
- **Anomaly Detection** — flags stock moves >= 3% and extreme sentiment scores

### Delivery
- **Email Reports** — HTML-formatted daily digest via Gmail (OAuth2)
- **Streamlit Dashboard** — 4-tab interactive UI (see below)
- **SQLite Database** — all data persisted for historical querying
- **Markdown + JSON Files** — each day's report saved to `reports/`

### Dashboard Tabs
| Tab | Contents |
|-----|----------|
| **Today's Report** | Metric cards for all tickers + sentiment gauge, GitHub trending table, full rendered report, download button |
| **Today vs Yesterday** | Side-by-side stock comparison with directional arrows, sentiment delta, new/dropped GitHub repos |
| **30-Day Trends** | Interactive Plotly line charts for stock prices (toggle tickers), sentiment trend, S&P 500 vs sentiment correlation, language distribution bar chart |
| **Historical Archive** | Date picker, keyword search, clickable report list with summary previews, download past reports |
| **Settings (sidebar)** | Run Report Now, Test Email, Clear Database, schedule info, DB stats, last 10 log lines |

## Requirements

- **Python 3.10+** (uses `X | Y` union type syntax)
- **Windows** (quickstart script is PowerShell; the Python code itself is cross-platform)
- **API keys** (see below)

## Quickstart

The fastest way to get running on Windows:

```powershell
git clone https://github.com/Arul-Santoshi/ai-market-intelligence.git
cd ai-market-intelligence
.\start.ps1
```

The script handles everything automatically:
1. Finds Python 3.10+ on your system
2. Creates and activates a virtual environment (`.\venv`)
3. Installs all dependencies
4. Creates `.env` from the template and prompts you for missing API keys
5. Creates required directories (`reports/`, `logs/`)
6. Initializes the SQLite database
7. Launches the Streamlit dashboard

### Quickstart Modes

```powershell
.\start.ps1              # launch the Streamlit dashboard (default)
.\start.ps1 -Test        # run one full report immediately, then exit
.\start.ps1 -Scheduler   # start the daily 08:00 AM scheduler
```

## Manual Setup

If you prefer to set things up yourself or are on macOS/Linux:

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/Arul-Santoshi/ai-market-intelligence.git
cd ai-market-intelligence
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API keys

```bash
cp .env.example .env     # Windows: copy .env.example .env
```

Edit `.env` and fill in your keys:

| Variable | Required | Where to get it |
|----------|----------|-----------------|
| `ANTHROPIC_API_KEY` | Yes | [Anthropic Console](https://console.anthropic.com/) |
| `NEWSAPI_KEY` | Yes | [NewsAPI](https://newsapi.org/) (free tier: 100 requests/day) |
| `GMAIL_EMAIL` | No | Your Gmail address |
| `GMAIL_APP_PASSWORD` | No | [Gmail App Password](https://support.google.com/accounts/answer/185833) (requires 2FA enabled) |
| `FRED_API_KEY` | No | [FRED API](https://fred.stlouisfed.org/docs/api/api_key.html) (free) |

**What happens if a key is missing?** The pipeline gracefully skips that data source and continues. You can run without any optional keys — you'll just get fewer data points in the report.

### 4. Gmail setup (optional)

Email delivery uses Google OAuth2, not just an app password. For first-time setup:

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the Gmail API
3. Create OAuth 2.0 credentials (Desktop application)
4. Download the client secret JSON and save it as `credentials.json` in the project root
5. On first email send, a browser window will open for you to authorize access
6. After authorization, a `token.pickle` file is cached for future runs

### 5. Run

```bash
# Launch the dashboard
streamlit run app.py

# Or run one report immediately
python -m src.main --test

# Or start the daily scheduler
python -m src.main
```

## Scheduling: Do I Need My Machine Running at 8 AM?

**Yes.** The scheduler uses APScheduler running as a Python process on your local machine. Your computer must be:

- **Powered on** at the scheduled time (8:00 AM by default)
- **Not asleep/hibernating** — the process cannot wake your machine
- **Running the scheduler process** (`.\start.ps1 -Scheduler` or `python -m src.main`)

If your machine is off or asleep at 8:00 AM, that day's report is simply skipped. No data is lost — when the next report runs, it will still compare against the most recent previous report in the database.

### Alternatives if you can't keep a machine running

- **Run manually** — use `.\start.ps1 -Test` or the "Run Report Now" button in the dashboard whenever you want a report
- **Windows Task Scheduler** — create a scheduled task that runs `python -m src.main --test` at 8:00 AM. Windows Task Scheduler can wake your machine from sleep:
  ```
  Action: Start a program
  Program: powershell.exe
  Arguments: -ExecutionPolicy Bypass -File "C:\path\to\ai-market-intelligence\start.ps1" -Test
  Trigger: Daily at 08:00
  Conditions: Wake the computer to run this task
  ```
- **Cloud deployment** — deploy to a server, cloud VM, or services like Railway / Render that run on a schedule

### Changing the schedule time

Edit `SCHEDULED_TIME` in `config.py`:

```python
SCHEDULED_TIME = "08:00"  # change to any HH:MM in 24-hour format
```

## Architecture

```
┌──────────────────────────────────────────┐
│              Data Fetchers               │
│  stocks · news · GitHub · economic       │
└──────────────┬───────────────────────────┘
               │
┌──────────────▼───────────────────────────┐
│        Sentiment Analysis                │
│  DistilBERT on each headline             │
└──────────────┬───────────────────────────┘
               │
┌──────────────▼───────────────────────────┐
│        Data Processing                   │
│  aggregate + compare to yesterday        │
└──────────────┬───────────────────────────┘
               │
┌──────────────▼───────────────────────────┐
│        Claude AI Analysis                │
│  insights + executive summary            │
└──────────────┬───────────────────────────┘
               │
┌──────────────▼───────────────────────────┐
│        Report Generation                 │
│  Markdown with tables, charts, links     │
└──────────────┬───────────────────────────┘
               │
       ┌───────┴───────┐
       │               │
┌──────▼──────┐ ┌──────▼──────┐
│  Database   │ │    Email    │
│  (SQLite)   │ │   (Gmail)   │
└──────┬──────┘ └─────────────┘
       │
┌──────▼──────────────────────────────────┐
│        Streamlit Dashboard              │
│  today · compare · trends · archive     │
└─────────────────────────────────────────┘
```

## Project Structure

```
ai-market-intelligence/
├── start.ps1                  # Quickstart script (setup + launch)
├── app.py                     # Streamlit dashboard (4 tabs + sidebar)
├── config.py                  # Constants, env vars, tickers, keywords
├── requirements.txt
├── .env.example               # Template for API keys
├── src/
│   ├── __init__.py
│   ├── main.py                # Entry point: --test or scheduler mode
│   ├── data_fetchers.py       # Stock, news, GitHub, economic fetchers
│   ├── sentiment_analyzer.py  # DistilBERT sentiment with model caching
│   ├── data_processor.py      # Aggregation and day-over-day comparison
│   ├── claude_analyzer.py     # Claude API calls for insights + summary
│   ├── report_generator.py    # Markdown report builder + anomaly detection
│   ├── database_handler.py    # SQLite schema, upsert, historical queries
│   ├── email_sender.py        # Gmail OAuth2, Markdown-to-HTML email
│   └── scheduler.py           # APScheduler cron, pipeline orchestration
├── reports/                   # Daily .md and .json report files
├── logs/                      # Rotating scheduler logs (30-day retention)
└── market_data.db             # SQLite database (auto-created)
```

## Database Schema

Five tables, all with upsert (insert-or-update) support:

| Table | Key columns | Unique constraint |
|-------|-------------|-------------------|
| `daily_reports` | date, markdown_content, summary, overall_sentiment | date |
| `stock_prices` | date, ticker, price, change_percent | (date, ticker) |
| `sentiment_scores` | date, overall_sentiment, positive/negative/neutral counts | date |
| `github_trends` | date, repo_name, stars, language, url | (date, repo_name) |
| `economic_data` | date, unemployment_rate, inflation_rate | date |

## Error Handling

The pipeline is designed to never crash:

- Each of the 8 steps runs in its own try/except block
- If a data source fails (API down, rate limited, no key), that step is logged and skipped
- The report is still generated with whatever data was successfully fetched
- If email fails, the report is still saved to the database and files
- The scheduler logs every step's status to `logs/scheduler.log`

## License

MIT
