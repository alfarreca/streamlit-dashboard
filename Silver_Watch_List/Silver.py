import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import pytz

# Configuration
CACHE_TTL = 3600  # 1 hour cache

@st.cache_data(ttl=CACHE_TTL)
def fetch_metal_price(api_key, metal_code):
    """Fetch gold/silver prices from MetalPriceAPI"""
    url = f"https://api.metalpriceapi.com/v1/latest?api_key={api_key}&base=USD&currencies={metal_code}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return 1 / float(data['rates'][metal_code])  # Convert to USD per ounce
    except Exception as e:
        st.error(f"Error fetching metal price: {str(e)}")
        return None

@st.cache_data(ttl=CACHE_TTL)
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
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if 'values' not in data:
            error_msg = data.get('message', 'Unknown error')
            if 'API key' in error_msg:
                st.error("TwelveData API key is invalid. Please check your secrets.toml file.")
            return None
            
        df = pd.DataFrame(data['values'])
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
        
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
        
        return df.iloc[-1]  # Return most recent data point
        
    except Exception as e:
        st.error(f"Error fetching ETF data: {str(e)}")
        return None

def get_historical_stats(symbol):
    """Get historical statistics (simplified - would use API in production)"""
    stats_db = {
        "XAGUSD": {"52w_high": 34.83, "52w_low": 26.65, "1y_ago": 28.15},
        "XAUUSD": {"52w_high": 3430.21, "52w_low": 2292.71, "1y_ago": 2380.50},
        "SLV": {"52w_high": 31.74, "52w_low": 24.33, "1y_ago": 27.91},
        "PSLV": {"52w_high": 11.73, "52w_low": 9.17, "1y_ago": 10.32},
        "SIL": {"52w_high": 43.15, "52w_low": 29.58, "1y_ago": 34.12},
        "GDX": {"52w_high": 51.91, "52w_low": 33.15, "1y_ago": 35.48},
        "WPM": {"52w_high": 86.75, "52w_low": 52.04, "1y_ago": 55.07},
        "AG": {"52w_high": 7.94, "52w_low": 4.62, "1y_ago": 7.08},
        "PAAS": {"52w_high": 28.02, "52w_low": 18.58, "1y_ago": 21.75},
        "HL": {"52w_high": 7.53, "52w_low": 4.54, "1y_ago": 5.84}
    }
    return stats_db.get(symbol, {})

def main():
    st.set_page_config(page_title="Precious Metals Dashboard", layout="wide")
    
    # Title and description
    st.title("💰 Precious Metals & Miners Dashboard")
    st.markdown("""
    Track live prices and performance of silver, gold, and related ETFs/mining stocks.
    Data updates hourly.
    """)
    
    # Initialize secrets with error handling
    try:
        metal_api_key = st.secrets["metalpriceapi"]["key"]
        td_api_key = st.secrets["twelvedata"]["api_key"]  # Changed from "key" to "api_key"
    except KeyError as e:
        st.error(f"Missing API key in secrets: {str(e)}")
        st.error("Please ensure your secrets.toml file is properly configured")
        st.stop()
    except Exception as e:
        st.error(f"Error loading API keys: {str(e)}")
        st.stop()
    
    # Dashboard layout
    tab1, tab2 = st.tabs(["Live Prices", "Historical Analysis"])
    
    with tab1:
        st.header("Live Market Data")
        
        # Commodities row
        col1, col2, col3 = st.columns(3)
        with col1:
            silver_spot = fetch_metal_price(metal_api_key, "XAG")
            if silver_spot:
                st.metric("Silver Spot (XAG/USD)", f"${silver_spot:.2f}")
        
        with col2:
            gold_spot = fetch_metal_price(metal_api_key, "XAU")
            if gold_spot:
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
                    st.progress((etf_data['close'] - stats['52w_low']) / (stats['52w_high'] - stats['52w_low']))
                else:
                    st.warning(f"Could not load data for {symbol}")
    
    with tab2:
        st.header("Historical Performance Analysis")
        st.write("Historical charts and analysis coming soon")

if __name__ == "__main__":
    main()
