from pathlib import Path

script = """
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import gspread
from google.oauth2.service_account import Credentials

# --- GOOGLE SHEETS AUTH ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_INFO = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
gc = gspread.authorize(creds)
sheet = gc.open_by_key("1JqJ7lSBFkPoTE0ZrYk9qrTfD2so4m2csZuQZ5aPCu4M").worksheet("Watchlist")

# --- LOAD WATCHLIST ---
def load_watchlist():
    records = sheet.get_all_records()
    df = pd.DataFrame(records)
    df = df.dropna(subset=["Symbol", "Exchange"])
    return df

# --- ADD NEW TICKER ---
def add_ticker(symbol, exchange):
    existing = load_watchlist()
    if symbol.upper() in existing["Symbol"].values:
        st.warning(f"{symbol} already
