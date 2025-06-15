import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- Configuration ---
st.set_page_config(
    layout="wide",
    page_title="AlphaPod Trader Pro",
    page_icon="📊",
    initial_sidebar_state="expanded"
)

# --- API Setup ---
POLYGON_KEY = st.secrets.get("POLYGON_KEY", "demo_key")
TIMEOUT = 8  # seconds
MAX_RETRIES = 2

# --- Session State ---
if "trades" not in st.session_state:
    st.session_state.trades = pd.DataFrame(columns=["timestamp", "ticker", "strategy", "status", "quantity", "entry_price"])
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = None
if "chart_period" not in st.session_state:
    st.session_state.chart_period = "3mo"

# --- Data Functions ---
@st.cache_data(ttl=1800)  # 30 minute cache
def get_historical_data(ticker, period="3mo"):
    """Get OHLCV data with technical indicators"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        
        if hist.empty:
            return None
            
        # Calculate indicators
        hist['SMA_20'] = hist['Close'].rolling(20).mean()
        hist['SMA_50'] = hist['Close'].rolling(50).mean()
        hist['Upper_BB'], hist['Lower_BB'] = (
            hist['SMA_20'] + 2*hist['Close'].rolling(20).std(),
            hist['SMA_20'] - 2*hist['Close'].rolling(20).std()
        )
        return hist[['Open', 'High', 'Low', 'Close', 'Volume', 'SMA_20', 'SMA_50', 'Upper_BB', 'Lower_BB']]
    except Exception as e:
        st.error(f"YFinance Error: {str(e)}")
        return None

def get_fundamentals(ticker):
    """Get key fundamental metrics"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            "pe_ratio": info.get('trailingPE'),
            "market_cap": info.get('marketCap'),
            "dividend_yield": info.get('dividendYield'),
            "beta": info.get('beta')
        }
    except:
        return None

# --- Market Data Fetching ---
@st.cache_data(ttl=300, show_spinner="Fetching live market data...")
def fetch_market_data():
    """Get earnings data from Polygon with fallback"""
    def _fetch_with_retry(url, params):
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.get(url, params=params, timeout=TIMEOUT)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    time.sleep(2 ** attempt)
            except Exception:
                time.sleep(1)
        return None
    
    earnings_url = "https://api.polygon.io/v2/reference/earnings"
    params = {
        "apiKey": POLYGON_KEY,
        "date.gte": (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d"),
        "date.lte": (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d"),
        "limit": 25
    }
    
    return {
        "earnings": _fetch_with_retry(earnings_url, params) or get_demo_earnings(),
        "last_updated": datetime.now()
    }

def get_demo_earnings():
    """Fallback demo data"""
    return {
        "results": [
            {
                "ticker": "NVDA",
                "reportDate": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                "epsEstimate": 3.34,
                "eps": 3.71,
                "surprisePercent": 11.08,
                "revenueEstimate": 16.18e9,
                "revenue": 18.12e9
            },
            {
                "ticker": "TSLA",
                "reportDate": (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d"),
                "epsEstimate": 0.73,
                "eps": 0.85,
                "surprisePercent": 16.44,
                "revenueEstimate": 24.32e9,
                "revenue": 25.17e9
            }
        ]
    }

# --- Technical Analysis ---
def render_technical_chart(ticker):
    """Interactive Plotly chart with indicators"""
    data = get_historical_data(ticker, st.session_state.chart_period)
    if data is None:
        return
        
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                       vertical_spacing=0.05,
                       row_heights=[0.7, 0.3])
    
    # Price Trace
    fig.add_trace(
        go.Candlestick(
            x=data.index,
            open=data['Open'],
            high=data['High'],
            low=data['Low'],
            close=data['Close'],
            name="Price"
        ), row=1, col=1
    )
    
    # SMAs
    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data['SMA_20'],
            line=dict(color='blue', width=1),
            name="20 SMA"
        ), row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data['SMA_50'],
            line=dict(color='orange', width=1),
            name="50 SMA"
        ), row=1, col=1
    )
    
    # Bollinger Bands
    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data['Upper_BB'],
            line=dict(color='gray', width=1),
            name="Upper BB"
        ), row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data['Lower_BB'],
            line=dict(color='gray', width=1),
            name="Lower BB",
            fill='tonexty'
        ), row=1, col=1
    )
    
    # Volume
    fig.add_trace(
        go.Bar(
            x=data.index,
            y=data['Volume'],
            name="Volume"
        ), row=2, col=1
    )
    
    fig.update_layout(
        height=700,
        xaxis_rangeslider_visible=False,
        hovermode="x unified"
    )
    
    st.plotly_chart(fig, use_container_width=True)

# --- UI Components ---
def render_stock_card(ticker, earnings_data):
    """Interactive stock card with fundamentals"""
    with st.expander(f"{ticker}", expanded=False):
        tab1, tab2, tab3 = st.tabs(["Overview", "Chart", "Fundamentals"])
        
        with tab1:
            cols = st.columns(2)
            with cols[0]:
                st.metric("EPS Surprise", f"{earnings_data.get('surprisePercent', 0):.2f}%")
                st.metric("Revenue", f"${earnings_data.get('revenue', 0)/1e9:.2f}B")
                
            with cols[1]:
                current_price = get_historical_data(ticker, "1d")['Close'].iloc[-1]
                st.metric("Current Price", f"${current_price:,.2f}")
                st.metric("Next Earnings", earnings_data.get('reportDate', 'N/A'))
                
            if st.button("📊 Full Analysis", key=f"analyze_{ticker}"):
                st.session_state.current_ticker = ticker
                
            if st.button("➕ Watchlist", key=f"watch_{ticker}"):
                if ticker not in st.session_state.watchlist:
                    st.session_state.watchlist.append(ticker)
                    st.toast(f"Added {ticker} to watchlist")
        
        with tab2:
            period = st.selectbox(
                "Chart Period",
                ["1mo", "3mo", "6mo", "1y", "2y"],
                key=f"period_{ticker}"
            )
            render_technical_chart(ticker)
        
        with tab3:
            fundamentals = get_fundamentals(ticker)
            if fundamentals:
                cols = st.columns(2)
                with cols[0]:
                    st.metric("P/E Ratio", f"{fundamentals.get('pe_ratio', 'N/A'):.1f}")
                    st.metric("Beta", f"{fundamentals.get('beta', 'N/A'):.2f}")
                with cols[1]:
                    st.metric("Market Cap", f"${fundamentals.get('market_cap', 0)/1e9:.2f}B")
                    st.metric("Div Yield", f"{fundamentals.get('dividend_yield', 0)*100 if fundamentals.get('dividend_yield') else 0:.2f}%")
            else:
                st.warning("Fundamental data unavailable")

# --- Main App ---
def main():
    st.title("📈 AlphaPod Trader Pro")
    st.caption("Institutional-grade trading analytics for retail investors")
    
    # --- Sidebar ---
    with st.sidebar:
        st.header("Controls")
        if st.button("🔄 Refresh Market Data", type="primary"):
            st.cache_data.clear()
            st.session_state.last_refresh = datetime.now()
            st.toast("Data refresh initiated")
            
        st.divider()
        st.metric("Last Refresh", 
                 st.session_state.last_refresh.strftime("%m/%d %H:%M") 
                 if st.session_state.last_refresh else "Never")
        
        st.divider()
        st.header("Watchlist")
        for ticker in st.session_state.watchlist:
            st.write(f"• {ticker}")
    
    # --- Data Loading ---
    with st.spinner("Loading latest market data..."):
        market_data = fetch_market_data()
        st.session_state.last_refresh = market_data["last_updated"]
    
    # --- Main Tabs ---
    tab1, tab2, tab3 = st.tabs(["Earnings Calendar", "Portfolio", "Research"])
    
    with tab1:
        st.header("Upcoming Earnings Plays")
        for play in market_data["earnings"].get("results", [])[:20]:
            render_stock_card(play["ticker"], play)
    
    with tab2:
        st.header("Your Portfolio")
        if not st.session_state.trades.empty:
            edited_df = st.data_editor(
                st.session_state.trades,
                use_container_width=True,
                num_rows="dynamic"
            )
            if st.button("Save Changes"):
                st.session_state.trades = edited_df
                st.success("Portfolio updated")
        else:
            st.info("No trades recorded yet")
    
    with tab3:
        st.header("Stock Research")
        research_ticker = st.text_input("Enter ticker:", "AAPL").upper()
        if research_ticker:
            render_technical_chart(research_ticker)
            fundamentals = get_fundamentals(research_ticker)
            if fundamentals:
                st.json(fundamentals)

if __name__ == "__main__":
    main()
