import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time

# Configuration
CACHE_TTL = 3600  # 1 hour cache
MAX_RETRIES = 2
RETRY_DELAY = 1

def validate_api_keys():
    """Validate that API keys exist and are properly formatted"""
    errors = []
    
    try:
        metal_api_key = st.secrets["metalpriceapi"]["key"]
        if not metal_api_key or len(metal_api_key) != 32:
            errors.append("MetalPriceAPI key is invalid (should be 32 characters)")
    except KeyError:
        errors.append("MetalPriceAPI key is missing in secrets.toml")

    try:
        td_api_key = st.secrets["twelvedata"]["api_key"]
        if not td_api_key or len(td_api_key) != 24:
            errors.append("TwelveData API key is invalid (should be 24 characters)")
    except KeyError:
        errors.append("TwelveData API key is missing in secrets.toml")

    return errors if errors else None

@st.cache_data(ttl=CACHE_TTL)
def fetch_with_retry(url, params=None, headers=None, retries=MAX_RETRIES):
    """Generic fetch function with retry logic"""
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt == retries - 1:
                raise
            time.sleep(RETRY_DELAY)
    return None

def fetch_metal_price(api_key, metal_code):
    """Fetch gold/silver prices from MetalPriceAPI"""
    url = f"https://api.metalpriceapi.com/v1/latest"
    params = {
        'api_key': api_key,
        'base': 'USD',
        'currencies': metal_code
    }
    
    try:
        data = fetch_with_retry(url, params=params)
        if data and 'rates' in data and metal_code in data['rates']:
            return 1 / float(data['rates'][metal_code])
        st.error(f"Unexpected MetalPriceAPI response format")
        return None
    except Exception as e:
        st.error(f"MetalPriceAPI Error: {str(e)}")
        return None

def fetch_etf_data(api_key, symbol):
    """Fetch ETF/stock data from TwelveData"""
    url = "https://api.twelvedata.com/time_series"
    params = {
        'symbol': symbol,
        'interval': '1day',
        'outputsize': '30',
        'apikey': api_key
    }
    
    try:
        data = fetch_with_retry(url, params=params)
        if not data:
            return None
            
        if 'code' in data and data['code'] == 401:
            st.error("TwelveData API key is invalid or unauthorized")
            return None
            
        if 'values' not in data:
            st.error(f"Unexpected TwelveData response: {data.get('message', 'No price data')}")
            return None
            
        df = pd.DataFrame(data['values'])
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
        
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
        
        return df.iloc[-1]
    except Exception as e:
        st.error(f"TwelveData Error: {str(e)}")
        return None

def get_historical_stats(symbol):
    """Get historical statistics"""
    stats_db = {
        "XAG": {"52w_high": 34.83, "52w_low": 26.65, "1y_ago": 28.15},
        "XAU": {"52w_high": 3430.21, "52w_low": 2292.71, "1y_ago": 2380.50},
        "SLV": {"52w_high": 31.74, "52w_low": 24.33, "1y_ago": 27.91},
        "PSLV": {"52w_high": 11.73, "52w_low": 9.17, "1y_ago": 10.32},
        "SIL": {"52w_high": 43.15, "52w_low": 29.58, "1y_ago": 34.12},
        "GDX": {"52w_high": 51.91, "52w_low": 33.15, "1y_ago": 35.48}
    }
    return stats_db.get(symbol, {})

def main():
    st.set_page_config(page_title="Precious Metals Dashboard", layout="wide")
    
    # Validate API keys before proceeding
    key_errors = validate_api_keys()
    if key_errors:
        st.error("Configuration Errors Detected:")
        for error in key_errors:
            st.error(f"• {error}")
        st.stop()
    
    # Title and description
    st.title("💰 Precious Metals & Miners Dashboard")
    st.markdown("""
    Track live prices and performance of silver, gold, and related ETFs.
    Data updates hourly.
    """)
    
    # Get API keys from secrets
    metal_api_key = st.secrets["metalpriceapi"]["key"]
    td_api_key = st.secrets["twelvedata"]["api_key"]
    
    # Dashboard layout
    tab1, tab2 = st.tabs(["Live Prices", "Historical Analysis"])
    
    with tab1:
        st.header("Live Market Data")
        
        # Commodities row
        col1, col2, col3 = st.columns(3)
        with col1:
            silver_spot = fetch_metal_price(metal_api_key, "XAG")
            if silver_spot is not None:
                st.metric("Silver Spot (XAG/USD)", f"${silver_spot:.2f}")
        
        with col2:
            gold_spot = fetch_metal_price(metal_api_key, "XAU")
            if gold_spot is not None:
                st.metric("Gold Spot (XAU/USD)", f"${gold_spot:.2f}")
        
        with col3:
            if silver_spot and gold_spot:
                ratio = gold_spot / silver_spot
                st.metric("Gold/Silver Ratio", f"{ratio:.2f}", 
                         help="Historical average ~70-80")
        
        # ETFs row
        st.subheader("ETFs & Funds")
        etf_cols = st.columns(4)
        etf_symbols = ["SLV", "PSLV", "SIL", "GDX"]
        
        for i, symbol in enumerate(etf_symbols):
            with etf_cols[i]:
                etf_data = fetch_etf_data(td_api_key, symbol)
                if etf_data is not None:
                    stats = get_historical_stats(symbol)
                    change_pct = ((etf_data['close'] - stats['1y_ago']) / stats['1y_ago']) * 100
                    
                    st.metric(
                        label=symbol,
                        value=f"${etf_data['close']:.2f}",
                        delta=f"{change_pct:.1f}% YoY"
                    )
                    current_progress = (etf_data['close'] - stats['52w_low']) / (stats['52w_high'] - stats['52w_low'])
                    st.progress(min(max(current_progress, 0), 1))  # Clamped between 0 and 1
                else:
                    st.warning(f"Data unavailable for {symbol}")

    with tab2:
        st.header("Historical Performance Analysis")
        st.info("Historical analysis features coming soon!")

if __name__ == "__main__":
    main()
