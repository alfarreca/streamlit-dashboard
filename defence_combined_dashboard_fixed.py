# -*- coding: utf-8 -*-
"""Streamlit Defense‑Sector Dashboard"""

import re
from io import StringIO
import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go

# ─────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────

def yf_symbol(code: str) -> str:
    if ":" not in code:
        return code
    exch, sym = code.split(":", 1)
    suffix = {
        "ETR": "DE", "STO": "ST", "EPA": "PA",
        "LON": "L", "BIT": "MI", "NYSE": "", "NASDAQ": ""
    }.get(exch.upper(), "")
    return f"{sym}{('.' + suffix) if suffix else ''}"

def safe_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return np.nan

@st.cache_data(show_spinner=False)
def fetch_weekly_ohlcv(ticker: str) -> pd.DataFrame:
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
    weekly = pd.DataFrame({
        "Close": daily["Close"].resample("W-FRI").last(),
        "Volume": daily["Volume"].resample("W-FRI").sum(min_count=1),
    }).dropna(subset=["Close"])
    return weekly

@st.cache_data(show_spinner=False)
def fetch_fundamentals(tickers: tuple[str, ...]) -> pd.DataFrame:
    records = []
    for t in tickers:
        try:
            info = yf.Ticker(yf_symbol(t)).info or {}
        except Exception:
            info = {}
        dy = safe_float(info.get("dividendYield"))
        dy_pct = dy * 100 if (not np.isnan(dy) and dy < 1) else dy
        pr = safe_float(info.get("payoutRatio"))
        pr_pct = pr * 100 if not np.isnan(pr) else np.nan
        fcf = safe_float(info.get("freeCashflow"))
        fcf_m = fcf / 1e6 if not np.isnan(fcf) else np.nan
        records.append({
            "Ticker": t,
            "Dividend Yield (%)": dy_pct,
            "Dividend Payout Ratio (%)": pr_pct,
            "Free Cash Flow (LC m)": fcf_m,
        })
    return pd.DataFrame(records).set_index("Ticker").reindex(tickers)

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
            "Overbought" if last.Close >= ma10.iloc[-1] * 1.1 else
            "Oversold" if last.Close <= ma10.iloc[-1] * 0.9 else "OK"
        ),
        "Prev Price": prev.Close,
        "Prev MA10": ma10.iloc[-2],
    }

# ─────────────────────────────────────────────
# Streamlit Layout
# ─────────────────────────────────────────────

st.set_page_config(page_title="Defense Dashboard", layout="wide")
st.sidebar.title("🧰 Defense Stocks")
page = st.sidebar.radio("Navigate", ("Overview", "Screener", "Chart"))
st.sidebar.markdown("---")
st.sidebar.markdown("Made with ❤️ using Streamlit")

# Ticker options dropdown
all_choices = [
    "ETR:RHM", "STO:SAAB-B", "EPA:HO", "LON:BA", "BIT:LDO",
    "NYSE:NOC", "NYSE:LMT", "NYSE:GD", "NASDAQ:AVAV", "NASDAQ:RTX"
]
default_tickers = ["ETR:RHM", "STO:SAAB-B", "EPA:HO"]

tickers = st.session_state.get("tickers", default_tickers)

# -------------------- Overview Tab --------------------
if page == "Overview":
    st.markdown("## 🗂️ Overview")
    selected = st.multiselect("Select tickers to analyze", options=all_choices, default=tickers)
    st.session_state["tickers"] = selected
    tickers = selected

    show_tbl = st.checkbox("✅ Show full metrics table", True)
    fund_df = fetch_fundamentals(tickers)
    tech_df = pd.DataFrame({t: technicals(fetch_weekly_ohlcv(t)) for t in tickers}).T
    combined = pd.concat([tech_df, fund_df], axis=1).round(2)

    if show_tbl:
        st.markdown("### 📊 All Metrics")
        st.dataframe(combined, use_container_width=True)
        csv = combined.to_csv().encode("utf-8")
        st.download_button(
            label="📥 Download metrics as CSV",
            data=csv,
            file_name="defense_metrics.csv",
            mime="text/csv",
        )

# -------------------- Screener Tab --------------------
elif page == "Screener":
    st.markdown("## 🔍 Screener")
    signal_filter = st.selectbox("Filter by Signal", options=["All", "Buy", "Sell"])

    fund_df = fetch_fundamentals(tickers)
    tech_df = pd.DataFrame({t: technicals(fetch_weekly_ohlcv(t)) for t in tickers}).T
    combined = pd.concat([tech_df, fund_df], axis=1).round(2)

    if signal_filter != "All":
        combined = combined[combined["Signal"] == signal_filter]

    if combined.empty:
        st.warning("No tickers match your selected signal.")
    else:
        st.dataframe(combined, use_container_width=True)

# -------------------- Chart Tab --------------------
elif page == "Chart":
    st.markdown("## 📈 Chart")
    sel = st.selectbox("Select Ticker to Chart", tickers)
    wk = fetch_weekly_ohlcv(sel)
    if wk.empty:
        st.warning("No price data available for that ticker.")
    else:
        plot = wk.copy()
        plot["MA10"] = plot["Close"].rolling(10).mean()
        plot["MA20"] = plot["Close"].rolling(20).mean()

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=plot.index, y=plot["Close"], mode='lines', name='Close'))
        fig.add_trace(go.Scatter(x=plot.index, y=plot["MA10"], mode='lines', name='MA10'))
        fig.add_trace(go.Scatter(x=plot.index, y=plot["MA20"], mode='lines', name='MA20'))

        fig.update_layout(
            title=f"{sel} Weekly Price Chart with MAs",
            xaxis_title="Date",
            yaxis_title="Price",
            hovermode="x unified",
            height=500
        )

        st.plotly_chart(fig, use_container_width=True)
