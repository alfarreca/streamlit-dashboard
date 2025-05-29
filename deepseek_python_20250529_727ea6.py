import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime

# Google Sheets Authentication
@st.cache_data
def get_google_sheet_data():
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    SERVICE_ACCOUNT_INFO = st.secrets["GCP_SERVICE_ACCOUNT"]
    creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key("1sNYUiP4Pl8GVYQ1S7Ltc4ETv-ctOA1RVCdYkMb5xjjg").sheet1
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

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_ticker_data(_ticker, yf_symbol):
    try:
        ticker_obj = yf.Ticker(yf_symbol)
        hist = ticker_obj.history(period="6mo")
        if hist.empty:
            return None

        close = hist["Close"]
        volume = hist["Volume"]

        last_price = close.iloc[-1]
        ma10 = close.rolling(window=10).mean().iloc[-1]
        ma20 = close.rolling(window=20).mean().iloc[-1]
        prev_price = close.iloc[-2]
        prev_ma10 = close.rolling(window=10).mean().iloc[-2]
        volume_ma10 = volume.rolling(window=10).mean().iloc[-1]

        divergence = round((last_price - ma10) / ma10 * 100, 2)
        signal = "Buy" if last_price > ma10 > ma20 else "Sell" if last_price < ma10 < ma20 else "Neutral"
        crossover = "MA10>MA20" if ma10 > ma20 else "MA10<MA20"

        # Get fundamental data with error handling
        ticker_info = ticker_obj.info
        dividend_yield = ticker_info.get("dividendYield", 0) * 100
        dividend_payout_ratio = ticker_info.get("payoutRatio", 0) * 100
        free_cash_flow = ticker_info.get("freeCashflow", None)

        return {
            "Symbol": _ticker,
            "Price": round(last_price, 2),
            "MA10": round(ma10, 2),
            "MA20": round(ma20, 2),
            "% vs MA10": f"{divergence}%",
            "Volume": int(volume.iloc[-1]),
            "Vol MA10": int(volume_ma10),
            "Signal": signal,
            "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Crossover": crossover,
            "Divergence": divergence,
            "Prev Price": round(prev_price, 2),
            "Prev MA10": round(prev_ma10, 2),
            "Dividend Yield (%)": round(dividend_yield, 2),
            "Dividend Payout Ratio (%)": round(dividend_payout_ratio, 2),
            "Free Cash Flow (LC m)": round(free_cash_flow / 1e6, 2) if free_cash_flow else "N/A",
            "YF Symbol": yf_symbol
        }
    except Exception as e:
        st.error(f"Error processing {_ticker} ({yf_symbol}): {str(e)}")
        return None

# Streamlit configuration
st.set_page_config(layout="wide")
st.title("📊 All Tickers – Technical & Fundamental Metrics")

# Load data
df = get_google_sheet_data()

# Add filters
col1, col2, col3 = st.columns(3)
with col1:
    selected_exchange = st.multiselect("Filter by Exchange", options=df["Exchange"].unique(), default=df["Exchange"].unique())
with col2:
    min_divergence = st.number_input("Minimum Divergence %", min_value=-100.0, max_value=100.0, value=-100.0)
with col3:
    signal_filter = st.multiselect("Filter by Signal", options=["Buy", "Sell", "Neutral"], default=["Buy", "Sell", "Neutral"])

# Process data
results = []
progress_bar = st.progress(0)
status_text = st.empty()

for i, (_, row) in enumerate(df.iterrows()):
    if selected_exchange and row["Exchange"] not in selected_exchange:
        continue
        
    symbol, exchange = row["Symbol"], row["Exchange"]
    yf_symbol = map_to_yfinance_symbol(symbol, exchange)
    
    progress = (i + 1) / len(df)
    progress_bar.progress(progress)
    status_text.text(f"Processing {i+1}/{len(df)}: {symbol} ({exchange})")
    
    ticker_data = get_ticker_data(symbol, yf_symbol)
    if ticker_data:
        results.append(ticker_data)

progress_bar.empty()
status_text.empty()

if results:
    results_df = pd.DataFrame(results)
    
    # Apply additional filters
    results_df = results_df[
        (results_df["Divergence"] >= min_divergence) &
        (results_df["Signal"].isin(signal_filter))
    ]
    
    # Sort options
    sort_options = {
        "Divergence (High to Low)": "Divergence",
        "Divergence (Low to High)": "Divergence",
        "Price (High to Low)": "Price",
        "Price (Low to High)": "Price",
        "Dividend Yield (High to Low)": "Dividend Yield (%)",
        "Volume (High to Low)": "Volume"
    }
    
    sort_col, _, _ = st.columns(3)
    with sort_col:
        sort_option = st.selectbox("Sort by", options=list(sort_options.keys()))
    
    sort_column = sort_options[sort_option]
    ascending = "Low to High" in sort_option
    results_df = results_df.sort_values(by=sort_column, ascending=ascending)
    
    # Display results
    st.dataframe(
        results_df.drop(columns=["Divergence", "YF Symbol"]),
        use_container_width=True,
        height=700
    )
    
    # Download button
    st.download_button(
        label="Download Data as CSV",
        data=results_df.to_csv(index=False),
        file_name="ticker_metrics.csv",
        mime="text/csv"
    )
else:
    st.warning("No metrics data available for the selected filters.")