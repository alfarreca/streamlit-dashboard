import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime, timedelta
import time
import random
import logging
from rich.traceback import install
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.exceptions import RequestException
import pytz
import re
from collections import Counter

# Initialize rich traceback
install(show_locals=True)

# Configuration
MAX_WORKERS = 8
REQUEST_DELAY = (0.8, 2.0)
BATCH_SIZE = 10
CACHE_TTL = 3600 * 4
MAX_RETRIES = 2
RATE_LIMIT_WINDOW = 60
MAX_REQUESTS_PER_MINUTE = 50

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("stock_watchlist.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Rate limit tracking
class RateLimiter:
    def __init__(self):
        self.request_times = []

    def check_rate_limit(self):
        now = time.time()
        self.request_times = [t for t in self.request_times if now - t < RATE_LIMIT_WINDOW]
        if len(self.request_times) >= MAX_REQUESTS_PER_MINUTE:
            wait_time = RATE_LIMIT_WINDOW - (now - self.request_times[0])
            logger.warning(f"Rate limit reached. Waiting {wait_time:.1f} seconds")
            time.sleep(wait_time)
            self.request_times = []

    def add_request(self):
        self.request_times.append(time.time())

rate_limiter = RateLimiter()

# Google Sheets Authentication
@st.cache_data(ttl=CACHE_TTL)
def get_google_sheet_data():
    try:
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        SERVICE_ACCOUNT_INFO = st.secrets["GCP_SERVICE_ACCOUNT"]
        creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key("1TT5xMOWU8MkYTOb5X5jrQ08BQ20cRVogfC77cSCeToQ").sheet1
        df = pd.DataFrame(sheet.get_all_records()).dropna(subset=["Symbol", "Exchange"]).drop_duplicates("Symbol")
        return df
    except Exception as e:
        logger.error(f"Failed to load Google Sheet data: {str(e)}")
        st.error("Failed to load data from Google Sheets. Please check the connection.")
        return pd.DataFrame()

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

def safe_round(value, decimals=2):
    if isinstance(value, str):
        try:
            return round(float(value), decimals)
        except ValueError:
            return value
    elif value is None:
        return None
    return round(value, decimals)

def calculate_crossover(close_series):
    try:
        if len(close_series) < 20:
            return "Insufficient data"
        ma10 = close_series.rolling(window=10).mean()
        ma20 = close_series.rolling(window=20).mean()
        ma10_values = ma10.iloc[-6:].values
        ma20_values = ma20.iloc[-6:].values
        current_relation = "MA10 > MA20" if ma10_values[-1] > ma20_values[-1] else "MA10 ≤ MA20"
        crossover_status = "No Crossover"
        if (ma10_values[-2] <= ma20_values[-2]) and (ma10_values[-1] > ma20_values[-1]):
            crossover_status = "🟢 Golden Cross (Bullish)"
        elif (ma10_values[-2] >= ma20_values[-2]) and (ma10_values[-1] < ma20_values[-1]):
            crossover_status = "🔴 Death Cross (Bearish)"
        else:
            for i in range(1, 6):
                if (ma10_values[-i-1] <= ma20_values[-i-1]) and (ma10_values[-1] > ma20_values[-1]):
                    crossover_status = "🟡 Recent Golden Cross"
                    break
                elif (ma10_values[-i-1] >= ma20_values[-i-1]) and (ma10_values[-1] < ma20_values[-1]):
                    crossover_status = "🟠 Recent Death Cross"
                    break
        return f"{current_relation} | {crossover_status}"
    except Exception as e:
        logger.error(f"Error in calculate_crossover: {str(e)}")
        return f"Error: {str(e)}"

def create_price_chart(symbol, history_data):
    try:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=history_data.index,
            y=history_data['Close'],
            name='Price',
            line=dict(color='#1f77b4')
        ))
        fig.add_trace(go.Scatter(
            x=history_data.index,
            y=history_data['Close'].rolling(window=10).mean(),
            name='MA10',
            line=dict(color='orange', width=1)
        ))
        fig.add_trace(go.Scatter(
            x=history_data.index,
            y=history_data['Close'].rolling(window=20).mean(),
            name='MA20',
            line=dict(color='red', width=1)
        ))
        fig.add_trace(go.Bar(
            x=history_data.index,
            y=history_data['Volume'],
            name='Volume',
            marker_color='rgba(100, 100, 100, 0.3)',
            yaxis='y2'
        ))
        fig.update_layout(
            title=f'{symbol} Price Chart',
            xaxis_title='Date',
            yaxis_title='Price',
            yaxis2=dict(title='Volume', overlaying='y', side='right', showgrid=False),
            hovermode='x unified',
            height=400,
            margin=dict(l=50, r=50, b=50, t=50, pad=4),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        return fig
    except Exception as e:
        logger.error(f"Error creating chart for {symbol}: {str(e)}")
        return None

@st.cache_data(ttl=CACHE_TTL)
def get_ticker_data(_ticker, exchange, yf_symbol, attempt=0):
    try:
        rate_limiter.check_rate_limit()
        time.sleep(random.uniform(*REQUEST_DELAY))
        ticker_obj = yf.Ticker(yf_symbol)
        try:
            hist = ticker_obj.history(period="6mo")
            if hist.empty or len(hist) < 20:
                error_msg = "Insufficient historical data (less than 20 days)"
                logger.warning(f"{_ticker} ({yf_symbol}): {error_msg}")
                return None, error_msg
            last_data_date = hist.index[-1].to_pydatetime()
            if last_data_date.tzinfo is not None:
                now = datetime.now(pytz.UTC)
                last_data_date = last_data_date.astimezone(pytz.UTC)
            else:
                now = datetime.now()
            if (now - last_data_date).days > 7:
                error_msg = f"Stale data (last update: {last_data_date})"
                logger.warning(f"{_ticker} ({yf_symbol}): {error_msg}")
                return None, error_msg
        except (RequestException, ValueError) as e:
            if attempt < MAX_RETRIES:
                logger.info(f"Retrying {_ticker} (attempt {attempt + 1})")
                return get_ticker_data(_ticker, exchange, yf_symbol, attempt + 1)
            error_msg = f"Failed to fetch history: {str(e)}"
            logger.error(f"{_ticker}: {error_msg}")
            return None, error_msg

        close = hist["Close"]
        volume = hist["Volume"]
        last_price = close.iloc[-1]

        try:
            ma10 = close.rolling(window=10, min_periods=5).mean().iloc[-1]
            ma20 = close.rolling(window=20, min_periods=10).mean().iloc[-1]
            volume_ma10 = volume.rolling(window=10, min_periods=5).mean().iloc[-1]
            change_5d = ((last_price - close.iloc[-5]) / close.iloc[-5] * 100) if len(close) >= 5 else None
            divergence = (last_price - ma10) / ma10 * 100
            signal = "🟢 Buy" if (last_price > ma10 and ma10 > ma20) else "🔴 Sell" if (last_price < ma10 and ma10 < ma20) else "🟡 Neutral"
            crossover = calculate_crossover(close)
            ticker_info = ticker_obj.info

            def safe_metric(value, scale=1, default=None):
                try:
                    if value is None:
                        return default
                    return safe_round(float(value) / scale)
                except (TypeError, ValueError):
                    return default

            dividend_yield = safe_metric(ticker_info.get("dividendYield"), scale=100, default=0)
            dividend_payout_ratio = safe_metric(ticker_info.get("payoutRatio"), scale=1, default=0)
            free_cash_flow = safe_metric(ticker_info.get("freeCashflow"), scale=1e6)
            pe_ratio = safe_metric(ticker_info.get("trailingPE"))
            market_cap = safe_metric(ticker_info.get("marketCap"), scale=1e6)
            chart = create_price_chart(_ticker, hist)
            if chart is None:
                error_msg = "Failed to create chart"
                return None, error_msg

            rate_limiter.add_request()

            return {
                "Symbol": _ticker,
                "Exchange": exchange,
                "Price": safe_round(last_price, 2),
                "5D Change %": safe_round(change_5d, 2),
                "MA10": safe_round(ma10, 2),
                "MA20": safe_round(ma20, 2),
                "Divergence": safe_round(divergence, 2),
                "% vs MA10": f"{safe_round(divergence, 2)}%",
                "Volume": int(volume.iloc[-1]),
                "Vol MA10": int(volume_ma10),
                "Signal": signal,
                "Crossover": crossover,
                "P/E Ratio": pe_ratio,
                "Dividend Yield": dividend_yield,
                "Dividend Payout Ratio (%)": dividend_payout_ratio,
                "Free Cash Flow (LC m)": free_cash_flow,
                "Market Cap (m)": market_cap,
                "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "YF Symbol": yf_symbol,
                "Chart": chart,
                "Data Quality": "🟢 Good" if (now - last_data_date).days <= 1 else "🟡 Stale" if (now - last_data_date).days <= 3 else "🔴 Old"
            }, None

        except Exception as e:
            error_msg = f"Error calculating metrics: {str(e)}"
            logger.error(f"{_ticker}: {error_msg}")
            return None, error_msg

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"{_ticker}: {error_msg}")
        return None, error_msg

def process_ticker(row, selected_exchange):
    try:
        symbol = row.Symbol
        exchange = row.Exchange
        if selected_exchange and exchange not in selected_exchange:
            return None, "Filtered by user exchange selection"
        yf_symbol = map_to_yfinance_symbol(symbol, exchange)
        if not yf_symbol or len(yf_symbol) > 10 or not yf_symbol[0].isalpha():
            error_msg = f"Invalid symbol format: {symbol} ({exchange})"
            logger.warning(error_msg)
            return None, error_msg
        return get_ticker_data(symbol, exchange, yf_symbol)
    except Exception as e:
        error_msg = f"Error in process_ticker: {str(e)}"
        logger.error(f"{getattr(row, 'Symbol', 'unknown')}: {error_msg}")
        return None, error_msg

# Streamlit UI Configuration
st.set_page_config(layout="wide", page_title="Stock Watchlist Dashboard")
st.title("📊 Stock Watchlist Dashboard (Enhanced)")

# Initialize session state
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'stop_processing' not in st.session_state:
    st.session_state.stop_processing = False
if 'results' not in st.session_state:
    st.session_state.results = []
if 'error_details' not in st.session_state:
    st.session_state.error_details = []
if 'error_reasons' not in st.session_state:
    st.session_state.error_reasons = []

# Dark mode toggle
dark_mode = st.sidebar.checkbox("Dark Mode", value=False)
if dark_mode:
    st.markdown("""
        <style>
            .stApp {
                background-color: #1E1E1E;
                color: white;
            }
            .css-1aumxhk {
                background-color: #1E1E1E;
            }
        </style>
    """, unsafe_allow_html=True)

# Load data
df = get_google_sheet_data()

# Defensive: Check required columns
required_columns = {"Symbol", "Exchange"}
if not required_columns.issubset(df.columns):
    st.error("The Google Sheet must contain columns: 'Symbol' and 'Exchange'.")
    st.stop()

# Filters
col1, col2, col3 = st.columns(3)
with col1:
    selected_exchange = st.multiselect(
        "Filter by Exchange", 
        options=df["Exchange"].unique(), 
        default=df["Exchange"].unique()
    )
with col2:
    signal_filter = st.multiselect(
        "Filter by Signal",
        options=["🟢 Buy", "🔴 Sell", "🟡 Neutral"],
        default=["🟢 Buy", "🔴 Sell", "🟡 Neutral"]
    )
with col3:
    crossover_filter = st.multiselect(
        "Filter by Crossover",
        options=["Golden Cross", "Death Cross", "Recent Golden Cross", "Recent Death Cross"],
        default=["Golden Cross", "Death Cross"]
    )

# Process data with threading
def process_data():
    st.session_state.processing = True
    st.session_state.stop_processing = False
    st.session_state.results = []
    st.session_state.error_details = []
    st.session_state.error_reasons = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    processed_count = 0
    error_count = 0

    filtered_df = df[df["Exchange"].isin(selected_exchange)] if selected_exchange else df

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_ticker, row, selected_exchange): idx 
            for idx, row in enumerate(filtered_df.itertuples())
        }
        for future in as_completed(futures):
            if st.session_state.stop_processing:
                executor.shutdown(wait=False)
                break
            idx = futures[future]
            try:
                ticker_data, error_reason = future.result()
                if ticker_data:
                    st.session_state.results.append(ticker_data)
                else:
                    error_count += 1
                    reason = error_reason or "Unknown error"
                    st.session_state.error_details.append(f"Row {idx}: {reason}")
                    st.session_state.error_reasons.append(reason)
            except Exception as e:
                error_count += 1
                st.session_state.error_details.append(f"Row {idx}: Exception: {str(e)}")
                st.session_state.error_reasons.append(str(e))
            processed_count += 1
            progress_percent = min(100, int(processed_count / len(filtered_df) * 100))
            progress_bar.progress(progress_percent)
            status_text.text(
                f"Processed {processed_count}/{len(filtered_df)} tickers | "
                f"Success: {len(st.session_state.results)} | Errors: {error_count}"
            )

    progress_bar.progress(100)
    if st.session_state.stop_processing:
        status_text.text(f"Processing stopped by user. Completed {len(st.session_state.results)} tickers")
    else:
        status_text.text(f"Completed processing {len(st.session_state.results)} tickers ({(len(st.session_state.results)/len(filtered_df)*100):.1f}% success rate)")
    st.session_state.processing = False

# Start/Stop buttons
col1, col2 = st.columns(2)
with col1:
    if st.button("Start Processing", type="primary", disabled=st.session_state.processing):
        process_data()
with col2:
    if st.button("Stop Processing", disabled=not st.session_state.processing):
        st.session_state.stop_processing = True
        st.warning("Stopping processing... Please wait")

# Display results if available
if st.session_state.results:
    results_df = pd.DataFrame(st.session_state.results)
    pattern = "|".join([re.escape(c) for c in crossover_filter])
    results_df = results_df[
        results_df["Signal"].isin(signal_filter) &
        results_df["Crossover"].str.contains(pattern, case=False, na=False)
    ]
    sort_options = {
        "5D Change (High to Low)": ("5D Change %", False),
        "Divergence (High to Low)": ("Divergence", False),
        "Price (High to Low)": ("Price", False),
        "P/E Ratio (Low to High)": ("P/E Ratio", True),
        "Dividend Yield (High to Low)": ("Dividend Yield", False),
        "Market Cap (High to Low)": ("Market Cap (m)", False),
        "Data Quality": ("Data Quality", True)
    }
    sort_col, _, _ = st.columns(3)
    with sort_col:
        sort_option = st.selectbox("Sort by", options=list(sort_options.keys()))
    sort_column, ascending = sort_options[sort_option]
    results_df = results_df.sort_values(by=sort_column, ascending=ascending, na_position='last')
    display_columns = [col for col in results_df.columns if col not in ["Chart", "YF Symbol", "Divergence"]]
    st.dataframe(
        results_df[display_columns],
        use_container_width=True,
        height=700,
        column_config={
            "Price": st.column_config.NumberColumn(format="$%.2f"),
            "5D Change %": st.column_config.NumberColumn(format="%.2f%%"),
            "Dividend Yield": st.column_config.NumberColumn(format="%.4f"),
            "P/E Ratio": st.column_config.NumberColumn(format="%.2f"),
            "Dividend Payout Ratio (%)": st.column_config.NumberColumn(format="%.2f%%"),
            "Free Cash Flow (LC m)": st.column_config.NumberColumn(format="$%.2f"),
            "Market Cap (m)": st.column_config.NumberColumn(format="$%.2f"),
            "Data Quality": st.column_config.TextColumn()
        }
    )
    selected_symbols = st.multiselect(
        "Select stocks to view charts:",
        options=results_df["Symbol"].unique()
    )
    for symbol in selected_symbols:
        ticker_data = next((item for item in st.session_state.results if item["Symbol"] == symbol), None)
        if ticker_data and "Chart" in ticker_data:
            st.plotly_chart(ticker_data["Chart"], use_container_width=True)
    st.download_button(
        label="Download Data as CSV",
        data=results_df.drop(columns=["Chart"]).to_csv(index=False),
        file_name="stock_metrics.csv",
        mime="text/csv"
    )
    # Show error reason summary
    if st.session_state.error_reasons:
        st.subheader("Summary of Failure Reasons")
        err_counter = Counter(st.session_state.error_reasons)
        for reason, count in err_counter.most_common():
            st.write(f"{reason}: {count} tickers")

    if st.session_state.error_details:
        with st.expander("View Error Details"):
            st.write("The following errors occurred during processing:")
            for error in st.session_state.error_details:
                st.write(f"- {error}")

elif st.session_state.processing:
    st.warning("Processing in progress...")
else:
    st.info("Click 'Start Processing' to begin analyzing stocks")

# Add footer with last update time
st.sidebar.markdown(f"""
---
**Last Updated**: {datetime.now().strftime("%Y-%m-%d %H:%M")}  
**Version**: 2.2  
**Data Source**: Yahoo Finance  
**Note**: This tool is for informational purposes only.
""")
