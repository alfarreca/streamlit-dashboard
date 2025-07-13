import streamlit as st
import pandas as pd
import yfinance as yf
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ────────────────────────────────
# Setup Constants
# ────────────────────────────────
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SERVICE_ACCOUNT_FILE = "credentials/credentials.json"  # relative path to service account file
GOOGLE_SHEET_ID = "1M9Vb7SnSwAGw3Uaqrje8m7mnQHjdqKXQoLkpZiDPt8"
SHEET_NAME = "Master_Watchlist"

# ────────────────────────────────
# Load Watchlist from Google Sheets
# ────────────────────────────────
@st.cache_data(show_spinner=True)
def load_watchlist_from_gsheet(sheet_id, sheet_name):
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=sheet_id, range=sheet_name).execute()
    values = result.get("values", [])
    if not values:
        return pd.DataFrame()
    headers = values[0]
    rows = values[1:]
    return pd.DataFrame(rows, columns=headers)

# ────────────────────────────────
# Plot Price Chart for Ticker
# ────────────────────────────────
def plot_price_chart(ticker):
    df = yf.download(ticker, period="6mo", interval="1d", auto_adjust=True)
    if df.empty:
        st.warning(f"No data found for {ticker}")
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["Close"], mode="lines", name=ticker))
    fig.update_layout(
        title=f"{ticker} – Daily Close (6mo)",
        xaxis_title="Date",
        yaxis_title="Price (USD)",
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)

# ────────────────────────────────
# Streamlit App
# ────────────────────────────────
st.set_page_config(page_title="GSheet Technical Dashboard", layout="wide")
st.title("📈 Stock Technical Analysis Dashboard (Google Sheets)")

with st.spinner("🔄 Loading watchlist from Google Sheets..."):
    df_watchlist = load_watchlist_from_gsheet(GOOGLE_SHEET_ID, SHEET_NAME)

if df_watchlist.empty or "Symbol" not in df_watchlist.columns:
    st.error("❌ Failed to load watchlist or missing 'Symbol' column.")
    st.stop()

tickers = df_watchlist["Symbol"].dropna().unique().tolist()

selected = st.multiselect("Select Tickers", options=tickers, default=tickers[:5])

for ticker in selected:
    st.subheader(f"📊 {ticker}")
    plot_price_chart(ticker)
