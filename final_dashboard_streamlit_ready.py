
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import json
from google.oauth2.service_account import Credentials
import gspread

# --- GOOGLE SHEETS AUTH ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_INFO = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
gc = gspread.authorize(creds)

# Open the sheet
sheet = gc.open_by_key("1JqJ7lSBFkPoTE0ZrYk9qrTfD2so4m2csZuQZ5aPCu4M").sheet1
df = pd.DataFrame(sheet.get_all_records())
df = df.dropna(subset=["Symbol", "Exchange"])

# Map to yfinance format
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

# --- STREAMLIT CONFIG ---
st.set_page_config(layout="wide")
st.title("📊 Global Defense & AI Stock Dashboard")

tab1, tab2, tab3 = st.tabs(["📈 Chart", "📋 Metrics", "🧠 AI Output"])

# --- TAB 1: CHART ---
with tab1:
    symbol = st.selectbox("Select Ticker", df["Symbol"])
    exchange = df[df["Symbol"] == symbol]["Exchange"].values[0]
    yf_symbol = map_to_yfinance_symbol(symbol, exchange)
    data = yf.Ticker(yf_symbol).history(period="6mo")
    if not data.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data.index, y=data["Close"], mode="lines", name="Close"))
        fig.update_layout(title=f"{symbol} ({yf_symbol})", xaxis_title="Date", yaxis_title="Price")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No chart data found.")

# --- TAB 2: METRICS TABLE ---
with tab2:
    st.subheader("📋 Ticker Metrics")
    results = []
    for _, row in df.iterrows():
        symbol, exchange = row["Symbol"], row["Exchange"]
        yf_symbol = map_to_yfinance_symbol(symbol, exchange)
        try:
            hist = yf.Ticker(yf_symbol).history(period="6mo")
            if hist.empty: continue
            close = hist["Close"]
            ma10 = close.rolling(window=10).mean().iloc[-1]
            ma20 = close.rolling(window=20).mean().iloc[-1]
            last = close.iloc[-1]
            volume = hist["Volume"].iloc[-1]
            signal = "Buy" if last > ma10 > ma20 else "Sell" if last < ma10 < ma20 else "Neutral"
            crossover = "MA10>MA20" if ma10 > ma20 else "MA10<MA20"
            divergence = round((last - ma10) / ma10 * 100, 2)
            results.append({
                "Symbol": symbol,
                "Price": round(last, 2),
                "MA10": round(ma10, 2),
                "MA20": round(ma20, 2),
                "% vs MA10": f"{divergence}%",
                "Volume": int(volume),
                "Signal": signal,
                "Crossover": crossover,
                "Last Updated": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
            })
        except Exception as e:
            continue
    st.dataframe(pd.DataFrame(results))

# --- TAB 3: AI OUTPUT ---
with tab3:
    st.markdown("🧠 AI-driven alerts and summaries coming soon!")
