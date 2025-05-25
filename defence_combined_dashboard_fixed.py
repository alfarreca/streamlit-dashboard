# -*- coding: utf-8 -*-
"""Defense‑Sector Dashboard – Professional Edition

Multi‑section Streamlit app:
    • **Overview**  – KPI tiles and high‑level summary
    • **Screener** – Technical + fundamental table
    • **Chart**    – Interactive weekly price chart

Sidebar uses a single `st.form` to avoid duplicate‑widget errors and to batch
updates (only reruns on **Load / Refresh**). All widgets carry explicit keys.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from io import StringIO

import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# ╭──────────────────────────────────────────────────────────────╮
# │ Helper utilities                                            │
# ╰──────────────────────────────────────────────────────────────╯

DEFAULT_TICKERS_TEXT = "ETR:RHM STO:SAAB-B EPA:HO LON:BA BIT:LDO"


def yf_symbol(code: str) -> str:
    """Convert `EXCHANGE:SYMBOL` → Yahoo Finance symbol."""
    if ":" not in code:
        return code
    exch, sym = code.split(":", 1)
    suffix = {
        "ETR": "DE",
        "STO": "ST",
        "EPA": "PA",
        "LON": "L",
        "BIT": "MI",
        "NYSE": "",
        "NASDAQ": "",
    }.get(exch.upper(), "")
    return f"{sym}{('.' + suffix) if suffix else ''}"


def parse_tickers(text: str) -> tuple[str, ...]:
    """Split on comma / whitespace, return tuple of non‑empty strings."""
    return tuple(tok.strip() for tok in re.split(r"[ ,]+", text) if tok.strip())


def safe_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return np.nan

# ╭──────────────────────────────────────────────────────────────╮
# │ Cached data fetchers                                        │
# ╰──────────────────────────────────────────────────────────────╯

@st.cache_data(show_spinner=False)
def fetch_weekly_ohlcv(ticker: str) -> pd.DataFrame:
    """1‑year daily → weekly‑Friday Close & Volume; Stooq fallback."""
    ysym = yf_symbol(ticker)
    daily = yf.Ticker(ysym).history(period="1y", interval="1d")[["Close", "Volume"]]

    if daily.empty:
        code = ysym.split(".")[0].lower()
        try:
            txt = requests.get(f"https://stooq.com/q/d/l/?s={code}&i=d", timeout=5).text
            if "Date" in txt:
                daily = pd.read_csv(StringIO(txt), parse_dates=["Date"], index_col="Date")[["Close"]]
                daily["Volume"] = np.nan
        except requests.RequestException:
            return pd.DataFrame()

    weekly = pd.DataFrame({
        "Close": daily["Close"].resample("W-FRI").last(),
        "Volume": daily["Volume"].resample("W-FRI").sum(min_count=1),
    }).dropna(subset=["Close"])
    return weekly


@st.cache_data(show_spinner=False)
def fetch_fundamentals(tickers: tuple[str, ...]) -> pd.DataFrame:
    rows = []
    for t in tickers:
        try:
            info = yf.Ticker(yf_symbol(t)).info or {}
        except Exception:
            info = {}

        dy_raw = safe_float(info.get("dividendYield"))
        dy = dy_raw * 100 if (not np.isnan(dy_raw) and dy_raw < 1) else dy_raw

        pr_raw = safe_float(info.get("payoutRatio"))
        pr = pr_raw * 100 if not np.isnan(pr_raw) else np.nan

        fcf_raw = safe_float(info.get("freeCashflow"))
        fcf_m = fcf_raw / 1e6 if not np.isnan(fcf_raw) else np.nan

        rows.append({
            "Ticker": t,
            "Dividend Yield (%)": dy,
            "Dividend Payout Ratio (%)": pr,
            "Free Cash Flow (LC m)": fcf_m,
        })

    return pd.DataFrame(rows).set_index("Ticker").reindex(tickers)

# ╭──────────────────────────────────────────────────────────────╮
# │ Technical metrics                                           │
# ╰──────────────────────────────────────────────────────────────╯

def technicals(df: pd.DataFrame) -> dict[str, float | str]:
    if df.empty or len(df) < 20:
        return {}

    last = df.iloc[-1]
    prev = df.iloc[-2]

    ma10 = df["Close"].rolling(10).mean()
    ma20 = df["Close"].rolling(20).mean()

    return {
        "Price": last.Close,
        "MA10": ma10.iloc[-1],
        "MA20": ma20.iloc[-1],
        "% vs MA10": (last.Close - ma10.iloc[-1]) / ma10.iloc[-1] * 100,
        "Volume": last.Volume,
        "Vol MA10": df["Volume"].rolling(10).mean().iloc[-1],
        "Signal": "Buy" if ma10.iloc[-1] > ma20.iloc[-1] else "Sell",
        "Last Updated": last.name.strftime("%Y-%m-%d"),
        "Crossover": "Above" if last.Close > ma20.iloc[-1] else "Below",
        "Divergence": (
            "Overbought" if last.Close >= ma10.iloc[-1] * 1.1 else (
                "Oversold" if last.Close <= ma10.iloc[-1] * 0.9 else "OK")
        ),
        "Prev Price": prev.Close,
        "Prev MA10": ma10.iloc[-2],
    }

# ╭──────────────────────────────────────────────────────────────╮
# │ Page renderers                                              │
# ╰──────────────────────────────────────────────────────────────╯

def page_overview(tickers: tuple[str, ...]):
    """KPI tiles summarising the universe."""
    tech_df = pd.DataFrame({t: technicals(fetch_weekly_ohlcv(t)) for t in tickers}).T
    fund_df = fetch_fundamentals(tickers)

    avg_dy = fund_df["Dividend Yield (%)"].mean()
    buy_ratio = (tech_df["Signal"] == "Buy").mean() * 100

    col1, col2, col3 = st.columns(3)
    col1.metric("Average Dividend Yield", f"{avg_dy:.2f}%")
    col2.metric("% Buy Signals", f"{buy_ratio:.0f}%")
    col3.metric("Tickers Tracked", len(tickers))

    st.markdown("### Latest Signals")
    st.dataframe(tech_df[["Signal", "Last Updated"]])


def page_screener(tickers: tuple[str, ...]):
    tech_df = pd.DataFrame({t: technicals(fetch_weekly_ohlcv(t)) for t in tickers}).T
    fund_df = fetch_fundamentals(tickers)
    df = pd.concat([tech_df, fund_df], axis=1).round(2)

    st.markdown("### Technical & Fundamental Screener")
    st.dataframe(
        df.style.apply(
            lambda s: ["background:#FFEB3B" if x == s.max() else "" for x in s],
            subset=["Dividend Yield (%)", "Dividend Payout Ratio (%)"],
        ),
        use_container_width=True,
    )


def page_chart(tickers: tuple[str, ...]):
    sel = st.selectbox("Select ticker", tickers, key="chart_select")
    df = fetch_weekly_ohlcv(sel)
    if df.empty:
        st.warning("No price data available.")
        return
    df_plot = df.copy()
    df_plot["MA10"] = df_plot["Close"].rolling(10).mean()
    df_plot["MA20"] = df_plot["Close"].rolling(20).mean()
    st.line_chart(df_plot[["Close", "MA10", "MA20"]])

# ╭──────────────────────────────────────────────────────────────╮
# │ Main entry                                                  │
# ╰──────────────────────────────────────────────────────────────╯

def main():
    st.set_page_config(page_title="Defense Dashboard", layout="wide")

    # —— header bar ——
    with st.container():
        cols = st.columns([1, 6, 2])
        cols[0].markdown("## 🛡️")
        cols[1].markdown("## Defense Sector Dashboard")
        cols[2].markdown(f"Last refresh: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    st.markdown("---")

    # —— sidebar form ——
    with st.sidebar.form(key="sidebar_form"):
        user_text = st.text_area("Enter tickers", value=st.session_state.get("tick_text", DEFAULT_TICKERS_TEXT), key="tickers_input", height=70)
        page_choice = st.radio("Navigate", ("Overview", "Screener", "Chart"), key="nav_choice")
        submitted = st.form_submit_button("Load / Refresh", use_container_width=True)

    if submitted or "tickers" not in st.session_state:
        st.session_state["tickers"] = parse_tickers(user_text)
        st.session_state["tick_text"] = user_text

    tickers = st.session_state["tickers"]

    # —— page routing ——
    if page_choice == "Overview":
        page_overview(tickers)
    elif page_choice == "Screener":
        page_screener(tickers)
    else:
        page_chart(tickers)


if __name__ == "__main__":
    main()
