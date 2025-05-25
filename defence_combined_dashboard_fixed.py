# -*- coding: utf-8 -*-
"""Streamlit Defense‑Sector Dashboard

Paste a list of tickers (e.g. "ETR:RHM LON:BA") in the sidebar and click
**Load Tickers** to refresh the table and chart.

Compatible with Streamlit 1.x and Python 3.8+.
"""

import re
from io import StringIO

import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# ────────────────────────────────
# Helper functions
# ────────────────────────────────

def yf_symbol(code: str) -> str:
    """Convert an `EXCHANGE:SYMBOL` string into a Yahoo Finance ticker."""
    if ":" not in code:
        return code  # already Yahoo‑formatted

    exch, sym = code.split(":", 1)
    suffix = {
        "ETR": "DE",     # Frankfurt (Xetra)
        "STO": "ST",     # Stockholm
        "EPA": "PA",     # Paris
        "LON": "L",      # London
        "BIT": "MI",     # Milan
        "NYSE": "",      # NYSE — no suffix
        "NASDAQ": "",    # Nasdaq — no suffix
    }.get(exch.upper(), "")

    return f"{sym}{('.' + suffix) if suffix else ''}"


def split_tickers(text: str) -> tuple[str, ...]:
    """Split on comma or whitespace and drop empties."""
    return tuple(tok.strip() for tok in re.split(r"[ ,]+", text.strip()) if tok.strip())


def safe_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return np.nan

# ────────────────────────────────
# Data fetchers (cached)
# ────────────────────────────────

@st.cache_data(show_spinner=False)
def fetch_weekly_ohlcv(ticker: str) -> pd.DataFrame:
    """Return a 1‑year weekly Friday OHLCV DataFrame (Close + Volume)."""
    ysym = yf_symbol(ticker)
    daily = yf.Ticker(ysym).history(period="1y", interval="1d")[["Close", "Volume"]]

    if daily.empty:
        sym = ysym.split(".")[0].lower()
        try:
            csv = requests.get(f"https://stooq.com/q/d/l/?s={sym}&i=d", timeout=5).text
            if "Date" in csv:
                daily = pd.read_csv(StringIO(csv), parse_dates=["Date"], index_col="Date")[["Close"]]
                daily["Volume"] = np.nan
        except requests.RequestException:
            return pd.DataFrame()

    weekly = pd.DataFrame(
        {
            "Close": daily["Close"].resample("W-FRI").last(),
            "Volume": daily["Volume"].resample("W-FRI").sum(min_count=1),
        }
    ).dropna(subset=["Close"])
    return weekly


@st.cache_data(show_spinner=False)
def fetch_fundamentals(tickers: tuple[str, ...]) -> pd.DataFrame:
    """Pull dividend yield, payout ratio, and FCF (in millions)."""
    records = []
    for t in tickers:
        try:
            info = yf.Ticker(yf_symbol(t)).info or {}
        except Exception:
            info = {}

        dy_raw = safe_float(info.get("dividendYield"))
        dy_pct = dy_raw * 100 if (not np.isnan(dy_raw) and dy_raw < 1) else dy_raw

        pr_raw = safe_float(info.get("payoutRatio"))
        pr_pct = pr_raw * 100 if not np.isnan(pr_raw) else np.nan

        fcf_raw = safe_float(info.get("freeCashflow"))
        fcf_m = fcf_raw / 1e6 if not np.isnan(fcf_raw) else np.nan

        records.append({
            "Ticker": t,
            "Dividend Yield (%)": dy_pct,
            "Dividend Payout Ratio (%)": pr_pct,
            "Free Cash Flow (LC m)": fcf_m,
        })

    df = pd.DataFrame(records).set_index("Ticker")
    return df.reindex(tickers)

# ────────────────────────────────
# Technical metrics
# ────────────────────────────────

def technicals(df: pd.DataFrame) -> dict:
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

# ────────────────────────────────
# Streamlit UI
# ────────────────────────────────

def main():
    st.set_page_config(page_title="Defense Dashboard", layout="wide")
    st.title("🛡️ Defense Sector: Weekly Signal Dashboard")

    default_text = "ETR:RHM STO:SAAB-B EPA:HO LON:BA BIT:LDO"

    # Sidebar controls
    with st.sidebar:
        st.header("Tickers")
        user_text = st.text_input("Enter tickers", default_text)
        if st.button("Load Tickers"):
            st.session_state["tickers"] = split_tickers(user_text)

    tickers = st.session_state.get("tickers", split_tickers(default_text))

    show_tbl = st.checkbox("Show All Tickers Table", True)

    # Data pulls
    fund_df = fetch_fundamentals(tickers)
    tech_df = pd.DataFrame({t: technicals(fetch_weekly_ohlcv(t)) for t in tickers}).T
    combined = pd.concat([tech_df, fund_df], axis=1).round(2)

    if show_tbl:
        st.subheader("📊 All Tickers – Technical & Fundamental Metrics")
        st.dataframe(
            combined.style.apply(
                lambda s: ["background:#FFEB3B" if x == s.max() else "" for x in s],
                subset=["Dividend Yield (%)", "Dividend Payout Ratio (%)"],
            ),
            use_container_width=True,
        )

    sel = st.selectbox("Select Ticker to View Chart", tickers)
    wk = fetch_weekly_ohlcv(sel)
    if wk.empty:
        st.warning("No price data available for that ticker.")
    else:
        plot = wk.copy()
        plot["MA10"] = plot["Close"].rolling(10).mean()
        plot["MA20"] = plot["Close"].rolling(20).mean()
        st.subheader(f"📈 Weekly Price Chart: {sel}")
        st.line_chart(plot[["Close", "MA10", "MA20"]])


if __name__ == "__main__":
    main()

# ---- sidebar navigation ----
with st.sidebar:
    page = st.radio("Navigate", ("Overview", "Screener", "Chart"))
    st.markdown("---")
    tick_text = st.text_area("Tickers", "ETR:RHM ...")
    if st.button("Load Tickers"):
        st.session_state.tickers = split_tickers(tick_text)

# ---- main switchboard ----
if page == "Overview":
    show_overview()
elif page == "Screener":
    show_screener_table()
else:  # Chart
    show_chart_view()
