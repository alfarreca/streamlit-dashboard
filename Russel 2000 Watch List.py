import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
MAX_WORKERS = 8  # Optimal for most systems
REQUEST_DELAY = (0.3, 1.0)  # Reduced delay range
CACHE_TTL = 3600 * 6  # 6 hour cache
PRELOAD_SYMBOLS = 50  # Initial load count

# Google Sheets Authentication
@st.cache_data(ttl=CACHE_TTL)
def get_google_sheet_data():
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    SERVICE_ACCOUNT_INFO = st.secrets["GCP_SERVICE_ACCOUNT"]
    creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key("1TT5xMOWU8MkYTOb5X5jrQ08BQ20cRVogfC77cSCeToQ").sheet1
    df = pd.DataFrame(sheet.get_all_records()).dropna(subset=["Symbol", "Exchange"]).drop_duplicates("Symbol")
    return df

# Exchange suffix mapping (unchanged)
def exchange_suffix(ex: str) -> str:
    suffix_map = {
        "ETR": "DE", "EPA": "PA", "LON": "L", "BIT": "MI", "STO": "ST",
        "SWX": "SW", "TSE": "TO", "ASX": "AX", "HKG": "HK"
    }
    return suffix_map.get(ex.upper(), "")

def map_to_yfinance_symbol(symbol: str, exchange: str) -> str:
    if exchange.upper() in ["NYSE", "NASDAQ"]:
        return symbol
    suffix = exchange_suffix(exchange)
    return f"{symbol}.{suffix}" if suffix else symbol

# Optimized data processing
@st.cache_data(ttl=CACHE_TTL)
def get_ticker_data(_ticker, exchange, yf_symbol):
    try:
        time.sleep(random.uniform(*REQUEST_DELAY))
        ticker_obj = yf.Ticker(yf_symbol)
        hist = ticker_obj.history(period="3mo")  # Reduced from 6mo to 3mo
        
        if hist.empty or len(hist) < 20:
            return None

        close = hist["Close"]
        last_price = close.iloc[-1]
        ma10 = close.rolling(window=10).mean().iloc[-1]
        ma20 = close.rolling(window=20).mean().iloc[-1]
        
        return {
            "Symbol": _ticker,
            "Exchange": exchange,
            "Price": round(last_price, 2),
            "MA10": round(ma10, 2),
            "MA20": round(ma20, 2),
            "YF Symbol": yf_symbol
        }

    except Exception as e:
        return None

# Streamlit UI - Optimized
st.set_page_config(layout="wide")
st.title("📊 Stock Watchlist Dashboard")

# Initial load with minimal data
if 'full_data_loaded' not in st.session_state:
    st.session_state.full_data_loaded = False
    st.session_state.initial_results = []

# Load basic data immediately
df = get_google_sheet_data()

# Display filters immediately
col1, col2 = st.columns(2)
with col1:
    selected_exchange = st.multiselect(
        "Filter by Exchange", 
        options=df["Exchange"].unique(), 
        default=["NASDAQ", "NYSE"]  # Default to most common
    )
with col2:
    min_price, max_price = st.slider(
        "Price Range",
        min_value=0.0,
        max_value=1000.0,
        value=(10.0, 200.0)
    )

# Load initial subset of data
if not st.session_state.initial_results:
    with st.spinner('Loading initial data...'):
        subset = df.head(PRELOAD_SYMBOLS)
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(get_ticker_data, row["Symbol"], row["Exchange"], 
                      map_to_yfinance_symbol(row["Symbol"], row["Exchange"])) 
                      for row in subset.to_dict('records')]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    st.session_state.initial_results.append(result)

# Display initial results immediately
if st.session_state.initial_results:
    initial_df = pd.DataFrame(st.session_state.initial_results)
    st.dataframe(
        initial_df[["Symbol", "Exchange", "Price", "MA10", "MA20"]],
        use_container_width=True,
        height=400
    )

# Load full data on demand
if st.button('Load Full Dataset') and not st.session_state.full_data_loaded:
    with st.spinner('Loading full dataset...'):
        progress_bar = st.progress(0)
        results = []
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(get_ticker_data, row["Symbol"], row["Exchange"], 
                      map_to_yfinance_symbol(row["Symbol"], row["Exchange"])): idx 
                      for idx, row in enumerate(df.to_dict('records'))}
            
            for i, future in enumerate(as_completed(futures)):
                result = future.result()
                if result:
                    results.append(result)
                if i % 20 == 0:
                    progress_bar.progress(min(100, int(i / len(df) * 100)))
        
        st.session_state.full_results = results
        st.session_state.full_data_loaded = True
        progress_bar.empty()

# Display full results when available
if st.session_state.full_data_loaded and 'full_results' in st.session_state:
    full_df = pd.DataFrame(st.session_state.full_results)
    st.dataframe(
        full_df[["Symbol", "Exchange", "Price", "MA10", "MA20"]],
        use_container_width=True,
        height=700
    )

# Lazy-load detailed charts only when requested
selected_symbol = st.selectbox("View details for:", options=df["Symbol"].unique())
if st.button('Show Detailed Chart'):
    with st.spinner(f'Loading {selected_symbol} details...'):
        yf_symbol = map_to_yfinance_symbol(selected_symbol, 
                                          df[df["Symbol"] == selected_symbol]["Exchange"].iloc[0])
        ticker = yf.Ticker(yf_symbol)
        hist = ticker.history(period="3mo")
        
        if not hist.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name='Price'))
            fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'].rolling(10).mean(), name='MA10'))
            fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'].rolling(20).mean(), name='MA20'))
            st.plotly_chart(fig, use_container_width=True)
