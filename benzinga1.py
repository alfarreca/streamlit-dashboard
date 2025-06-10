import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(layout="wide")
st.title("🚀 Market Clubhouse Pro: Trading Levels with Options Flow")

st.markdown("""
Calculate dynamic **Support/Resistance** levels using Price, Volume, and **real options data** from Yahoo Finance.
""")

# --- Sidebar Inputs ---
st.sidebar.header("Settings")
ticker = st.sidebar.text_input("Stock/ETF Ticker", "SPY").upper()
lookback_days = st.sidebar.slider("Lookback Period (Days)", 5, 30, 10)
k1 = st.sidebar.slider("Volume Weight (k1)", 0.1, 1.0, 0.3)
k2 = st.sidebar.slider("Options Flow Weight (k2)", 0.1, 1.0, 0.5)
k3 = st.sidebar.slider("Volatility Weight (k3)", 0.1, 1.0, 0.5)

# --- Input Validation Function ---
def validate_ticker(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        if info is None or 'regularMarketPrice' not in info or info['regularMarketPrice'] is None:
            return False
        return True
    except Exception:
        return False

if not ticker or not validate_ticker(ticker):
    st.error("Invalid or unavailable ticker symbol. Please enter a valid listed stock/ETF ticker.")
    st.stop()

# --- Data Fetching with Loading Spinner ---
@st.cache_data(ttl=3600)
def get_stock_data(ticker, lookback):
    end_date = datetime.today()
    start_date = end_date - timedelta(days=lookback*2)  # Double range for non-trading days
    data = yf.download(ticker, start=start_date, end=end_date, auto_adjust=True)
    data = data[-lookback:]  # Only keep last N trading days
    return data

# Example loading spinner usage:
with st.spinner("Fetching data, please wait..."):
    df = get_stock_data(ticker, lookback_days)
    if df.empty:
        st.error("No stock data found for this period. Try a different ticker or timeframe.")
        st.stop()
