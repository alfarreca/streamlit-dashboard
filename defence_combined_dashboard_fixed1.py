# -*- coding: utf-8 -*-
"""Updated Streamlit Defense-Sector Dashboard integrated with Google Sheets

Compatible with Streamlit 1.x and Python 3.8+.
"""

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
from google.oauth2.service_account import Credentials
import gspread

# Google Sheets Authentication
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_INFO = st.secrets["GCP_SERVICE_ACCOUNT"]
creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
gc = gspread.authorize(creds)

sheet = gc.open_by_key("1sNYUiP4Pl8GVYQ1S7Ltc4ETv-ctOA1RVCdYkMb5xjjg").sheet1
sheet_df = pd.DataFrame(sheet.get_all_records()).dropna(subset=["Symbol", "Exchange"])

# Helper functions
def yf_symbol(symbol: str, exchange: str) -> str:
    suffix_map = {"ETR": "DE", "EPA": "PA", "LON": "L", "BIT": "MI", "STO": "ST",
                  "NYSE": "", "NASDAQ": ""}
    suffix = suffix_map.get(exchange.upper(), "")
    return f"{symbol}{('.' + suffix) if suffix else ''}"

@st.cache_data(show_spinner=False)
def fetch_weekly_data(symbol: str, exchange: str) -> pd.DataFrame:
    ysym = yf_symbol(symbol, exchange)
    daily = yf.Ticker(ysym).history(period="1y", interval="1d")[["Close", "Volume"]]
    weekly = daily.resample("W-FRI").agg({"Close": "last", "Volume": "sum"}).dropna()
    weekly['MA10'] = weekly['Close'].rolling(10).mean()
    weekly['MA20'] = weekly['Close'].rolling(20).mean()
    return weekly

@st.cache_data(show_spinner=False)
def fetch_fundamentals(df: pd.DataFrame) -> pd.DataFrame:
    records = []
    for _, row in df.iterrows():
        info = yf.Ticker(yf_symbol(row["Symbol"], row["Exchange"])).info
        dy_raw = info.get("dividendYield", np.nan)
        dy_pct = dy_raw * 100 if dy_raw and dy_raw < 1 else dy_raw
        records.append({
            "Symbol": row["Symbol"],
            "Dividend Yield (%)": dy_pct,
            "Dividend Payout Ratio (%)": info.get("payoutRatio", np.nan) * 100,
            "Free Cash Flow (LC m)": info.get("freeCashflow", np.nan) / 1e6,
            "Prev Price": info.get("previousClose", np.nan)
        })
    return pd.DataFrame(records).set_index("Symbol")

# Streamlit UI
st.set_page_config(page_title="Defense Dashboard", layout="wide")
st.title("🛡️ Defense Sector: Weekly Signal Dashboard")

st.checkbox("Show All Tickers Table", True)

fund_df = fetch_fundamentals(sheet_df)
records = {}
for _, row in sheet_df.iterrows():
    weekly = fetch_weekly_data(row["Symbol"], row["Exchange"])
    last = weekly.iloc[-1]
    records[row["Symbol"]] = {
        "Price": last.Close,
        "MA10": last.MA10,
        "MA20": last.MA20,
        "% vs MA10": ((last.Close - last.MA10) / last.MA10 * 100),
        "Volume": last.Volume,
        "Vol MA10": weekly.Volume.rolling(10).mean().iloc[-1],
        "Signal": "Buy" if last.MA10 > last.MA20 else "Sell",
        "Last Updated": pd.Timestamp.today().date(),
        "Crossover": "Above" if last.Close > last.MA20 else "Below",
        "Divergence": "Overbought" if last.Close > last.MA20 else "OK",
        "Prev MA10": weekly.MA10.iloc[-2] if len(weekly) > 1 else np.nan
    }

tech_df = pd.DataFrame(records).T

# Only keep fundamental columns not present in tech_df to avoid duplicates
fund_cols = [col for col in fund_df.columns if col not in tech_df.columns]
fund_df_trimmed = fund_df[fund_cols]

# Reset index for merge
tech_df = tech_df.reset_index().rename(columns={'index': 'Symbol'})
combined_df = tech_df.merge(fund_df_trimmed.reset_index(), how='left', left_on='Symbol', right_on='Symbol')

# Set Symbol as index for display
combined_df = combined_df.set_index('Symbol')

st.subheader("📊 All Tickers – Technical & Fundamental Metrics")
st.dataframe(combined_df, use_container_width=True)

# Ticker Chart
selected_ticker = st.selectbox("Select Ticker to View Chart", sheet_df["Symbol"].tolist())
selected_exchange = sheet_df.loc[sheet_df["Symbol"] == selected_ticker, "Exchange"].iloc[0]
weekly_selected = fetch_weekly_data(selected_ticker, selected_exchange)

st.subheader(f"📈 {selected_ticker}")
st.line_chart(weekly_selected[["Close", "MA10", "MA20"]])
