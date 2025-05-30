import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
import time
import random
from functools import wraps

# Retry decorator with exponential backoff
def retry_with_exponential_backoff(retries=3, initial_delay=1, backoff_factor=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if "Too Many Requests" in str(e) and attempt < retries - 1:
                        time.sleep(delay)
                        delay *= backoff_factor
                        continue
                    raise
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Google Sheets Authentication
@st.cache_data
def get_google_sheet_data():
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    SERVICE_ACCOUNT_INFO = st.secrets["GCP_SERVICE_ACCOUNT"]
    creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key("1TT5xMOWU8MkYTOb5X5jrQ08BQ20cRVogfC77cSCeToQ").sheet1
    df = pd.DataFrame(sheet.get_all_records()).dropna(subset=["Symbol", "Exchange"]).drop_duplicates("Symbol")
    return df

# Exchange suffix mapping and other helper functions remain the same...

@retry_with_exponential_backoff()
@st.cache_data(ttl=3600)
def get_ticker_data(_ticker, exchange, yf_symbol):
    try:
        # Random delay to avoid rate limiting
        time.sleep(random.uniform(0.5, 1.5))
        
        ticker_obj = yf.Ticker(yf_symbol)
        hist = ticker_obj.history(period="6mo")
        if hist.empty or len(hist) < 20:
            return None, None

        # Rest of your existing get_ticker_data function...
        # ... [keep all the existing code] ...
        
    except Exception as e:
        st.error(f"Error processing {_ticker}: {str(e)}")
        return None, None

# Streamlit UI Configuration
st.set_page_config(layout="wide")
st.title("📊 Stock Watchlist Dashboard")

# Load data
df = get_google_sheet_data()

# Filters remain the same...

# Process data with batch delays
results = []
progress_bar = st.progress(0)
status_text = st.empty()

batch_size = 10  # Process 10 at a time
delay_between_batches = 5  # Wait 5 seconds between batches

for i, (_, row) in enumerate(df.iterrows()):
    symbol, exchange = row["Symbol"], row["Exchange"]
    if selected_exchange and exchange not in selected_exchange:
        continue
        
    yf_symbol = map_to_yfinance_symbol(symbol, exchange)
    progress_bar.progress((i + 1) / len(df))
    status_text.text(f"Processing {i+1}/{len(df)}: {symbol} ({exchange})")
    
    ticker_data, history_data = get_ticker_data(symbol, exchange, yf_symbol)
    if ticker_data:
        results.append(ticker_data)
    
    # Add delay after each batch
    if (i + 1) % batch_size == 0:
        time.sleep(delay_between_batches)

# Rest of your Streamlit display code remains the same...
