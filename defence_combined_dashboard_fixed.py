# -*- coding: utf-8 -*-
"""Defense-Sector Dashboard – Professional Edition (implicit ticker mode)

Users can now enter **just the ticker symbol** (e.g. `RHM`, `SAAB-B`, `HO`),
and the app maps it to the correct Yahoo Finance code.  Exchange prefixes are
still accepted (`ETR:RHM` etc.).
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

# ══════════ Constants ══════════
DEFAULT_TICKERS_TEXT = "RHM SAAB-B HO BA LDO"
IMPLICIT_SUFFIX = {
    "RHM": "DE",      # Rheinmetall – Frankfurt/Xetra
    "SAAB-B": "ST",   # Saab AB B – Stockholm
    "HO": "PA",       # Thales – Paris
    "BA": "L",        # BAE Systems – London
    "LDO": "MI",       # Leonardo – Milan
}
EXCHANGE_SUFFIX = {
    "ETR": "DE", "STO": "ST", "EPA": "PA", "LON": "L", "BIT": "MI", "NYSE": "", "NASDAQ": "",
}

# ══════════ Helpers ══════════

def yf_symbol(code: str) -> str:
    """Turn user input into a Yahoo Finance symbol."""
    code = code.strip()
    if ":" in code:  # explicit exchange
        exch, sym = code.split(":", 1)
        suf = EXCHANGE_SUFFIX.get(exch.upper(), "")
        return f"{sym}{('.' + suf) if suf else ''}"
    # implicit mapping
    suf = IMPLICIT_SUFFIX.get(code.upper())
    return f"{code}{('.' + suf) if suf else ''}" if suf is not None else code

def parse_tickers(text: str) -> tuple[str, ...]:
    return tuple(tok for tok in re.split(r"[ ,]+", text) if tok)

def safe_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return np.nan

# ══════════ Data fetchers (cached) ══════════
@st.cache_data(show_spinner=False)
def fetch_weekly_ohlcv(ticker: str) -> pd.DataFrame:
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
        info = yf.Ticker(yf_symbol(t)).info or {}
        dy_raw = safe_float(info.get("dividendYield"))
        dy = dy_raw * 100 if (not np.isnan(dy_raw) and dy_raw < 1) else dy_raw
        pr_raw = safe_float(info.get("payoutRatio"))
        pr = pr_raw * 100 if not np.isnan(pr_raw) else np.nan
        fcf_raw = safe_float(info.get("freeCashflow"))
        fcf_m = fcf_raw / 1e6 if not np.isnan(fcf_raw) else np.nan
        rows.append({"Ticker": t, "Dividend Yield (%)": dy, "Dividend Payout Ratio (%)": pr, "Free Cash Flow (LC m)": fcf_m})
    return pd.DataFrame(rows).set_index("Ticker").reindex(tickers)

# ══════════ Technical metrics ══════════

def technicals(df: pd.DataFrame) -> dict[str, float | str]:
    if df.empty or len(df) < 20:
        return {}
    last, prev = df.iloc[-1], df.iloc[-2]
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
        "Divergence": "Overbought" if last.Close >= ma10.iloc[-1] * 1.1 else ("Oversold" if last.Close <= ma10.iloc[-1] * 0.9 else "OK"),
        "Prev Price": prev.Close,
        "Prev MA10": ma10.iloc[-2],
    }

# ══════════ Page functions ══════════

def page_overview(tickers):
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

def page_screener(tickers):
    tech_df = pd.DataFrame({t: technicals(fetch_weekly_ohlcv(t)) for t in tickers}).T
    fund_df = fetch_fundamentals(tickers)
    df = pd.concat([tech_df, fund_df], axis=1).round(2)
    st.dataframe(df, use_container_width=True)

def page_chart(tickers):
    sel = st.selectbox("Select ticker", tickers, key="chart_sel")
    df = fetch_weekly_ohlcv(sel)
    if df.empty:
        st.warning("No price data available.")
        return
    dfp = df.copy()
    dfp["MA10"] = dfp["Close"].rolling(10).mean()
    dfp["MA20"] = dfp["Close"].rolling(20).mean()
    st.line_chart(dfp[["Close", "MA10", "MA20"]])

# ══════════ Main ══════════

def main():
    st.set_page_config(page_title="Defense Dashboard", layout="wide")
    hdr = st.container()
    with hdr:
        c1, c2, c3 = st.columns([1,6,2])
        c1.markdown("## 🛡️")
        c2.markdown("## Defense Sector Dashboard")
        c3.markdown(datetime.now(timezone.utc).strftime("Last refresh: %Y-%m-%d %H:%M UTC"))
    st.markdown("---")
    with st.sidebar.form(key="sidebar_form"):
        user_text = st.text_area("Enter tickers", st.session_state.get("tick_text", DEFAULT_TICKERS_TEXT), key="ticker_input", height=60)
        nav = st.radio("Navigate", ("Overview", "Screener", "Chart"), key="nav_choice")
        submitted = st.form_submit_button("Load / Refresh")
    if submitted or "tickers" not in st.session_state:
        st.session_state.tickers = parse_tickers(user
