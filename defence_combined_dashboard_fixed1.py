# -*- coding: utf-8 -*-
"""Streamlit Defense‐Sector Dashboard integrated with Google Sheets

Compatible with Streamlit 1.x and Python 3.8+.
"""

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
from google.oauth2.service_account import Credentials
import gspread

# ──────────────────────────────────────────
# Google Sheets Authentication
# ──────────────────────────────────────────
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_INFO = st.secrets["GCP_SERVICE_ACCOUNT"]
creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
gc = gspread.authorize(creds)


# Open Google Sheet
sheet = gc.open_by_key("1sNYUiP4Pl8GVYQ1S7Ltc4ETv-ctOA1RVCdYkMb5xjjg").sheet1
sheet_df = pd.DataFrame(sheet.get_all_records()).dropna(subset=["Symbol", "Exchange"])

# ──────────────────────────────────────────
# Helper functions
# ──────────────────────────────────────────

def yf_symbol(symbol: str, exchange: str) -> str:
    suffix_map = {"ETR": "DE", "EPA": "PA", "LON": "L", "BIT": "MI", "STO": "ST",
                  "NYSE": "", "NASDAQ": ""}
    suffix = suffix_map.get(exchange.upper(), "")
    return f"{symbol}{('.' + suffix) if suffix else ''}"

@st.cache_data(show_spinner=False)
def fetch_weekly_ohlcv(symbol: str, exchange: str) -> pd.DataFrame:
    ysym = yf_symbol(symbol, exchange)
    daily = yf.Ticker(ysym).history(period="1y", interval="1d")[["Close", "Volume"]]
    weekly = pd.DataFrame({
        "Close": daily["Close"].resample("W-FRI").last(),
        "Volume": daily["Volume"].resample("W-FRI").sum(min_count=1)
    }).dropna(subset=["Close"])
    return weekly

@st.cache_data(show_spinner=False)
def fetch_fundamentals(df: pd.DataFrame) -> pd.DataFrame:
    records = []
    for _, row in df.iterrows():
        symbol, exchange = row["Symbol"], row["Exchange"]
        info = yf.Ticker(yf_symbol(symbol, exchange)).info or {}
        dy_raw = info.get("dividendYield", np.nan)
        dy_pct = dy_raw * 100 if dy_raw and dy_raw < 1 else dy_raw
        records.append({
            "Symbol": symbol,
            "Dividend Yield (%)": dy_pct,
            "Payout Ratio (%)": info.get("payoutRatio", np.nan) * 100,
            "Free Cash Flow (m)": info.get("freeCashflow", np.nan) / 1e6
        })
    return pd.DataFrame(records).set_index("Symbol")

# ──────────────────────────────────────────
# Streamlit UI
# ──────────────────────────────────────────
st.set_page_config(page_title="Defense Dashboard", layout="wide")
st.title("🛡️ Defense Sector: Weekly Signal Dashboard")

# Sidebar navigation
with st.sidebar:
    page = st.radio("Navigate", ("Overview", "Chart"))

# Overview Page
if page == "Overview":
    st.subheader("📊 Tickers from Google Sheets")
    fund_df = fetch_fundamentals(sheet_df)
    tech_records = {}
    for _, row in sheet_df.iterrows():
        weekly = fetch_weekly_ohlcv(row["Symbol"], row["Exchange"])
        if not weekly.empty:
            last = weekly.iloc[-1]
            ma10 = weekly["Close"].rolling(10).mean().iloc[-1]
            ma20 = weekly["Close"].rolling(20).mean().iloc[-1]
            tech_records[row["Symbol"]] = {
                "Price": last.Close,
                "MA10": ma10,
                "MA20": ma20,
                "% vs MA10": (last.Close - ma10) / ma10 * 100,
                "Volume": last.Volume,
                "Signal": "Buy" if ma10 > ma20 else "Sell",
                "Crossover": "Above" if last.Close > ma20 else "Below",
            }
    tech_df = pd.DataFrame(tech_records).T
    combined = pd.concat([tech_df, fund_df], axis=1).round(2)
    st.dataframe(combined, use_container_width=True)

# Chart Page
elif page == "Chart":
    symbol = st.selectbox("Select Ticker", sheet_df["Symbol"])
    exchange = sheet_df.loc[sheet_df["Symbol"] == symbol, "Exchange"].values[0]
    weekly = fetch_weekly_ohlcv(symbol, exchange)
    if weekly.empty:
        st.warning("No price data available.")
    else:
        weekly["MA10"] = weekly["Close"].rolling(10).mean()
        weekly["MA20"] = weekly["Close"].rolling(20).mean()
        st.subheader(f"📈 Weekly Chart: {symbol}")
        st.line_chart(weekly[["Close", "MA10", "MA20"]])
