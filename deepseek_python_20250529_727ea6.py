import streamlit as st
import pandas as pd
import yfinance as yf
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

# Improved Crossover Calculation
def calculate_crossover(close_series):
    ma10 = close_series.rolling(window=10).mean()
    ma20 = close_series.rolling(window=20).mean()
    
    # Current relationship
    current_relation = "MA10 > MA20" if ma10.iloc[-1] > ma20.iloc[-1] else "MA10 ≤ MA20"
    
    # Crossover detection
    crossover_status = "No Crossover"
    
    # Golden Cross (MA10 crosses above MA20)
    if (ma10.iloc[-2] <= ma20.iloc[-2]) and (ma10.iloc[-1] > ma20.iloc[-1]):
        crossover_status = "🟢 Golden Cross (Bullish)"
    
    # Death Cross (MA10 crosses below MA20)
    elif (ma10.iloc[-2] >= ma20.iloc[-2]) and (ma10.iloc[-1] < ma20.iloc[-1]):
        crossover_status = "🔴 Death Cross (Bearish)"
    
    # Recent crossover within last 5 days
    elif any((ma10.shift(i) <= ma20.shift(i)) & (ma10 > ma20) for i in range(1, 6)):
        crossover_status = "🟡 Recent Golden Cross"
    elif any((ma10.shift(i) >= ma20.shift(i)) & (ma10 < ma20) for i in range(1, 6)):
        crossover_status = "🟠 Recent Death Cross"
    
    return f"{current_relation} | {crossover_status}"

@st.cache_data(ttl=3600)
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
        signal = "🟢 Buy" if last_price > ma10 > ma20 else "🔴 Sell" if last_price < ma10 < ma20 else "🟡 Neutral"
        crossover = calculate_crossover(close)

        ticker_info = ticker_obj.info
        dividend_yield = ticker_info.get("dividendYield", 0) * 100
        dividend_payout_ratio = ticker_info.get("payoutRatio", 0) * 100
        free_cash_flow = ticker_info.get("freeCashflow", None)
        pe_ratio = ticker_info.get("trailingPE", None)

        return {
            "Symbol": symbol,
            "Exchange": exchange,
            "Price": round(last_price, 2),
            "MA10": round(ma10, 2),
            "MA20": round(ma20, 2),
            "% vs MA10": f"{divergence}%",
            "Volume": int(volume.iloc[-1]),
            "Vol MA10": int(volume_ma10),
            "Signal": signal,
            "Crossover": crossover,
            "P/E Ratio": round(pe_ratio, 2) if pe_ratio else "N/A",
            "Dividend Yield (%)": round(dividend_yield, 2),
            "Dividend Payout Ratio (%)": round(dividend_payout_ratio, 2),
            "Free Cash Flow (LC m)": round(free_cash_flow / 1e6, 2) if free_cash_flow else "N/A",
            "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "YF Symbol": yf_symbol
        }
    except Exception as e:
        st.error(f"Error processing {_ticker}: {str(e)}")
        return None

# Streamlit UI Configuration
st.set_page_config(layout="wide")
st.title("📊 Stock Watchlist Dashboard")

# Load data
df = get_google_sheet_data()

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

# Process data
results = []
progress_bar = st.progress(0)
status_text = st.empty()

for i, (_, row) in enumerate(df.iterrows()):
    symbol, exchange = row["Symbol"], row["Exchange"]
    if selected_exchange and exchange not in selected_exchange:
        continue
        
    yf_symbol = map_to_yfinance_symbol(symbol, exchange)
    progress_bar.progress((i + 1) / len(df))
    status_text.text(f"Processing {i+1}/{len(df)}: {symbol} ({exchange})")
    
    ticker_data = get_ticker_data(symbol, yf_symbol)
    if ticker_data:
        results.append(ticker_data)

progress_bar.empty()
status_text.empty()

if results:
    results_df = pd.DataFrame(results)
    
    # Apply filters
    results_df = results_df[
        results_df["Signal"].isin(signal_filter) &
        results_df["Crossover"].str.contains("|".join(crossover_filter), case=False)
    ]
    
    # Sort options
    sort_options = {
        "Divergence (High to Low)": ("% vs MA10", False),
        "Price (High to Low)": ("Price", False),
        "P/E Ratio (Low to High)": ("P/E Ratio", True),
        "Dividend Yield (High to Low)": ("Dividend Yield (%)", False)
    }
    
    sort_col, _, _ = st.columns(3)
    with sort_col:
        sort_option = st.selectbox("Sort by", options=list(sort_options.keys()))
    
    sort_column, ascending = sort_options[sort_option]
    results_df = results_df.sort_values(
        by=sort_column, 
        ascending=ascending,
        key=lambda x: pd.to_numeric(x.str.replace('%', ''), errors='coerce')
    )
    
    # Display results
    st.dataframe(
        results
