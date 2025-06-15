import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import numpy as np

# .streamlit/secrets.toml
POLYGON_KEY = "rOaZAKKbjkTXFj7FVfQaWormDpSQj8Ki"

# --- Configuration ---
st.set_page_config(layout="wide", page_title="AlphaPod Trader")
POLYGON_KEY = st.secrets["POLYGON_KEY"]  # Set in Streamlit Cloud secrets

# --- Session State ---
if "trades" not in st.session_state:
    st.session_state.trades = []
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []

# --- Core Functions ---
def fetch_live_earnings():
    """Get real earnings data from Polygon.io"""
    url = "https://api.polygon.io/v2/reference/earnings"
    params = {
        "apiKey": POLYGON_KEY,
        "date.gte": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
        "date.lte": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
        "limit": 50
    }
    try:
        response = requests.get(url, params=params)
        data = response.json().get("results", [])
        return sorted(data, key=lambda x: x.get("reportDate", ""), reverse=True)
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return []

def enhance_earnings_data(earnings):
    """Add trading signals to raw earnings data"""
    enhanced = []
    for event in earnings:
        ticker = event.get("ticker", "")
        
        # Get additional market data
        try:
            stock_data = get_stock_details(ticker)
            options_data = get_options_data(ticker)
            
            enhanced.append({
                "ticker": ticker,
                "date": event.get("reportDate"),
                "eps_estimate": event.get("epsEstimate"),
                "eps_actual": event.get("eps"),
                "surprise_pct": event.get("surprisePercent"),
                "price": stock_data.get("price"),
                "iv_rank": calculate_iv_rank(ticker),
                "volume_ratio": stock_data.get("volume") / stock_data.get("avgVolume"),
                "short_interest": get_short_interest(ticker),
                "recommended_strategy": recommend_strategy(ticker)
            })
        except:
            continue
    return enhanced

def get_stock_details(ticker):
    """Get real-time stock data"""
    url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}"
    response = requests.get(url, params={"apiKey": POLYGON_KEY})
    data = response.json().get("ticker", {})
    return {
        "price": data.get("day", {}).get("c"),
        "volume": data.get("day", {}).get("v"),
        "avgVolume": data.get("day", {}).get("av")
    }

def recommend_strategy(ticker):
    """AI-powered strategy recommendation"""
    # In production, replace with ML model
    iv = calculate_iv_rank(ticker)
    if iv > 75:
        return "Iron Condor"
    elif iv > 50:
        return "Straddle"
    else:
        return "Directional Spread"

# --- UI Components ---
def render_earnings_card(ticker, data):
    with st.expander(f"{ticker} - {data['date']}"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Price", f"${data['price']:,.2f}")
            st.metric("IV Rank", f"{data['iv_rank']:.0f}%")
            st.metric("EPS Surprise", f"{data['surprise_pct'] or 0:.2f}%")
            
        with col2:
            st.metric("Volume Ratio", f"{data['volume_ratio']:.1f}x")
            st.metric("Short Interest", f"{data['short_interest'] or 0:.2f}%")
            st.metric("Strategy", data["recommended_strategy"])
        
        if st.button("Execute Trade", key=f"trade_{ticker}"):
            execute_trade(ticker, data["recommended_strategy"])
            
        if st.button("Add to Watchlist", key=f"watch_{ticker}"):
            st.session_state.watchlist.append(ticker)
            st.success(f"Added {ticker} to watchlist")

# --- Main App ---
st.title("📈 AlphaPod Trader - Live Market Data")
st.caption("Pod shop strategies for retail traders")

tab1, tab2, tab3 = st.tabs(["Earnings Plays", "Watchlist", "Trade History"])

with tab1:
    st.header("Upcoming Earnings Plays")
    earnings_data = enhance_earnings_data(fetch_live_earnings())
    
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        min_iv = st.slider("Min IV Rank", 0, 100, 70)
    with col2:
        min_surprise = st.slider("Min EPS Surprise %", -50, 50, 0)
    with col3:
        strategy_filter = st.multiselect(
            "Strategies",
            ["Iron Condor", "Straddle", "Directional Spread"],
            default=["Iron Condor", "Straddle"]
        )
    
    filtered_data = [
        d for d in earnings_data 
        if (d["iv_rank"] >= min_iv) and 
           (d["surprise_pct"] or 0 >= min_surprise) and
           (d["recommended_strategy"] in strategy_filter)
    ]
    
    for play in filtered_data:
        render_earnings_card(play["ticker"], play)

with tab2:
    st.header("Your Watchlist")
    if st.session_state.watchlist:
        for ticker in st.session_state.watchlist:
            st.write(ticker)
    else:
        st.info("No stocks in watchlist")

with tab3:
    st.header("Trade History")
    if st.session_state.trades:
        st.dataframe(pd.DataFrame(st.session_state.trades))
    else:
        st.info("No trades executed yet")

# --- Hidden Utility Functions ---
def calculate_iv_rank(ticker):
    """Calculate IV percentile (mock for demo)"""
    return min(100, int(np.random.normal(60, 20)))

def get_short_interest(ticker):
    """Get short interest percentage (mock for demo)"""
    return round(np.random.uniform(1, 10), 2)

def execute_trade(ticker, strategy):
    """Simulate trade execution"""
    st.session_state.trades.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "ticker": ticker,
        "strategy": strategy,
        "status": "Executed"
    })
