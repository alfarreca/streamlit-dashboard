import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import numpy as np
import time
import yfinance as yf  # Added yfinance as fallback

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
RATE_LIMIT_DELAY = 2  # seconds to wait when rate limited

# --- Session State ---
if "trades" not in st.session_state:
    st.session_state.trades = pd.DataFrame(columns=["timestamp", "ticker", "strategy", "status"])
if "watchlist" not in st.session_state:
    st.session_state.watchlist = ["CCJ", "LEU", "SMR", "OKLO"]  # Default watchlist
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = None

# --- Enhanced Demo Data Fallback ---
def get_demo_data(ticker=None):
    """Improved fallback demo data when API fails"""
    demo_data = {
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
            },
            {
                "ticker": "CCJ",
                "reportDate": (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d"),
                "epsEstimate": 0.25,
                "eps": 0.28,
                "surprisePercent": 12.00
            },
            {
                "ticker": "LEU",
                "reportDate": (datetime.now() + timedelta(days=4)).strftime("%Y-%m-%d"),
                "epsEstimate": 0.15,
                "eps": 0.18,
                "surprisePercent": 20.00
            },
            {
                "ticker": "SMR",
                "reportDate": (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d"),
                "epsEstimate": -0.10,
                "eps": -0.08,
                "surprisePercent": 20.00
            },
            {
                "ticker": "OKLO",
                "reportDate": (datetime.now() + timedelta(days=6)).strftime("%Y-%m-%d"),
                "epsEstimate": -0.20,
                "eps": -0.15,
                "surprisePercent": 25.00
            }
        ]
    }
    
    if ticker:
        return next((item for item in demo_data["results"] if item["ticker"] == ticker), None)
    return demo_data

# --- Market Data Functions ---
def calculate_iv_rank(ticker):
    """Calculate IV percentile with more realistic mock data"""
    iv_values = {
        "CCJ": 65,
        "LEU": 72,
        "SMR": 58,
        "OKLO": 80,
        "NVDA": 45,
        "TSLA": 55
    }
    return iv_values.get(ticker, min(100, int(np.random.normal(60, 20))))

def get_stock_price(ticker):
    """Get stock price with yfinance fallback"""
    try:
        # Try yfinance first
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        if not hist.empty:
            return round(hist['Close'].iloc[-1], 2)
    except:
        pass
    
    # Fallback to demo data
    prices = {
        "CCJ": 42.50,
        "LEU": 38.20,
        "SMR": 25.75,
        "OKLO": 15.40,
        "NVDA": 450.50,
        "TSLA": 210.75
    }
    return prices.get(ticker, 100.00)

# --- Optimized Data Fetching ---
@st.cache_data(ttl=300, show_spinner="Fetching market data...")
def fetch_market_data():
    """Safe API call with retries, timeout, and better rate limit handling"""
    def _fetch_with_retry(url, params):
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.get(url, params=params, timeout=TIMEOUT)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    st.warning(f"Rate limited. Waiting {RATE_LIMIT_DELAY} seconds...")
                    time.sleep(RATE_LIMIT_DELAY)
                    continue
                else:
                    st.warning(f"API error: {response.status_code}")
                    break
            except Exception as e:
                st.warning(f"Request failed: {str(e)}")
                time.sleep(1)
        return None
    
    # Earnings data
    earnings_url = "https://api.polygon.io/v2/reference/earnings"
    earnings_params = {
        "apiKey": POLYGON_KEY,
        "date.gte": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
        "date.lte": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
        "limit": 10  # Reduced for stability
    }
    
    api_data = _fetch_with_retry(earnings_url, earnings_params)
    
    return {
        "earnings": api_data if api_data else get_demo_data(),
        "last_updated": datetime.now()
    }

# --- UI Components ---
def render_watchlist():
    """Render the watchlist section"""
    st.header("Watchlist Overview")
    
    for ticker in st.session_state.watchlist:
        with st.expander(f"### {ticker}", expanded=False):
            try:
                # Get data with fallback
                demo_data = get_demo_data(ticker)
                price = get_stock_price(ticker)
                iv_rank = calculate_iv_rank(ticker)
                
                cols = st.columns([1, 1, 2])
                
                with cols[0]:
                    st.metric("Price", f"${price:.2f}")
                    st.metric("IV Rank", f"{iv_rank}%")
                
                with cols[1]:
                    if demo_data:
                        eps_surprise = demo_data.get("surprisePercent", 0)
                        st.metric("EPS Surprise", f"{eps_surprise:.2f}%")
                    else:
                        st.metric("EPS Surprise", "N/A")
                    
                    st.metric("Volume", "1.0x")  # Simplified for demo
                
                with cols[2]:
                    if st.button("📊 Analyze", key=f"analyze_{ticker}"):
                        st.session_state.current_ticker = ticker
                    if st.button("❌ Remove", key=f"remove_{ticker}"):
                        st.session_state.watchlist.remove(ticker)
                        st.rerun()
            
            except Exception as e:
                st.error(f"Error displaying {ticker}: {str(e)}")

def safe_render_earnings_card(ticker, data):
    """Render earnings cards with error handling"""
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
            st.rerun()
            
        st.divider()
        st.metric("Last Refresh", 
                 st.session_state.last_refresh.strftime("%H:%M:%S") 
                 if st.session_state.last_refresh else "Never")
        
        # Watchlist management
        st.header("Manage Watchlist")
        new_ticker = st.text_input("Add ticker to watchlist", "").strip().upper()
        if new_ticker and st.button("Add"):
            if new_ticker not in st.session_state.watchlist:
                st.session_state.watchlist.append(new_ticker)
                st.rerun()
    
    # Data Loading
    with st.spinner("Loading market data..."):
        market_data = fetch_market_data()
        st.session_state.last_refresh = market_data["last_updated"]
    
    # Render watchlist first
    render_watchlist()
    st.divider()
    
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
        if st.session_state.trades.empty:
            st.info("No trades recorded yet")
        else:
            st.dataframe(st.session_state.trades, use_container_width=True)

if __name__ == "__main__":
    main()
