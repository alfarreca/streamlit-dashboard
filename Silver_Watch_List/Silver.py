import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# Configuration
CACHE_TTL = 3600  # 1 hour cache
ETF_SYMBOLS = {
    "SLV": "iShares Silver Trust",
    "PSLV": "Sprott Physical Silver Trust", 
    "SIL": "Global X Silver Miners ETF",
    "GDX": "VanEck Gold Miners ETF"
}

@st.cache_data(ttl=CACHE_TTL)
def fetch_eodhd_data(api_key, symbol, exchange="US"):
    """Fetch ETF data from EODHD API"""
    base_url = "https://eodhistoricaldata.com/api/real-time/"
    url = f"{base_url}{symbol}.{exchange}"
    
    params = {
        'api_token': api_key,
        'fmt': 'json',
        'filter': 'last_close,high,low,change_p'
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if isinstance(data, dict) and 'code' in data:
            st.error(f"EODHD API Error: {data.get('message', 'Unknown error')}")
            return None
            
        return {
            'symbol': symbol,
            'price': data.get('last_close'),
            'change_pct': data.get('change_p'),
            'high': data.get('high'),
            'low': data.get('low')
        }
        
    except Exception as e:
        st.error(f"Error fetching {symbol} data: {str(e)}")
        return None

def fetch_metal_price(api_key, metal):
    """Fetch metal prices from MetalPriceAPI"""
    url = f"https://api.metalpriceapi.com/v1/latest"
    params = {
        'api_key': api_key,
        'base': 'USD',
        'currencies': metal
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return 1 / float(data['rates'][metal])  # Convert to USD per ounce
    except Exception as e:
        st.error(f"Error fetching {metal} price: {str(e)}")
        return None

def main():
    st.set_page_config(page_title="Precious Metals Dashboard", layout="wide")
    
    # Title
    st.title("💰 Precious Metals & ETFs Dashboard")
    st.markdown("Live prices and performance data updated hourly")
    
    # Initialize API keys
    try:
        metal_key = st.secrets["metalpriceapi"]["key"]
        eod_key = st.secrets["eodhd"]["api_key"]
    except KeyError as e:
        st.error(f"Missing API key in secrets: {str(e)}")
        st.stop()
    
    # Dashboard layout
    tab1, tab2 = st.tabs(["Live Prices", "Historical Trends"])
    
    with tab1:
        st.header("Spot Prices")
        
        # Metals prices
        col1, col2, col3 = st.columns(3)
        with col1:
            silver = fetch_metal_price(metal_key, "XAG")
            st.metric("Silver (XAG/USD)", 
                     f"${silver:.2f}" if silver else "N/A",
                     help="Spot price per ounce")
        
        with col2:
            gold = fetch_metal_price(metal_key, "XAU")
            st.metric("Gold (XAU/USD)", 
                     f"${gold:.2f}" if gold else "N/A",
                     help="Spot price per ounce")
        
        with col3:
            if silver and gold:
                ratio = gold / silver
                st.metric("Gold/Silver Ratio", 
                         f"{ratio:.2f}",
                         help="Historical average: ~70-80")
        
        # ETFs section
        st.header("ETF Performance")
        
        # Fetch all ETF data
        etf_data = []
        with st.spinner("Loading ETF data..."):
            for symbol in ETF_SYMBOLS:
                data = fetch_eodhd_data(eod_key, symbol)
                if data:
                    etf_data.append(data)
        
        # Display ETF metrics
        if etf_data:
            cols = st.columns(len(etf_data))
            for i, etf in enumerate(etf_data):
                with cols[i]:
                    st.metric(
                        label=ETF_SYMBOLS.get(etf['symbol'], etf['symbol']),
                        value=f"${etf['price']:.2f}" if etf['price'] else "N/A",
                        delta=f"{etf['change_pct']:.2f}%" if etf['change_pct'] else None
                    )
                    
                    # Show price in 52-week range
                    if etf['high'] and etf['low']:
                        progress = (etf['price'] - etf['low']) / (etf['high'] - etf['low'])
                        st.progress(min(max(progress, 0), 1))
                        st.caption(f"52W: ${etf['low']:.2f}-${etf['high']:.2f}")
        
    with tab2:
        st.header("Historical Trends")
        st.info("Historical chart functionality coming soon")

if __name__ == "__main__":
    main()
