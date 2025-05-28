import json
from google.oauth2.service_account import Credentials

# --- SETUP GOOGLE SHEETS INTEGRATION ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_INFO = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)

import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials

# --- SETUP GOOGLE SHEETS INTEGRATION ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_INFO = st.secrets["GCP_SERVICE_ACCOUNT"]
creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
gc = gspread.authorize(creds)
SPREADSHEET_ID = "1JqJ7ISBFkPoTE0ZzYKqHdPvW0McsPyTbqZKOC0YgLBY"  # Replace with your actual Sheet ID
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

@st.cache_data(show_spinner=False)
def load_watchlist():
    data = sheet.get_all_records()
    return pd.DataFrame(data)

watchlist = load_watchlist()
exchange_map = dict(zip(watchlist["Symbol"], watchlist["Exchange"]))

def exchange_suffix(ex: str) -> str:
    suffix_map = {
        "ETR": "DE", "EPA": "PA", "LON": "L", "BIT": "MI", "STO": "ST",
        "SWX": "SW", "TSE": "TO", "ASX": "AX", "HKG": "HK"
    }
    return suffix_map.get(ex.upper(), "")

def map_to_exchange(symbol: str) -> str:
    exch = exchange_map.get(symbol.upper())
    if exch in ["NYSE", "NASDAQ"]:
        return symbol
    suffix = exchange_suffix(exch)
    return f"{symbol}.{suffix}" if suffix else symbol

# --- STREAMLIT LAYOUT ---
st.set_page_config(layout="wide")
st.title("📊 Global Defense & AI Stock Dashboard")

tab1, tab2, tab3 = st.tabs(["📈 Charts", "📋 All Metrics", "🧠 AI Insight"])

# --- TAB 1: PLOT STOCK PRICE ---
with tab1:
    selected = st.selectbox("Select a symbol", watchlist["Symbol"].tolist())
    yf_symbol = map_to_exchange(selected)
    df = yf.Ticker(yf_symbol).history(period="6mo")
    if not df.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=df["Close"], name="Close"))
        fig.add_trace(go.Scatter(x=df.index, y=df["Close"].rolling(10).mean(), name="MA10"))
        fig.add_trace(go.Scatter(x=df.index, y=df["Close"].rolling(20).mean(), name="MA20"))
        fig.update_layout(title=f"{selected} - Price & MAs", xaxis_title="Date", yaxis_title="Price")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No data found for this ticker.")

# --- TAB 2: SHOW METRICS TABLE ---
with tab2:
    tickers = st.text_input("Enter tickers (comma or space separated)", "TSLA NVDA RHM")
    input_list = [t.strip().upper() for t in tickers.replace(",", " ").split()]
    metrics = []

    for t in input_list:
        try:
            data = yf.Ticker(map_to_exchange(t)).history(period="6mo")
            if not data.empty:
                close = data["Close"]
                row = {
                    "Symbol": t,
                    "Price": close[-1],
                    "MA10": close.rolling(10).mean().iloc[-1],
                    "MA20": close.rolling(20).mean().iloc[-1],
                    "% vs MA10": ((close[-1] - close.rolling(10).mean().iloc[-1]) / close.rolling(10).mean().iloc[-1]) * 100,
                    "Volume": data["Volume"][-1],
                    "Signal": "Buy" if close[-1] > close.rolling(20).mean().iloc[-1] else "Wait",
                    "Last Updated": pd.Timestamp.now().strftime("%Y-%m-%d")
                }
                metrics.append(row)
        except Exception as e:
            st.error(f"{t} - Error fetching data: {e}")

    if metrics:
        df_metrics = pd.DataFrame(metrics)
        st.dataframe(df_metrics)
    else:
        st.info("No valid ticker data found.")

# --- TAB 3: AI GENERATED PLACEHOLDER ---
with tab3:
    st.markdown("✅ **AI-generated insights will appear here soon.**")
