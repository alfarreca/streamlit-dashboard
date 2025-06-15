import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import numpy as np
import time
import io

# --- Configuration ---
st.set_page_config(layout="wide", page_title="AlphaPod Trader", page_icon="📈")

# --- API Setup ---
POLYGON_KEY = st.secrets.get("POLYGON_KEY", "demo_key")
TIMEOUT = 10
MAX_RETRIES = 3

# --- Session State ---
if "trades" not in st.session_state:
    st.session_state.trades = pd.DataFrame(columns=["timestamp", "ticker", "strategy", "status"])
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = None

# --- Add a demo trade for visual feedback if table is empty ---
if st.session_state.trades.empty:
    st.session_state.trades = pd.DataFrame([{
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ticker": "NVDA",
        "strategy": "Earnings Beat",
        "status": "Open"
    }])

# --- Market Data Fetching ---
@st.cache_data(ttl=300, show_spinner="Fetching market data...")
def fetch_data(url, params):
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, params=params, timeout=TIMEOUT)
            if response.status_code == 200:
                return response.json()
            time.sleep(2 ** attempt)
        except requests.RequestException:
            time.sleep(1)
    return None

def get_earnings_data():
    url = "https://api.polygon.io/v2/reference/earnings"
    params = {
        "apiKey": POLYGON_KEY,
        "date.gte": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
        "date.lte": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
        "limit": 20
    }
    data = fetch_data(url, params)
    # --- Always fallback to demo data if API fails or returns nothing ---
    if not data or "results" not in data or not data["results"]:
        data = {
            "results": [
                {
                    "ticker": "NVDA",
                    "reportDate": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                    "epsEstimate": 3.34,
                    "eps": 3.71,
                    "surprisePercent": 11.08
                },
                {
                    "ticker": "TSLA",
                    "reportDate": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"),
                    "epsEstimate": 0.73,
                    "eps": 0.85,
                    "surprisePercent": 16.44
                }
            ]
        }
    return data

def get_stock_quote(ticker):
    # Return a fixed price for demo, but try API if you wish
    demo_prices = {"NVDA": 450.50, "TSLA": 210.75, "AAPL": 175.25, "MSFT": 310.40}
    return demo_prices.get(ticker, 100.00)

def calculate_iv_rank(ticker):
    # Mock IV rank
    return int(np.clip(np.random.normal(50, 20), 0, 100))

# --- UI Components ---
def render_earnings_card(ticker, data):
    with st.expander(f"{ticker}", expanded=False):
        cols = st.columns([1, 1, 2])

        with cols[0]:
            st.metric("EPS Surprise", f"{data['surprise_pct']:.2f}%")
            st.metric("IV Rank", f"{data['iv_rank']:.0f}%")

        with cols[1]:
            price = data.get('price', 'N/A')
            st.metric("Price", f"${price:.2f}" if price != 'N/A' else price)
            st.metric("Volume", f"{data['volume_ratio']:.1f}x")

        with cols[2]:
            if st.button("📊 Analyze", key=f"analyze_{ticker}"):
                st.session_state.current_ticker = ticker
            if st.button("➕ Add to Watchlist", key=f"watch_{ticker}"):
                if ticker not in st.session_state.watchlist:
                    st.session_state.watchlist.append(ticker)
                    st.toast(f"{ticker} added to watchlist")
                else:
                    st.toast(f"{ticker} already in watchlist")

def remove_from_watchlist(ticker):
    if ticker in st.session_state.watchlist:
        st.session_state.watchlist.remove(ticker)
        st.toast(f"{ticker} removed from watchlist")

# --- Main Application ---
def main():
    st.title("📈 AlphaPod Trader")

    # Sidebar controls
    with st.sidebar:
        st.header("Controls")
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.session_state.last_refresh = datetime.now()

        st.metric("Last Refresh",
                  st.session_state.last_refresh.strftime("%Y-%m-%d %H:%M:%S")
                  if st.session_state.last_refresh else "Never")

        # --- XLSX Watchlist Upload ---
        st.header("Watchlist Management")
        uploaded_file = st.file_uploader("Upload Watchlist (.xlsx)", type=["xlsx"])
        if uploaded_file is not None:
            try:
                df_watchlist = pd.read_excel(uploaded_file)
                if "Symbol" in df_watchlist.columns and "Exchange" in df_watchlist.columns:
                    tickers = df_watchlist["Symbol"].astype(str).str.upper().tolist()
                    # Only add new tickers
                    new_tickers = [t for t in tickers if t not in st.session_state.watchlist]
                    st.session_state.watchlist.extend(new_tickers)
                    st.success(f"Added {len(new_tickers)} tickers to watchlist!")
                else:
                    st.error("Excel file must contain columns: 'Symbol' and 'Exchange'.")
            except Exception as e:
                st.error(f"Failed to read file: {e}")

        if st.session_state.watchlist:
            for ticker in st.session_state.watchlist:
                col1, col2 = st.columns([4, 1])
                col1.write(ticker)
                if col2.button("❌", key=f"remove_{ticker}"):
                    remove_from_watchlist(ticker)
        else:
            st.write("Watchlist is empty.")

    # Fetch data
    earnings_data = get_earnings_data()
    st.session_state.last_refresh = datetime.now()

    # Tabs for data display
    earnings_tab, portfolio_tab = st.tabs(["📅 Earnings Plays", "💼 Portfolio"])

    with earnings_tab:
        st.header("Upcoming Earnings Opportunities")
        for play in earnings_data["results"][:15]:
            ticker = play["ticker"]
            price = get_stock_quote(ticker)
            data = {
                "surprise_pct": play.get("surprisePercent", 0),
                "iv_rank": calculate_iv_rank(ticker),
                "price": price,
                "volume_ratio": np.random.uniform(0.8, 2.0)  # Demo value
            }
            render_earnings_card(ticker, data)

    with portfolio_tab:
        st.header("Trade History")
        st.dataframe(st.session_state.trades, use_container_width=True)

if __name__ == "__main__":
    main()
