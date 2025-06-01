import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime, timedelta
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_exponential

# ========== CONFIGURATION ==========
MAX_WORKERS = 6
REQUEST_DELAY = (0.5, 2.0)
CACHE_TTL = 3600 * 12
PRELOAD_SYMBOLS = 50
MAX_RETRIES = 3
BATCH_SIZE = 300

# ========== SETUP ==========
yf.set_tz_cache_location("cache")

# ========== RETRY MECHANISM ==========
@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
def safe_yfinance_fetch(ticker, period="3mo"):
    time.sleep(random.uniform(*REQUEST_DELAY))
    return ticker.history(period=period)

# ========== DATA FETCHING ==========
@st.cache_data(ttl=CACHE_TTL)
def get_google_sheet_data():
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    SERVICE_ACCOUNT_INFO = st.secrets["GCP_SERVICE_ACCOUNT"]
    creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key("1TT5xMOWU8MkYTOb5X5jrQ08BQ20cRVogfC77cSCeToQ").sheet1
    df = pd.DataFrame(sheet.get_all_records()).dropna(subset=["Symbol", "Exchange"]).drop_duplicates("Symbol")
    return df

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

# ========== EVENT ANALYSIS ==========
def get_events_data(ticker_obj):
    """Get upcoming earnings date using get_earnings_dates()."""
    try:
        df = ticker_obj.get_earnings_dates(limit=2)
        if not df.empty:
            # The index is DatetimeIndex, filter for future earnings
            future_dates = df[df.index >= pd.Timestamp.now()].index.tolist()
            return [pd.to_datetime(date) for date in future_dates]
    except Exception as e:
        st.warning(f"Error fetching earnings dates: {str(e)}")
    return []

# ========== TECHNICAL INDICATORS ==========
def calculate_momentum(hist):
    close = hist['Close']
    high = hist['High']
    low = hist['Low']
    volume = hist['Volume']
    
    # Moving Averages
    ema20 = close.ewm(span=20).mean().iloc[-1]
    ema50 = close.ewm(span=50).mean().iloc[-1]
    ema200 = close.ewm(span=200).mean().iloc[-1]
    
    # RSI
    delta = close.diff()
    gain = delta

