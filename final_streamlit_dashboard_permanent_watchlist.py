from pathlib import Path

# Updated Streamlit script with Google Sheets integration, ticker metrics, and UI
streamlit_script = """
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import json
import gspread
from google.oauth2.service_account import Credentials

# --- SETUP GOOGLE SHEETS INTEGRATION ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_INFO = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
gc = gspread.authorize(creds)
SPREADSHEET_ID = "1JqJ7ISBFkPoTE0ZrYkq9rTfD2so4m2csZuQZ5aP4CuM"
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
        return symbol  # US tickers need no suffix
    suffix = exchange_suffix(exch)
    return f"{symbol}.{suffix}" if suffix else symbol

# --- METRICS CALC ---
def calculate_metrics(tickers):
    rows = []
    for ticker in tickers:
        yf_symbol = map_to_exchange(ticker)
        try:
            data = yf.Ticker(yf_symbol).history(period="6mo")
            if data.empty:
                continue
            price = data["Close"].iloc[-1]
            ma10 = data["Close"].rolling(10).mean().iloc[-1]
            ma20 = data["Close"].rolling(20).mean().iloc[-1]
            pct_above_ma10 = ((price - ma10) / ma10) * 100 if ma10 else None
            volume = data["Volume"].iloc[-1]
            vol_ma10 = data["Volume"].rolling(10).mean().iloc[-1]
            signal = "Buy" if price > ma10 and price > ma20 else "Hold"
            crossover = "Above" if price > ma10 else "Below"
            divergence = "Overbought" if pct_above_ma10 and pct_above_ma10 > 10 else "OK"
            rows.append({
                "Ticker": ticker, "Price": price, "MA10": ma10, "MA20": ma20,
                "% vs MA10": pct_above_ma10, "Volume": volume, "Vol MA10": vol_ma10,
                "Signal": signal, "Crossover": crossover, "Divergence": divergence,
                "Last Updated": pd.Timestamp.today().date()
            })
        except Exception:
            continue
    return pd.DataFrame(rows)

# --- STREAMLIT UI ---
st.set_page_config(layout="wide")
st.title("🧭 Global Defense & AI Watchlist (Permanent Sheet Access)")

tab1, tab2, tab3 = st.tabs(["📈 Chart", "📊 All Metrics", "🧠 AI Insight"])

# --- TAB 1: SINGLE STOCK PLOT ---
with tab1:
    selected = st.selectbox("Select symbol", clean_symbols)
    yf_symbol = map_to_exchange(selected)
    data = yf.Ticker(yf_symbol).history(period="6mo")
    if not data.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data.index, y=data["Close"], name="Close"))
        fig.add_trace(go.Scatter(x=data.index, y=data["Close"].rolling(10).mean(), name="MA10"))
        fig.add_trace(go.Scatter(x=data.index, y=data["Close"].rolling(20).mean(), name="MA20"))
        fig.update_layout(title=f"{selected} - Price & MAs", xaxis_title="Date", yaxis_title="Price")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("⚠️ No chart data found.")

# --- TAB 2: METRICS TABLE ---
with tab2:
    st.markdown("### 📋 All Metrics")
    ticker_input = st.text_input("Enter tickers (comma or space separated)", value=" ".join(clean_symbols))
    if ticker_input:
        tickers = [t.strip().upper() for t in ticker_input.replace(",", " ").split()]
        df = calculate_metrics(tickers)
        st.dataframe(df)

# --- TAB 3: AI ---
with tab3:
    st.markdown("✅ **AI-generated summaries will appear here soon.**")
"""

# Save script
script_path = "/mnt/data/final_streamlit_dashboard_permanent_watchlist.py"
Path(script_path).write_text(streamlit_script)

script_path
