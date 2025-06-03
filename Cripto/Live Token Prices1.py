import streamlit as st
import pandas as pd
import yfinance as yf
import time
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import requests
from bs4 import BeautifulSoup
from pytz import timezone
import numpy as np

# Configure page
st.set_page_config(
    page_title="Multi-Source Crypto Dashboard",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
<style>
    .main {
        background-color: #0E1117;
    }
    .data-source-tag {
        font-size: 0.8rem;
        padding: 2px 6px;
        border-radius: 4px;
        background: #333;
        color: white;
    }
    .coingecko-tag {
        background: #8CC63F;
    }
    .yahoo-tag {
        background: #720E9E;
    }
</style>
""", unsafe_allow_html=True)

# Constants
TIMEZONE = timezone('UTC')
REFRESH_INTERVAL = 300
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

# Initialize session state for API source tracking
if 'data_sources' not in st.session_state:
    st.session_state.data_sources = {}

@st.cache_data(ttl=REFRESH_INTERVAL, show_spinner=False)
def get_coingecko_data(ticker_id):
    """Fetch data from CoinGecko API"""
    try:
        # First get the current price
        price_url = f"{COINGECKO_API_URL}/simple/price?ids={ticker_id}&vs_currencies=usd&include_24hr_change=true"
        price_response = requests.get(price_url, timeout=10)
        price_data = price_response.json().get(ticker_id, {})
        
        if not price_data:
            return None, None, None, None
        
        current_price = price_data.get('usd')
        daily_change = price_data.get('usd_24h_change', 0)
        
        # Then get historical data for the weekly change
        hist_url = f"{COINGECKO_API_URL}/coins/{ticker_id}/market_chart?vs_currency=usd&days=7"
        hist_response = requests.get(hist_url, timeout=10)
        hist_data = hist_response.json()
        
        if not hist_data.get('prices'):
            return current_price, daily_change, 0, None
        
        prices = [p[1] for p in hist_data['prices']]
        weekly_change = ((prices[-1] - prices[0]) / prices[0]) * 100 if prices[0] else 0
        
        # Create a pandas DataFrame similar to Yahoo Finance format
        hist_df = pd.DataFrame({
            'Date': [datetime.fromtimestamp(p[0]/1000) for p in hist_data['prices']],
            'Close': [p[1] for p in hist_data['prices']],
            'Volume': [v[1] for v in hist_data['total_volumes']]
        }).set_index('Date')
        
        return current_price, daily_change, weekly_change, hist_df
    
    except Exception as e:
        st.error(f"CoinGecko API error for {ticker_id}: {str(e)}")
        return None, None, None, None

@st.cache_data(ttl=REFRESH_INTERVAL, show_spinner=False)
def get_yahoo_crypto_data(ticker):
    """Fetch comprehensive crypto data from Yahoo Finance with enhanced caching"""
    try:
        base_ticker = ticker.split('.')[0].split('-')[0].upper()
        yahoo_ticker = f"{base_ticker}-USD"
        
        data = yf.Ticker(yahoo_ticker)
        hist = data.history(period="7d", interval="1d")
        
        if hist.empty:
            return None, None, None, None
        
        current_price = hist['Close'].iloc[-1]
        prev_price = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        week_ago_price = hist['Close'].iloc[0] if len(hist) > 1 else current_price
        
        daily_change = ((current_price - prev_price) / prev_price) * 100 if prev_price else 0
        weekly_change = ((current_price - week_ago_price) / week_ago_price) * 100 if week_ago_price else 0
        
        return current_price, daily_change, weekly_change, hist
    
    except Exception as e:
        st.error(f"Yahoo Finance error for {ticker}: {str(e)}")
        return None, None, None, None

def get_crypto_data(ticker, symbol):
    """Determine which API to use based on the token"""
    # Special cases where we prefer CoinGecko
    coingecko_mapping = {
        "UNI": "uniswap",
        "MPL": "maple"
    }
    
    if symbol in coingecko_mapping:
        st.session_state.data_sources[symbol] = "CoinGecko"
        return get_coingecko_data(coingecko_mapping[symbol])
    else:
        st.session_state.data_sources[symbol] = "Yahoo Finance"
        return get_yahoo_crypto_data(ticker)

def main():
    st.title("🌐 Multi-Source Crypto Dashboard")
    st.markdown("---")
    
    # Sidebar configuration
    with st.sidebar:
        st.header("Data Sources")
        st.info("""
        - UNI and MPL: CoinGecko API
        - Others: Yahoo Finance
        """)
        st.markdown("---")
        st.header("Configuration")
        auto_refresh = st.checkbox("Enable auto-refresh", value=True)
    
    # Crypto data configuration
    crypto_data = [
        {"Token ID": "UNI-USD", "Symbol": "UNI", "Project": "Uniswap"},
        {"Token ID": "AAVE-USD", "Symbol": "AAVE", "Project": "Aave"},
        {"Token ID": "DYDX", "Symbol": "DYDX", "Project": "dYdX"},
        {"Token ID": "CRV", "Symbol": "CRV", "Project": "Curve Finance"},
        {"Token ID": "ONDO", "Symbol": "ONDO", "Project": "Ondo Finance"},
        {"Token ID": "MPL", "Symbol": "MPL", "Project": "Maple Finance"},
        {"Token ID": "CFG", "Symbol": "CFG", "Project": "Centrifuge"},
        {"Token ID": "POLYX", "Symbol": "POLYX", "Project": "Polymesh"},
    ]
    
    df = pd.DataFrame(crypto_data)
    
    # Initialize columns
    for col in ["Price", "24h Change", "7d Trend", "Volume", "Source"]:
        if col not in df.columns:
            df[col] = np.nan
    
    # Fetch data
    with st.spinner("Loading multi-source market data..."):
        progress_bar = st.progress(0)
        
        for i, row in df.iterrows():
            ticker = row['Token ID']
            symbol = row['Symbol']
            
            price, daily_change, weekly_change, hist = get_crypto_data(ticker, symbol)
            
            if price is not None:
                df.at[i, 'Price'] = price
                df.at[i, '24h Change'] = daily_change
                df.at[i, '7d Trend'] = weekly_change
                df.at[i, 'Volume'] = hist['Volume'].iloc[-1] if hist is not None and 'Volume' in hist.columns else 0
                df.at[i, 'Source'] = st.session_state.data_sources.get(symbol, "Unknown")
            
            progress_bar.progress((i + 1) / len(df))
    
    # Display data with source tags
    def format_source(source):
        if source == "CoinGecko":
            return '<span class="data-source-tag coingecko-tag">CoinGecko</span>'
        else:
            return '<span class="data-source-tag yahoo-tag">Yahoo</span>'
    
    st.dataframe(
        df.style.format({
            "Price": "${:.4f}",
            "24h Change": "{:.2f}%",
            "7d Trend": "{:.2f}%",
            "Volume": "{:,.0f}",
            "Source": format_source
        }).applymap(
            lambda x: "color: #00D1B2" if isinstance(x, (int, float)) and x >= 0 else "color: #FF4B4B", 
            subset=["24h Change", "7d Trend"]
        ),
        use_container_width=True,
        height=500,
        column_config={
            "Source": st.column_config.TextColumn("Data Source")
        }
    )
    
    # Visualization section
    st.markdown("---")
    st.subheader("Multi-Source Performance")
    
    tab1, tab2 = st.tabs(["Price Comparison", "Source Distribution"])
    
    with tab1:
        fig = px.bar(
            df.sort_values('24h Change', ascending=False),
            x='Symbol',
            y='24h Change',
            color='Source',
            color_discrete_map={
                "CoinGecko": "#8CC63F",
                "Yahoo Finance": "#720E9E"
            },
            title="24h Price Change by Data Source"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        source_counts = df['Source'].value_counts().reset_index()
        fig = px.pie(
            source_counts,
            names='Source',
            values='count',
            color='Source',
            color_discrete_map={
                "CoinGecko": "#8CC63F",
                "Yahoo Finance": "#720E9E"
            },
            title="Data Source Distribution"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Auto-refresh logic
    if auto_refresh:
        time.sleep(REFRESH_INTERVAL)
        st.rerun()

if __name__ == "__main__":
    main()
