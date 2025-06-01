from pathlib import Path

# Path where the corrected final script will be saved
final_path = Path("/mnt/data/final_streamlit_dashboard_with_all_metrics.py")
final_path.write_text("""
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(layout="wide")
st.title("📊 Global Defense & AI Stock Dashboard")

# --- LOAD WATCHLIST FROM GOOGLE SHEETS ---
@st.cache_data(show_spinner=False)
def load_watchlist():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRe5_juKpIbiTy7fc92QICvpGhawvqKZWDxmrgUTFNtFjNsCPA10e-wt0UJ4eZ-3tlF5Ol55g-U9wke/pub?output=csv"
    df = pd.read_csv(url)
    df = df.dropna(subset=["Symbol", "Exchange"])
    return df

watchlist = load_watchlist()
symbol_list = watchlist["Symbol"].tolist()
exchange_map = dict(zip(watchlist["Symbol"], watchlist["Exchange"]))

def exchange_suffix(ex: str) -> str:
    suffix_map = {
        "ETR": "DE", "EPA": "PA", "LON": "L", "BIT": "MI", "STO": "ST",
        "SWX": "SW", "TSE": "TO", "ASX": "AX", "HKG": "HK"
    }
    return suffix_map.get(ex.upper(), "")

def format_yf_symbol(symbol: str) -> str:
    exch = exchange_map.get(symbol.upper())
    if exch in ["NYSE", "NASDAQ"]:
        return symbol
    suffix = exchange_suffix(exch)
    return f"{symbol}.{suffix}" if suffix else symbol

def fetch_metrics(symbols: list) -> pd.DataFrame:
    rows = []
    for symbol in symbols:
        try:
            yf_symbol = format_yf_symbol(symbol)
            df = yf.Ticker(yf_symbol).history(period="6mo")
            if df.empty:
                continue
            ma10 = df["Close"].rolling(10).mean().iloc[-1]
            ma20 = df["Close"].rolling(20).mean().iloc[-1]
            close = df["Close"].iloc[-1]
            vol = df["Volume"].iloc[-1]
            vol_mean = df["Volume"].rolling(10).mean().iloc[-1]
            prev = df["Close"].iloc[-2]

            row = {
                "Symbol": symbol,
                "Price": close,
                "MA10": ma10,
                "MA20": ma20,
                "% vs MA10": (close - ma10) / ma10 * 100,
                "Volume": vol,
                "Vol MA10": vol_mean,
                "Signal": "Buy" if close > ma10 else "Sell",
                "Last Updated": datetime.today().strftime("%Y-%m-%d"),
                "Crossover": "Above" if close > ma20 else "Below",
                "Divergence": "Overbought" if close > ma10 * 1.1 else "OK",
                "Prev Price": prev
            }
            rows.append(row)
        except Exception as e:
            continue
    return pd.DataFrame(rows)

tab1, tab2, tab3 = st.tabs(["📈 Charts", "📋 All Metrics", "🧠 AI Insight"])

# --- TAB 1: Charts ---
with tab1:
    selected = st.selectbox("Select a symbol", symbol_list)
    yf_symbol = format_yf_symbol(selected)
    data = yf.Ticker(yf_symbol).history(period="6mo")
    if not data.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data.index, y=data["Close"], mode="lines", name="Close"))
        fig.update_layout(title=f"{selected} - 6mo Chart", xaxis_title="Date", yaxis_title="Price")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No data found for this ticker.")

# --- TAB 2: All Metrics ---
with tab2:
    st.subheader("All Metrics")
    input_tickers = st.text_input("Enter tickers (space or comma separated)", value="TSLA MSFT NVDA")
    tickers = [t.strip().upper() for t in input_tickers.replace(",", " ").split()]
    valid_tickers = [t for t in tickers if t in symbol_list]
    if valid_tickers:
        df_metrics = fetch_metrics(valid_tickers)
        st.dataframe(df_metrics)
    else:
        st.warning("No valid tickers entered or not found in watchlist.")

# --- TAB 3: Placeholder ---
with tab3:
    st.markdown("✅ AI-generated insights will appear here soon.")
""")
final_path
