import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import numpy as np
import time
import yfinance as yf

# --- Configuration ---
st.set_page_config(
    layout="wide",
    page_title="AlphaPod Trader",
    page_icon="📈"
)

# --- API Setup ---
POLYGON_KEY = st.secrets.get("POLYGON_KEY", "demo_key")
TIMEOUT = 10  # seconds
MAX_RETRIES = 3
RATE_LIMIT_DELAY = 2

# --- Session State Initialization ---
for state_var, default_value in [
    ("trades", pd.DataFrame(columns=["timestamp", "ticker", "strategy", "status"])),
    ("watchlist", ["CCJ", "LEU", "SMR", "OKLO"]),
    ("last_refresh", None),
    ("current_ticker", None)
]:
    if state_var not in st.session_state:
        st.session_state[state_var] = default_value

# --- Enhanced Demo Data Fallback ---
def get_demo_data(ticker=None):
    demo_data = {
        "results": [
            {"ticker": "NVDA", "reportDate": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"), "surprisePercent": 11.08},
            {"ticker": "TSLA", "reportDate": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"), "surprisePercent": 16.44},
            {"ticker": "CCJ", "reportDate": (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d"), "surprisePercent": 12.00},
            {"ticker": "LEU", "reportDate": (datetime.now() + timedelta(days=4)).strftime("%Y-%m-%d"), "surprisePercent": 20.00}
        ]
    }
    return next((item for item in demo_data["results"] if item["ticker"] == ticker), None) if ticker else demo_data

# --- Data Functions ---
def calculate_iv_rank(ticker):
    return np.clip(np.random.normal(60, 20), 0, 100)

def get_stock_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        if not hist.empty:
            return round(hist['Close'].iloc[-1], 2)
    except:
        pass
    return 100.00

@st.cache_data(ttl=300, show_spinner="Fetching market data...")
def fetch_market_data():
    earnings_url = "https://api.polygon.io/v2/reference/earnings"
    earnings_params = {"apiKey": POLYGON_KEY, "limit": 10}

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(earnings_url, params=earnings_params, timeout=TIMEOUT)
            if response.status_code == 200:
                return {"earnings": response.json(), "last_updated": datetime.now()}
            time.sleep(RATE_LIMIT_DELAY if response.status_code == 429 else 1)
        except Exception:
            time.sleep(1)

    return {"earnings": get_demo_data(), "last_updated": datetime.now()}

# --- UI Rendering ---
def render_watchlist():
    st.header("Watchlist")
    for ticker in st.session_state.watchlist:
        cols = st.columns([1, 1, 2])
        cols[0].metric("Price", f"${get_stock_price(ticker):.2f}")
        cols[0].metric("IV Rank", f"{calculate_iv_rank(ticker):.2f}%")

        eps_surprise = get_demo_data(ticker).get("surprisePercent", "N/A")
        cols[1].metric("EPS Surprise", f"{eps_surprise}%")
        cols[1].metric("Volume", "1.0x")

        if cols[2].button("📊 Analyze", key=f"analyze_{ticker}"):
            st.session_state.current_ticker = ticker
        if cols[2].button("❌ Remove", key=f"remove_{ticker}"):
            st.session_state.watchlist.remove(ticker)
            st.rerun()

# --- Main Application ---
def main():
    st.title("AlphaPod Trader")

    with st.sidebar:
        st.header("Controls")
        if st.button("🔄 Refresh"):
            st.cache_data.clear()
            st.session_state.last_refresh = datetime.now()
            st.rerun()
        st.metric("Last Refresh", st.session_state.last_refresh.strftime("%H:%M:%S") if st.session_state.last_refresh else "Never")

        ticker_to_add = st.text_input("Add ticker", "").strip().upper()
        if ticker_to_add and st.button("➕ Add"):
            if ticker_to_add not in st.session_state.watchlist:
                st.session_state.watchlist.append(ticker_to_add)
                st.rerun()

    market_data = fetch_market_data()
    render_watchlist()

    tab1, tab2 = st.tabs(["Earnings Plays", "Portfolio"])
    with tab1:
        st.header("Earnings Opportunities")
        for play in market_data["earnings"].get("results", []):
            ticker = play["ticker"]
            cols = st.columns([1,1,2])
            cols[0].metric("EPS Surprise", f"{play.get('surprisePercent', 0):.2f}%")
            cols[0].metric("IV Rank", f"{calculate_iv_rank(ticker):.2f}%")
            cols[1].metric("Price", f"${get_stock_price(ticker):.2f}")
            cols[1].metric("Volume", "1.0x")
            if cols[2].button("📊 Analyze", key=f"earnings_analyze_{ticker}"):
                st.session_state.current_ticker = ticker

    with tab2:
        st.header("Portfolio")
        if st.session_state.trades.empty:
            st.info("No trades recorded yet")
        else:
            st.dataframe(st.session_state.trades)

if __name__ == "__main__":
    main()
