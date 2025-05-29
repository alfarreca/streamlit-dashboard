import streamlit as st
import pandas as pd
import gspread
import json
from google.oauth2.service_account import Credentials

# --- GOOGLE SHEETS SETUP ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_INFO = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
gc = gspread.authorize(creds)
SHEET_ID = "1JqJ7lSBFkPoTE0ZrYk9qrTfD2so4m2csZuQZ5aPCu4M"
worksheet = gc.open_by_key(SHEET_ID).worksheet("Watchlist")

# --- LOAD WATCHLIST ---
@st.cache_data(show_spinner=False)
def load_watchlist():
    df = pd.DataFrame(worksheet.get_all_records())
    return df

# --- SAVE NEW TICKER ---
def save_ticker(symbol, exchange):
    worksheet.append_row([symbol.upper(), exchange.upper()])
    st.success(f"Added {symbol.upper()} to watchlist.")

# --- STREAMLIT UI ---
st.title("📈 Watchlist Dashboard")

# Add ticker
st.subheader("➕ Add New Ticker")
with st.form("add_ticker_form"):
    symbol = st.text_input("Ticker Symbol")
    exchange = st.text_input("Exchange (e.g., NASDAQ, NYSE)")
    submitted = st.form_submit_button("Add")
    if submitted and symbol and exchange:
        save_ticker(symbol, exchange)

# Show current watchlist
st.subheader("📋 Current Watchlist")
df_watchlist = load_watchlist()
st.dataframe(df_watchlist)
