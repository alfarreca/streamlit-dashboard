import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import numpy as np
import time

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

# --- Session State ---
if "trades" not in st.session_state:
    st.session_state.trades = pd.DataFrame(columns=["timestamp", "ticker", "strategy", "status"])
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = None

# --- Demo Data Fallback ---
def get_demo_data():
    """Fallback demo data when API fails"""
    return {
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

# --- Market Data Functions ---
def calculate_iv_rank(ticker):
    """Calculate IV percentile (mock for demo)"""
    return min(100, int(np.random.normal(60, 20)))

def get_stock_price(ticker):
    """Get stock price (mock for demo)"""
    prices = {
        "NVDA": 450.50,
        "TSLA": 210.75,
        "AAPL": 175.25,
        "MSFT": 310.40
    }
    return prices.get(ticker, 100.00)

# --- Optimized Data Fetching ---
@st.cache_data(ttl=300, show_spinner="Fetching market data...")
def fetch_market_data():
    """Safe API call with retries and timeout"""
    def _fetch_with_retry(url, params):
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.get(url, params=params, timeout=TIMEOUT)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    time.sleep(2 ** attempt)  # Exponential backoff
            except Exception:
                time.sleep(1)
        return None
    
    # Earnings data
    earnings_url = "https://api.polygon.io/v2/reference/earnings"
    earnings_params = {
        "apiKey": POLYGON_KEY,
        "date.gte": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
        "date.lte": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
        "limit": 20  # Reduced for stability
    }
    
    return {
        "earnings": _fetch_with_retry(earnings_url, earnings_params) or get_demo_data(),
        "last_updated": datetime.now()
    }

# --- UI Components ---
def safe_render_earnings_card(ticker, data):
    try:
        with st.expander(f"{ticker}", expanded=False):
            cols = st.columns([1,1,2])
            
            with cols[0]:
                st.metric("EPS Surprise", f"{data.get('surprise_pct', 0):.2f}%")
                st.metric("IV Rank", f"{data.get('iv_rank', 0):.0f}%")
                
            with cols[1]:
                st.metric("Price", f"${data.get('price', 0):.2f}")
                st.metric("Volume", f"{data.get('volume_ratio', 0):.1f}x")
                
            with cols[2]:
                if st.button("📊 Analyze", key=f"analyze_{ticker}"):
                    st.session_state.current_ticker = ticker
                if st.button("➕ Watchlist", key=f"watch_{ticker}"):
                    if ticker not in st.session_state.watchlist:
                        st.session_state.watchlist.append(ticker)
                        st.toast(f"Added {ticker} to watchlist")
    except Exception as e:
        st.error(f"Error rendering card: {str(e)}")

# --- Main App Flow ---
def main():
    st.title("AlphaPod Trader")
    
    # Control Panel
    with st.sidebar:
        st.header("Controls")
        if st.button("🔄 Refresh Data", type="primary"):
            st.cache_data.clear()
            st.session_state.last_refresh = datetime.now()
            
        st.divider()
        st.metric("Last Refresh", 
                 st.session_state.last_refresh.strftime("%H:%M:%S") 
                 if st.session_state.last_refresh else "Never")
    
    # Data Loading
    with st.spinner("Loading market data..."):
        market_data = fetch_market_data()
        st.session_state.last_refresh = market_data["last_updated"]
    
    # Main Tabs
    tab1, tab2 = st.tabs(["Earnings Plays", "Portfolio"])
    
    with tab1:
        st.header("Earnings Opportunities")
        for play in market_data["earnings"].get("results", [])[:15]:  # Limit to 15 items
            safe_render_earnings_card(play["ticker"], {
                "surprise_pct": play.get("surprisePercent", 0),
                "iv_rank": calculate_iv_rank(play["ticker"]),
                "price": get_stock_price(play["ticker"]),
                "volume_ratio": 1.0  # Simplified for demo
            })
    
    with tab2:
        st.header("Your Portfolio")
        st.dataframe(st.session_state.trades, use_container_width=True)

if __name__ == "__main__":
    main()
