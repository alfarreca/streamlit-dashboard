import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(layout="wide")

# ---- Load from Google Sheets ----
@st.cache_data(show_spinner=True)
def load_watchlist_from_gsheet(sheet_id: str, worksheet_name: str = None):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file(
        "streamlit-dashboard/credentials/credentials.json",
        scopes=scope
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id)
    worksheet = sheet.worksheet(worksheet_name) if worksheet_name else sheet.sheet1
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

# ---- Set your Sheet ID ----
GOOGLE_SHEET_ID = "1M9Vb7SnSwAGw3Uaqrje8m7nmQHjdqKX0qLkpZiDPt8"

# ---- Load the Watchlist ----
st.title("📊 Master Watchlist Dashboard (Google Sheet Powered)")
with st.spinner("Loading your Google Sheet..."):
    df = load_watchlist_from_gsheet(GOOGLE_SHEET_ID)
    st.success("Loaded watchlist successfully!")

# ---- Preview Table ----
st.subheader("📄 Watchlist Preview")
st.dataframe(df, use_container_width=True)
