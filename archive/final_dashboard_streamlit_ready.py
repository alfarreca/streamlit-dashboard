import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from google.oauth2.service_account import Credentials
import gspread

# Google Sheets Authentication
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_INFO = st.secrets["GCP_SERVICE_ACCOUNT"]
creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
gc = gspread.authorize(creds)

# Open the Google Sheet
sheet = gc.open_by_key("1sNYUiP4Pl8GVYQ1S7Ltc4ETv-ctOA1RVCdYkMb5xjjg").sheet1
df = pd.DataFrame(sheet.get_all_records()).dropna(subset=["Symbol", "Exchange"]).drop_duplicates("Symbol")

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

# Streamlit configuration
st.set_page_config(layout="wide")
st.title("📊 All Tickers – Technical & Fundamental Metrics")

results = []
for _, row in df.iterrows():
    symbol, exchange = row["Symbol"], row["Exchange"]
    yf_symbol = map_to_yfinance_symbol(symbol, exchange)
    try:
        hist = yf.Ticker(yf_symbol).history(period="6mo")
        if hist.empty:
            continue

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

        ticker_info = yf.Ticker(yf_symbol).info
        dividend_yield = ticker_info.get("dividendYield", 0) * 100
        dividend_payout_ratio = ticker_info.get("payoutRatio", 0) * 100
        free_cash_flow = ticker_info.get("freeCashflow", 0)

        results.append({
            "Symbol": symbol,
            "Price": round(last_price, 2),
            "MA10": round(ma10, 2),
            "MA20": round(ma20, 2),
            "% vs MA10": f"{divergence}%",
            "Volume": int(volume.iloc[-1]),
            "Vol MA10": int(volume_ma10),
            "Signal": signal,
            "Last Updated": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
            "Crossover": crossover,
            "Divergence": divergence,
            "Prev Price": round(prev_price, 2),
            "Prev MA10": round(prev_ma10, 2),
            "Dividend Yield (%)": round(dividend_yield, 2),
            "Dividend Payout Ratio (%)": round(dividend_payout_ratio, 2),
            "Free Cash Flow (LC m)": round(free_cash_flow / 1e6, 2) if free_cash_flow else "N/A"
        })

    except Exception as e:
        st.error(f"Error processing {symbol}: {e}")

if results:
    st.dataframe(pd.DataFrame(results))
else:
    st.warning("No metrics data available.")
