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
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configuration
MAX_WORKERS = 6  # Conservative number to avoid rate limits
REQUEST_DELAY = (0.5, 2.0)  # Wider delay range for safety
CACHE_TTL = 3600 * 12  # 12 hour cache
PRELOAD_SYMBOLS = 30  # Initial load count
MAX_RETRIES = 3  # Max retries for rate-limited requests

# Configure yfinance timeout
yf.set_tz_cache_location("cache")
yf.pdr_override()

# Retry decorator for rate limits
@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(yf.YFRateLimitError)
)
def safe_yfinance_fetch(ticker, period="3mo"):
    time.sleep(random.uniform(*REQUEST_DELAY))
    return ticker.history(period=period)

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

# Exchange suffix mapping
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

# Optimized data processing with robust error handling
@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_ticker_data(_ticker, exchange, yf_symbol):
    try:
        ticker_obj = yf.Ticker(yf_symbol)
        
        try:
            hist = safe_yfinance_fetch(ticker_obj)
        except yf.YFRateLimitError:
            st.warning(f"Rate limit reached for {_ticker}, skipping...")
            return None
        except Exception as e:
            st.warning(f"Error fetching {_ticker}: {str(e)}")
            return None
            
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
            "YF Symbol": yf_symbol,
            "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M")
        }

    except Exception as e:
        st.warning(f"Error processing {_ticker}: {str(e)}")
        return None

# Streamlit UI
st.set_page_config(layout="wide", page_title="Russell 2000 Watch List")
st.title("📊 Russell 2000 Watch List")

# Initialize session state
if 'full_data_loaded' not in st.session_state:
    st.session_state.full_data_loaded = False
    st.session_state.initial_results = []
    st.session_state.last_full_load = None

# Load basic data immediately
df = get_google_sheet_data()

# Display filters
col1, col2 = st.columns(2)
with col1:
    selected_exchange = st.multiselect(
        "Filter by Exchange", 
        options=df["Exchange"].unique(), 
        default=["NASDAQ", "NYSE"]
    )
with col2:
    price_range = st.slider(
        "Price Range ($)",
        min_value=0.0,
        max_value=1000.0,
        value=(10.0, 200.0),
        step=5.0
    )

# Load initial subset of data
if not st.session_state.initial_results:
    with st.spinner('Loading initial data (30 symbols)...'):
        subset = df.head(PRELOAD_SYMBOLS)
        with ThreadPoolExecutor(max_workers=3) as executor:  # Fewer workers for initial load
            futures = [executor.submit(get_ticker_data, row["Symbol"], row["Exchange"], 
                      map_to_yfinance_symbol(row["Symbol"], row["Exchange"])) 
                      for row in subset.to_dict('records')]
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    st.session_state.initial_results.append(result)

# Display initial results
if st.session_state.initial_results:
    initial_df = pd.DataFrame(st.session_state.initial_results)
    st.dataframe(
        initial_df[["Symbol", "Exchange", "Price", "MA10", "MA20", "Last Updated"]],
        use_container_width=True,
        height=400
    )

# Load full data with careful rate limiting
if st.button('Load Full Dataset (500+ Symbols)'):
    if (st.session_state.last_full_load and 
        (datetime.now() - st.session_state.last_full_load) < timedelta(hours=1)):
        st.warning("Full dataset was loaded less than 1 hour ago. Please wait before reloading.")
    else:
        with st.spinner('Loading full dataset (this may take 5-10 minutes)...'):
            progress_bar = st.progress(0)
            status_text = st.empty()
            results = []
            
            filtered_df = df[df["Exchange"].isin(selected_exchange)]
            
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {executor.submit(get_ticker_data, row["Symbol"], row["Exchange"], 
                          map_to_yfinance_symbol(row["Symbol"], row["Exchange"])): idx 
                          for idx, row in enumerate(filtered_df.to_dict('records'))}
                
                for i, future in enumerate(as_completed(futures)):
                    try:
                        result = future.result()
                        if result:
                            results.append(result)
                    except Exception as e:
                        st.warning(f"Error processing future: {str(e)}")
                    
                    if i % 10 == 0:
                        progress = min(100, int((i+1) / len(futures) * 100)
                        progress_bar.progress(progress)
                        status_text.text(f"Processed {i+1}/{len(futures)} symbols")
                        time.sleep(0.1)  # Small delay to prevent UI freeze
            
            st.session_state.full_results = results
            st.session_state.full_data_loaded = True
            st.session_state.last_full_load = datetime.now()
            progress_bar.empty()
            status_text.empty()
            st.success("Full dataset loaded successfully!")

# Display full results when available
if st.session_state.full_data_loaded and 'full_results' in st.session_state:
    full_df = pd.DataFrame(st.session_state.full_results)
    st.dataframe(
        full_df[["Symbol", "Exchange", "Price", "MA10", "MA20", "Last Updated"]],
        use_container_width=True,
        height=700
    )

# Chart viewing with independent loading
st.subheader("Detailed Chart View")
selected_symbol = st.selectbox("Select symbol:", options=df["Symbol"].unique())

if st.button('Load Chart'):
    with st.spinner(f'Loading {selected_symbol} chart...'):
        try:
            exchange = df[df["Symbol"] == selected_symbol]["Exchange"].iloc[0]
            yf_symbol = map_to_yfinance_symbol(selected_symbol, exchange)
            ticker = yf.Ticker(yf_symbol)
            
            try:
                hist = safe_yfinance_fetch(ticker, "6mo")
                
                if not hist.empty:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=hist.index, 
                        y=hist['Close'], 
                        name='Price',
                        line=dict(color='#1f77b4')
                    ))
                    fig.add_trace(go.Scatter(
                        x=hist.index,
                        y=hist['Close'].rolling(10).mean(),
                        name='MA10',
                        line=dict(color='orange', width=1)
                    ))
                    fig.add_trace(go.Scatter(
                        x=hist.index,
                        y=hist['Close'].rolling(20).mean(),
                        name='MA20',
                        line=dict(color='red', width=1)
                    ))
                    fig.update_layout(
                        title=f'{selected_symbol} Price Chart (6 Months)',
                        xaxis_title='Date',
                        yaxis_title='Price',
                        height=500
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("No historical data available for this symbol")
                    
            except yf.YFRateLimitError:
                st.error("Chart loading failed due to rate limits. Please try again later.")
            except Exception as e:
                st.error(f"Error loading chart: {str(e)}")
                
        except Exception as e:
            st.error(f"Error: {str(e)}")

# Add cache management
if st.checkbox("Show cache management options"):
    if st.button("Clear all caches"):
        st.cache_data.clear()
        st.session_state.clear()
        st.rerun()
    st.write(f"Last full load: {st.session_state.last_full_load}")
