
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import json
from google.oauth2.service_account import Credentials
import gspread

# --- SETUP GOOGLE SHEETS INTEGRATION ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_INFO = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
gc = gspread.authorize(creds)
SPREADSHEET_ID = "1JqJ7lSBFkPoTE0ZrYk9qrTFd2so4m2csZuQZ5aPCu4M"
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# --- LOAD WATCHLIST FROM GOOGLE SHEETS ---
@st.cache_data(show_spinner=False)
def load_watchlist():
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    df = df.dropna(subset=["Symbol", "Exchange"])
    return df

watchlist = load_watchlist()
clean_symbols = watchlist["Symbol"].tolist()
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
st.title("📊 Global Defense & AI Dashboard")

tab1, tab2, tab3 = st.tabs(["📈 Charts", "📋 Watchlist Table", "🧠 AI Insight"])

# --- TAB 1: PLOT STOCK PRICE ---
with tab1:
    selected = st.selectbox("Select a symbol", clean_symbols)
    yf_symbol = map_to_exchange(selected)
    data = yf.Ticker(yf_symbol).history(period="6mo")
    if not data.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data.index, y=data["Close"], mode="lines", name="Close"))
        fig.add_trace(go.Scatter(x=data.index, y=data["Close"].rolling(10).mean(), name="MA10"))
        fig.add_trace(go.Scatter(x=data.index, y=data["Close"].rolling(20).mean(), name="MA20"))
        fig.update_layout(title=f"{selected} - Price & MAs", xaxis_title="Date", yaxis_title="Price")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No chart data found.")

# --- TAB 2: METRICS TABLE ---
with tab2:
    st.subheader("Watchlist Table")
    st.dataframe(watchlist)

# --- TAB 3: AI INSIGHT PLACEHOLDER ---
with tab3:
    st.markdown("✅ **AI-generated insights will appear here soon.**")
