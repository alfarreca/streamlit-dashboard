
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

# --- LOAD WATCHLIST FROM GOOGLE SHEETS ---
@st.cache_data(show_spinner=False)
def load_watchlist():
    url = "https://docs.google.com/spreadsheets/d/e/YOUR_SHEET_ID_HERE/pub?output=csv"  # Replace with your real sheet link
    df = pd.read_csv(url)
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

# --- STREAMLIT LAYOUT ---
st.set_page_config(layout="wide")
st.title("📊 Global Defense & AI Stock Dashboard")

tab1, tab2, tab3 = st.tabs(["📈 Charts", "📋 Metrics Table", "🧠 AI Insight"])

# --- TAB 1: PLOT STOCK PRICE ---
with tab1:
    selected = st.selectbox("Select a symbol", clean_symbols)
    yf_symbol = map_to_exchange(selected)
    data = yf.Ticker(yf_symbol).history(period="6mo")
    if not data.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data.index, y=data["Close"], mode="lines", name="Close"))
        fig.update_layout(title=f"{selected} - 6mo Chart", xaxis_title="Date", yaxis_title="Price")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No data found for this ticker.")

# --- TAB 2: SHOW RAW TABLE ---
with tab2:
    st.subheader("Watchlist")
    st.dataframe(watchlist)

# --- TAB 3: DUMMY AI OUTPUT ---
with tab3:
    st.markdown("✅ This tab will include AI-generated summaries and alerts soon.")
