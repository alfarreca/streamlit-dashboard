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
import pytz
import numpy as np

# ========== CONFIGURATION ==========
MAX_WORKERS = 8
REQUEST_DELAY = (0.5, 2.0)
CACHE_TTL = 3600 * 12  # 12 hours
PRELOAD_SYMBOLS = 100
BATCH_SIZE = 300
MAX_RETRIES = 3
TIMEZONE = 'America/New_York'

# ========== SETUP ==========
yf.set_tz_cache_location("cache")

# ========== RETRY MECHANISM ==========
@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
def safe_yfinance_fetch(ticker, period="3mo"):
    """Fetch historical data with retry logic and random delay"""
    time.sleep(random.uniform(*REQUEST_DELAY))
    return ticker.history(period=period)

# ========== DATA FETCHING ==========
@st.cache_data(ttl=CACHE_TTL)
def get_google_sheet_data():
    """Fetch stock symbols from Google Sheets"""
    try:
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        SERVICE_ACCOUNT_INFO = st.secrets["GCP_SERVICE_ACCOUNT"]
        creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key("1sNYUiP4Pl8GVYQ1S7Ltc4ETv-ctOA1RVCdYkMb5xjjg").sheet1
        df = pd.DataFrame(sheet.get_all_records()).dropna(subset=["Symbol", "Exchange"]).drop_duplicates("Symbol")
        return df
    except Exception as e:
        st.error(f"Failed to load Google Sheet data: {str(e)}")
        return pd.DataFrame(columns=["Symbol", "Exchange"])

def exchange_suffix(ex: str) -> str:
    """Map exchange codes to Yahoo Finance suffixes"""
    suffix_map = {
        "ETR": "DE", "EPA": "PA", "LON": "L", "BIT": "MI", "STO": "ST",
        "SWX": "SW", "TSE": "TO", "ASX": "AX", "HKG": "HK"
    }
    return suffix_map.get(ex.upper(), "")

def map_to_yfinance_symbol(symbol: str, exchange: str) -> str:
    """Convert symbol to Yahoo Finance format"""
    if exchange.upper() in ["NYSE", "NASDAQ"]:
        return symbol
    suffix = exchange_suffix(exchange)
    return f"{symbol}.{suffix}" if suffix else symbol

# ========== TECHNICAL INDICATORS ==========
# ... [No changes in indicators calculation functions] ...

# ========== TICKER PROCESSING ==========
@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_ticker_data(_ticker, exchange, yf_symbol):
    """Fetch and process data for a single ticker"""
    try:
        ticker_obj = yf.Ticker(yf_symbol)
        hist = safe_yfinance_fetch(ticker_obj)
        if hist.empty or len(hist) < 50:
            return None

        momentum_data = calculate_momentum(hist)
        if not momentum_data:
            return None

        # Calculate price changes
        current_price = hist['Close'].iloc[-1]
        five_day_change = ((current_price/hist['Close'].iloc[-5]-1)*100) if len(hist) >= 5 else None
        twenty_day_change = ((current_price/hist['Close'].iloc[-20]-1)*100) if len(hist) >= 20 else None

        return {
            "Symbol": _ticker,
            "Exchange": exchange,
            "Price": round(current_price, 2),
            "5D_Change": round(five_day_change, 1) if five_day_change else None,
            "20D_Change": round(twenty_day_change, 1) if twenty_day_change else None,
            **momentum_data,
            "Last_Updated": datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d %H:%M"),
            "YF_Symbol": yf_symbol
        }
    except Exception as e:
        st.warning(f"Error processing {_ticker}: {str(e)}")
        return None

# ========== STREAMLIT UI ==========
def display_results(filtered_df):
    """Display the filtered results in a professional table"""
    if filtered_df.empty:
        st.warning("No stocks match your current filters. Try adjusting your criteria.")
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Stocks Found", len(filtered_df))
    with col2:
        st.metric("Avg Momentum Score", round(filtered_df["Momentum_Score"].mean(), 1))
    with col3:
        st.metric("Strong Trends", len(filtered_df[filtered_df["Trend"] == "↑ Strong"]))
    with col4:
        st.metric("Avg Volume Ratio", round(filtered_df["Volume_Ratio"].mean(), 2))

    # === DI CROSSOVER SECTION: show crossover columns in summary
    st.dataframe(
        filtered_df[[
            "Symbol", "Exchange", "Price", "5D_Change", "20D_Change",
            "Momentum_Score", "Trend", "RSI", "MACD_Hist",
            "Volume_Ratio", "ADX", "Bullish_Crossover", "Bearish_Crossover", "Last_Updated"
        ]].sort_values("Momentum_Score", ascending=False),
        use_container_width=True,
        height=600,
        column_config={
            "Symbol": st.column_config.TextColumn(width="small"),
            "Exchange": st.column_config.TextColumn(width="small"),
            "Price": st.column_config.NumberColumn(format="$%.2f", width="small"),
            "5D_Change": st.column_config.NumberColumn(format="%.1f%%", width="small"),
            "20D_Change": st.column_config.NumberColumn(format="%.1f%%", width="small"),
            "Volume_Ratio": st.column_config.NumberColumn(format="%.2fx", width="small"),
            "Momentum_Score": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100),
            "RSI": st.column_config.NumberColumn(format="%.1f"),
            "MACD_Hist": st.column_config.NumberColumn(format="%.3f"),
            "ADX": st.column_config.NumberColumn(format="%.1f"),
            "Trend": st.column_config.TextColumn(width="small"),
            "Bullish_Crossover": st.column_config.CheckboxColumn(),
            "Bearish_Crossover": st.column_config.CheckboxColumn()
        },
        hide_index=True
    )

def display_symbol_details(selected_symbol):
    """Display detailed analysis for a selected symbol"""
    if not selected_symbol:
        return

    with st.spinner(f'Loading {selected_symbol} analysis...'):
        try:
            # Always filter from the .copy() of the DataFrame to avoid index misalignment
            symbol_data = st.session_state.filtered_results[
                st.session_state.filtered_results["Symbol"] == selected_symbol
            ].copy().iloc[0]

            st.subheader(f"📊 {selected_symbol} Detailed Analysis")
            tab1, tab2, tab3, tab4 = st.tabs(["Price Chart", "Technical Indicators", "DI Crossovers", "Fundamentals"])
            # [Tabs handling code as before, no changes]
        except Exception as e:
            st.error(f"Error loading {selected_symbol}: {str(e)}")

def main():
    st.set_page_config(page_title="S&P 500 Momentum Scanner", layout="wide")
    st.title("S&P 500 Momentum Scanner")

    # Load data from Google Sheets
    df = get_google_sheet_data()
    if df.empty:
        st.warning("No data loaded from Google Sheets.")
        return

    # Map symbols to Yahoo Finance format
    df["YF_Symbol"] = df.apply(
        lambda row: map_to_yfinance_symbol(row["Symbol"], row["Exchange"]), axis=1
    )

    # User filters
    exchanges = df["Exchange"].unique().tolist()
    selected_exchange = st.sidebar.selectbox("Exchange", ["All"] + exchanges)
    min_score = st.sidebar.slider("Min Momentum Score", 0, 100, 50)

    # (Optional) For faster testing, limit the number of symbols fetched:
    # df = df.head(10)

    # Parallel ticker data loading with progress bar
    ticker_data = []
    progress = st.progress(0, text="Fetching ticker data...")
    total = len(df)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(get_ticker_data, row["Symbol"], row["Exchange"], row["YF_Symbol"])
            for idx, row in df.iterrows()
        ]
        for i, f in enumerate(as_completed(futures)):
            data = f.result()
            if data:
                ticker_data.append(data)
            progress.progress((i + 1) / total, text=f"Processed {i+1}/{total} tickers")
    progress.empty()

    results_df = pd.DataFrame(ticker_data)

    # Apply filters SAFELY
    if not results_df.empty:
        results_df = results_df.reset_index(drop=True)
        if selected_exchange != "All":
            mask = (
                (results_df["Momentum_Score"] >= min_score) &
                (results_df["Exchange"] == selected_exchange)
            )
            filtered = results_df[mask].copy()
        else:
            mask = (results_df["Momentum_Score"] >= min_score)
            filtered = results_df[mask].copy()
    else:
        filtered = pd.DataFrame()

    st.session_state.filtered_results = filtered

    # Show results table
    display_results(filtered)

    # Details for selected stock
    if not filtered.empty:
        selected = st.selectbox("Select a symbol for details", filtered["Symbol"])
        display_symbol_details(selected)

if __name__ == "__main__":
    main()
