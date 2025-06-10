import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- App Config ---
st.set_page_config(layout="wide")
st.title("🚀 Market Clubhouse Pro: Trading Levels with Options Flow")

st.markdown("""
Calculate dynamic **Support/Resistance** levels using Price, Volume, and **real options data** from Yahoo Finance.
""")

# --- Sidebar Inputs ---
st.sidebar.header("Settings")
ticker = st.sidebar.text_input("Stock/ETF Ticker", "SPY").upper()
lookback_days = st.sidebar.slider("Lookback Period (Trading Days)", 5, 30, 10)
k1 = st.sidebar.slider("Volume Weight (k1)", 0.1, 1.0, 0.3)
k2 = st.sidebar.slider("Options Flow Weight (k2)", 0.1, 1.0, 0.5)
k3 = st.sidebar.slider("Volatility Weight (k3)", 0.1, 1.0, 0.5)

# --- Validate Ticker ---
def validate_ticker(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        if info is None or 'regularMarketPrice' not in info or info['regularMarketPrice'] is None:
            return False
        return True
    except Exception:
        return False

if not ticker:
    st.error("Please enter a ticker symbol.")
    st.stop()

with st.spinner("Validating ticker..."):
    if not validate_ticker(ticker):
        st.error("Invalid or unavailable ticker symbol. Please enter a valid, listed stock/ETF ticker.")
        st.stop()

# --- Fetch Stock Data ---
@st.cache_data(ttl=3600)
def get_stock_data(ticker, lookback):
    end_date = datetime.today()
    start_date = end_date - timedelta(days=lookback * 3)
    df = yf.download(ticker, start=start_date, end=end_date, auto_adjust=True)
    # Flatten multi-level columns if present (e.g., ('Close', 'MSFT') -> 'Close')
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[df['Close'].notna()]
    df = df.tail(lookback)
    return df

with st.spinner("Fetching price history..."):
    df = get_stock_data(ticker, lookback_days)
    # Normalize column names to title case (e.g., 'high' → 'High')
    df.columns = [str(col).title() for col in df.columns]

    # Debug: Show DataFrame shape and columns
    st.write("Downloaded DataFrame shape:", df.shape)
    st.write("Columns:", df.columns)
    st.write("Preview:", df.head())

    # Check for empty DataFrame or missing columns
    required_cols = {'High', 'Low', 'Close', 'Volume'}
    if df.empty or not required_cols.issubset(df.columns):
        st.error("No or insufficient stock data found for this period, or required columns are missing. "
                 "Try a different ticker or timeframe.")
        st.stop()

    if len(df) < lookback_days // 2:
        st.error("Insufficient stock data for this period. Try a different ticker or longer lookback.")
        st.stop()

# --- Robust ATR Calculation ---
def calculate_atr(df, period=14):
    required_cols = {'High', 'Low', 'Close'}
    if df.empty or not required_cols.issubset(df.columns):
        st.error("Not enough data to calculate ATR (missing columns or empty data).")
        st.stop()
    try:
        from ta.volatility import
