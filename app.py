"""AI Market Intelligence — Streamlit Dashboard."""

import os
import sqlite3
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import AVAILABLE_MODELS, DATABASE_PATH, DEFAULT_MODEL, GMAIL_EMAIL, LOGS_FOLDER, SCHEDULED_TIME

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Market Intelligence Dashboard",
    page_icon="\U0001F4CA",
    layout="wide",
)

TICKER_NAMES = {
    "^GSPC": "S&P 500",
    "^IXIC": "NASDAQ",
    "NVDA": "NVDA",
    "MSFT": "MSFT",
    "AMZN": "AMZN",
}


# ---------------------------------------------------------------------------
# Database helpers (lightweight, no heavy imports)
# ---------------------------------------------------------------------------

def _db_connect():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _db_available() -> bool:
    return os.path.exists(DATABASE_PATH)


@st.cache_data(ttl=300)
def _get_today_report():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = _db_connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM daily_reports WHERE date = ?", (today,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


@st.cache_data(ttl=300)
def _get_report_by_date(date_str: str):
    conn = _db_connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM daily_reports WHERE date = ?", (date_str,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


@st.cache_data(ttl=300)
def _get_stocks_for_date(date_str: str):
    conn = _db_connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM stock_prices WHERE date = ?", (date_str,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@st.cache_data(ttl=300)
def _get_sentiment_for_date(date_str: str):
    conn = _db_connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sentiment_scores WHERE date = ?", (date_str,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


@st.cache_data(ttl=300)
def _get_github_for_date(date_str: str):
    conn = _db_connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM github_trends WHERE date = ?", (date_str,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@st.cache_data(ttl=300)
def _get_historical_stocks(days: int = 30):
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _db_connect()
    df = pd.read_sql_query(
        "SELECT date, ticker, price, change_percent FROM stock_prices WHERE date >= ? ORDER BY date",
        conn, params=(since,),
    )
    conn.close()
    return df


@st.cache_data(ttl=300)
def _get_historical_sentiment(days: int = 30):
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _db_connect()
    df = pd.read_sql_query(
        "SELECT date, overall_sentiment, positive_count, negative_count, neutral_count "
        "FROM sentiment_scores WHERE date >= ? ORDER BY date",
        conn, params=(since,),
    )
    conn.close()
    return df


@st.cache_data(ttl=300)
def _get_historical_github(days: int = 30):
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = _db_connect()
    df = pd.read_sql_query(
        "SELECT date, repo_name, stars, language, url FROM github_trends WHERE date >= ? ORDER BY date",
        conn, params=(since,),
    )
    conn.close()
    return df


@st.cache_data(ttl=300)
def _get_all_report_dates():
    conn = _db_connect()
    cur = conn.cursor()
    cur.execute("SELECT date, summary FROM daily_reports ORDER BY date DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@st.cache_data(ttl=300)
def _get_db_info():
    conn = _db_connect()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as cnt, MIN(date) as oldest, MAX(date) as newest FROM daily_reports")
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else {}


# ---------------------------------------------------------------------------
# Sidebar — Settings (Tab 5)
# ---------------------------------------------------------------------------

def _render_sidebar():
    st.sidebar.title("Settings")

    # Claude model selector
    st.sidebar.subheader("Claude Model")
    selected_model = st.sidebar.selectbox(
        "Model for analysis",
        options=AVAILABLE_MODELS,
        index=AVAILABLE_MODELS.index(DEFAULT_MODEL) if DEFAULT_MODEL in AVAILABLE_MODELS else 0,
    )

    # Next scheduled run
    st.sidebar.subheader("Schedule")
    st.sidebar.write(f"**Next run:** Daily at {SCHEDULED_TIME}")
    st.sidebar.write(f"**Email recipient:** {GMAIL_EMAIL or 'Not configured'}")

    # Run report now
    if st.sidebar.button("Run Report Now"):
        with st.sidebar.status("Running daily report...", expanded=True):
            try:
                from src.scheduler import run_daily_report
                status = run_daily_report(model=selected_model)
                failed = [k for k, v in status.items() if v != "success"]
                if failed:
                    st.sidebar.warning(f"Completed with issues: {', '.join(failed)}")
                else:
                    st.sidebar.success("Report generated successfully!")
                st.cache_data.clear()
            except Exception as exc:
                st.sidebar.error(f"Error: {exc}")

    # Test email
    if st.sidebar.button("Test Email"):
        with st.sidebar.spinner("Sending test email..."):
            try:
                from src.email_sender import test_email_connection
                ok = test_email_connection()
                if ok:
                    st.sidebar.success("Test email sent!")
                else:
                    st.sidebar.error("Email test failed. Check credentials.")
            except Exception as exc:
                st.sidebar.error(f"Error: {exc}")

    # Clear database
    st.sidebar.divider()
    if st.sidebar.button("Clear Database", type="secondary"):
        st.sidebar.warning("This will delete ALL stored data.")
        # Use a second confirmation via checkbox
    if st.sidebar.checkbox("Confirm: delete all data", value=False, key="confirm_clear"):
        if st.sidebar.button("Yes, clear everything", type="primary", key="clear_confirm_btn"):
            try:
                conn = _db_connect()
                for table in ["daily_reports", "stock_prices", "sentiment_scores", "github_trends", "economic_data"]:
                    conn.execute(f"DELETE FROM {table}")
                conn.commit()
                conn.close()
                st.cache_data.clear()
                st.sidebar.success("Database cleared.")
            except Exception as exc:
                st.sidebar.error(f"Error: {exc}")

    # Database info
    st.sidebar.divider()
    st.sidebar.subheader("Database Info")
    if _db_available():
        info = _get_db_info()
        st.sidebar.write(f"**Reports:** {info.get('cnt', 0)}")
        st.sidebar.write(f"**Oldest:** {info.get('oldest', '—')}")
        st.sidebar.write(f"**Newest:** {info.get('newest', '—')}")
    else:
        st.sidebar.info("No database found yet.")

    # Recent logs
    st.sidebar.divider()
    st.sidebar.subheader("Recent Logs")
    log_path = os.path.join(LOGS_FOLDER, "scheduler.log")
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            last_lines = lines[-10:] if len(lines) >= 10 else lines
            st.sidebar.code("".join(last_lines), language="log")
        except Exception:
            st.sidebar.info("Could not read log file.")
    else:
        st.sidebar.info("No logs yet.")


# ---------------------------------------------------------------------------
# Tab 1 — Today's Report
# ---------------------------------------------------------------------------

def _render_tab_today():
    if not _db_available():
        st.info("No data yet. Run the pipeline first: `python -m src.main --test`")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    report = _get_today_report()
    stocks = _get_stocks_for_date(today)
    sentiment = _get_sentiment_for_date(today)
    github_repos = _get_github_for_date(today)

    if not report:
        st.info("No report for today yet. Click **Run Report Now** in the sidebar or wait for the scheduled run.")
        return

    # Key metrics row
    st.subheader("Key Metrics")
    cols = st.columns(len(stocks) + 1)  # +1 for sentiment
    for i, s in enumerate(stocks):
        name = TICKER_NAMES.get(s["ticker"], s["ticker"])
        change = s["change_percent"] or 0
        delta_color = "normal"  # green for positive, red for negative
        cols[i].metric(
            label=name,
            value=f"${s['price']:,.2f}" if s["price"] else "—",
            delta=f"{change:+.2f}%",
        )
    # Sentiment metric
    if sentiment:
        score = sentiment["overall_sentiment"] or 0.5
        cols[-1].metric(
            label="AI Sentiment",
            value=f"{score:.0%}",
            delta=f"+{sentiment['positive_count']}/-{sentiment['negative_count']}",
            delta_color="off",
        )

    st.divider()

    # Sentiment gauge
    if sentiment and sentiment["overall_sentiment"] is not None:
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=sentiment["overall_sentiment"] * 100,
            title={"text": "AI News Sentiment"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#1f77b4"},
                "steps": [
                    {"range": [0, 35], "color": "#ffcccc"},
                    {"range": [35, 65], "color": "#ffffcc"},
                    {"range": [65, 100], "color": "#ccffcc"},
                ],
            },
        ))
        fig_gauge.update_layout(height=250, margin=dict(t=40, b=0, l=40, r=40))
        st.plotly_chart(fig_gauge, use_container_width=True)

    # Full report (includes GitHub Trending, Insights, etc.)
    st.subheader("Full Report")
    st.markdown(report["markdown_content"])

    # Download button
    col_dl, _ = st.columns([1, 3])
    col_dl.download_button(
        label="Download Report (.md)",
        data=report["markdown_content"],
        file_name=f"ai_market_report_{today}.md",
        mime="text/markdown",
        key="download_today",
    )


# ---------------------------------------------------------------------------
# Tab 2 — Compare Today vs Yesterday
# ---------------------------------------------------------------------------

def _render_tab_compare():
    if not _db_available():
        st.info("No data yet.")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    stocks_today = {s["ticker"]: s for s in _get_stocks_for_date(today)}
    stocks_yesterday = {s["ticker"]: s for s in _get_stocks_for_date(yesterday)}
    sent_today = _get_sentiment_for_date(today)
    sent_yesterday = _get_sentiment_for_date(yesterday)
    gh_today = {r["repo_name"] for r in _get_github_for_date(today)}
    gh_yesterday = {r["repo_name"] for r in _get_github_for_date(yesterday)}

    if not stocks_today:
        st.info("No data for today yet.")
        return

    # Stock comparison table
    st.subheader("Stock Prices")
    rows = []
    all_tickers = list(dict.fromkeys(list(stocks_today.keys()) + list(stocks_yesterday.keys())))
    for ticker in all_tickers:
        name = TICKER_NAMES.get(ticker, ticker)
        t = stocks_today.get(ticker)
        y = stocks_yesterday.get(ticker)
        today_price = t["price"] if t else None
        yesterday_price = y["price"] if y else None
        if today_price is not None and yesterday_price is not None:
            change = today_price - yesterday_price
            change_pct = (change / yesterday_price) * 100 if yesterday_price else 0
            direction = "\u2191" if change >= 0 else "\u2193"
        else:
            change = None
            change_pct = None
            direction = "—"
        rows.append({
            "Ticker": name,
            "Today": f"${today_price:,.2f}" if today_price is not None else "—",
            "Yesterday": f"${yesterday_price:,.2f}" if yesterday_price is not None else "—",
            "Change": f"{change_pct:+.2f}%" if change_pct is not None else "—",
            "Direction": direction,
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Sentiment comparison
    st.subheader("Sentiment")
    sent_cols = st.columns(3)
    t_sent = sent_today["overall_sentiment"] if sent_today and sent_today["overall_sentiment"] else None
    y_sent = sent_yesterday["overall_sentiment"] if sent_yesterday and sent_yesterday["overall_sentiment"] else None
    sent_cols[0].metric("Today", f"{t_sent:.0%}" if t_sent is not None else "—")
    sent_cols[1].metric("Yesterday", f"{y_sent:.0%}" if y_sent is not None else "—")
    if t_sent is not None and y_sent is not None:
        diff = t_sent - y_sent
        label = "improved" if diff > 0 else "declined"
        sent_cols[2].metric("Change", f"{diff:+.1%}", delta=label)
    else:
        sent_cols[2].metric("Change", "—")

    # GitHub comparison
    st.subheader("GitHub Trending")
    new_repos = sorted(gh_today - gh_yesterday)
    dropped_repos = sorted(gh_yesterday - gh_today)
    col_new, col_drop = st.columns(2)
    with col_new:
        st.write("**New today**")
        if new_repos:
            for r in new_repos:
                st.write(f"- {r}")
        else:
            st.write("_None_")
    with col_drop:
        st.write("**Dropped from yesterday**")
        if dropped_repos:
            for r in dropped_repos:
                st.write(f"- {r}")
        else:
            st.write("_None_")


# ---------------------------------------------------------------------------
# Tab 3 — 30-Day Trends
# ---------------------------------------------------------------------------

def _render_tab_trends():
    if not _db_available():
        st.info("No data yet.")
        return

    stock_df = _get_historical_stocks(30)
    sent_df = _get_historical_sentiment(30)
    gh_df = _get_historical_github(30)

    if stock_df.empty:
        st.info("Not enough historical data yet. Run the pipeline for a few days to see trends.")
        return

    # --- Stock price chart ---
    st.subheader("Stock Prices (30 Days)")
    stock_df["name"] = stock_df["ticker"].map(TICKER_NAMES).fillna(stock_df["ticker"])
    all_names = sorted(stock_df["name"].unique())
    selected = st.multiselect("Select tickers", all_names, default=all_names)
    filtered = stock_df[stock_df["name"].isin(selected)]

    if not filtered.empty:
        fig_stocks = px.line(
            filtered, x="date", y="price", color="name",
            labels={"price": "Price ($)", "date": "Date", "name": "Ticker"},
        )
        fig_stocks.update_layout(height=400, hovermode="x unified")
        st.plotly_chart(fig_stocks, use_container_width=True)

    # --- Sentiment trend ---
    if not sent_df.empty:
        st.subheader("AI News Sentiment (30 Days)")
        fig_sent = px.line(
            sent_df, x="date", y="overall_sentiment",
            labels={"overall_sentiment": "Sentiment Score", "date": "Date"},
        )
        fig_sent.update_traces(line_color="#1f77b4")
        fig_sent.update_layout(height=350, hovermode="x unified")
        st.plotly_chart(fig_sent, use_container_width=True)

        # Correlation with S&P 500
        sp500 = stock_df[stock_df["ticker"] == "^GSPC"][["date", "change_percent"]].copy()
        if not sp500.empty and not sent_df.empty:
            merged = pd.merge(sp500, sent_df[["date", "overall_sentiment"]], on="date", how="inner")
            if len(merged) >= 3:
                corr = merged["change_percent"].corr(merged["overall_sentiment"])
                st.metric("Sentiment vs S&P 500 Correlation", f"{corr:.2f}")
                if abs(corr) >= 0.5:
                    st.caption("Notable correlation between AI news sentiment and S&P 500 movement.")

    # --- GitHub language breakdown ---
    if not gh_df.empty:
        st.subheader("Trending Repo Languages (30 Days)")
        lang_counts = gh_df["language"].value_counts().reset_index()
        lang_counts.columns = ["Language", "Count"]
        fig_lang = px.bar(
            lang_counts, x="Language", y="Count", color="Language",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_lang.update_layout(height=350, showlegend=False)
        st.plotly_chart(fig_lang, use_container_width=True)


# ---------------------------------------------------------------------------
# Tab 4 — Historical Reports Archive
# ---------------------------------------------------------------------------

def _render_tab_archive():
    if not _db_available():
        st.info("No data yet.")
        return

    all_reports = _get_all_report_dates()
    if not all_reports:
        st.info("No archived reports found.")
        return

    # Date picker
    available_dates = [r["date"] for r in all_reports]
    col_pick, col_search = st.columns([1, 2])
    with col_pick:
        selected_date = st.date_input(
            "Select a date",
            value=datetime.strptime(available_dates[0], "%Y-%m-%d"),
            min_value=datetime.strptime(available_dates[-1], "%Y-%m-%d"),
            max_value=datetime.strptime(available_dates[0], "%Y-%m-%d"),
        )
    with col_search:
        search_term = st.text_input("Search reports by keyword", "")

    # Report list
    st.subheader("Available Reports")
    for r in all_reports:
        summary_preview = (r["summary"] or "")[:120]
        if search_term:
            combined = f"{r['date']} {r.get('summary', '')}".lower()
            if search_term.lower() not in combined:
                continue
        if st.button(f"{r['date']}  —  {summary_preview}...", key=f"report_{r['date']}"):
            selected_date = datetime.strptime(r["date"], "%Y-%m-%d")

    # Display selected report
    st.divider()
    date_str = selected_date.strftime("%Y-%m-%d") if hasattr(selected_date, "strftime") else str(selected_date)
    report = _get_report_by_date(date_str)
    if report:
        st.subheader(f"Report for {date_str}")
        st.markdown(report["markdown_content"])
        st.download_button(
            label="Download Report (.md)",
            data=report["markdown_content"],
            file_name=f"ai_market_report_{date_str}.md",
            mime="text/markdown",
            key=f"download_archive_{date_str}",
        )
    else:
        st.info(f"No report found for {date_str}.")


# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------

def main():
    st.title("AI Market Intelligence Dashboard")

    _render_sidebar()

    tab1, tab2, tab3, tab4 = st.tabs([
        "Today's Report",
        "Today vs Yesterday",
        "30-Day Trends",
        "Historical Archive",
    ])

    with tab1:
        _render_tab_today()
    with tab2:
        _render_tab_compare()
    with tab3:
        _render_tab_trends()
    with tab4:
        _render_tab_archive()


main()

print("Phase 4 complete! Dashboard is ready. Run 'streamlit run app.py' to view.")
