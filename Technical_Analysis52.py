import streamlit as st
import pandas as pd
import yfinance as yf

# Google Sheets integration
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Stock Technical Analysis Dashboard", layout="wide")

st.title("📈 Stock Technical Analysis Dashboard")

# ---------- Google Sheets Integration (Enhanced) ----------
def get_gsheet_dataframe(sheet_name, worksheet_name=None):
    try:
        # Use Streamlit secrets if available, else local credentials
        if "google_service_account" in st.secrets:
            creds_dict = dict(st.secrets["google_service_account"])
            creds = Credentials.from_service_account_info(creds_dict, scopes=[
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ])
        else:
            creds = Credentials.from_service_account_file(
                "credentials.json",
                scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            )

        gc = gspread.authorize(creds)

        available_sheets = [sheet.title for sheet in gc.openall()]
        if sheet_name not in available_sheets:
            st.error(f"Google Sheet '{sheet_name}' not found. Available sheets: {available_sheets}")
            return pd.DataFrame()

        sheet = gc.open(sheet_name)

        worksheets = [ws.title for ws in sheet.worksheets()]
        if worksheet_name and worksheet_name not in worksheets:
            st.error(f"Worksheet '{worksheet_name}' not found. Available worksheets: {worksheets}")
            return pd.DataFrame()

        ws = sheet.worksheet(worksheet_name) if worksheet_name else sheet.sheet1
        data = ws.get_all_records()

        if not data:
            st.error("Worksheet is empty or contains no valid rows.")
            return pd.DataFrame()

        df = pd.DataFrame(data)
        return df

    except Exception as e:
        st.error(f"Error accessing Google Sheet: {str(e)}")
        return pd.DataFrame()

# ---------- Ticker Validation ----------
@st.cache_data(show_spinner=True)
def is_valid_ticker(symbol):
    try:
        data = yf.Ticker(symbol).history(period="5d")
        return not data.empty
    except Exception:
        return False

@st.cache_data(show_spinner=True)
def filter_valid_tickers(df, symbol_col="YFinance_Symbol"):
    df = df.copy()
    df["Is_Valid"] = df[symbol_col].apply(is_valid_ticker)
    valid_df = df[df["Is_Valid"]].reset_index(drop=True)
    return valid_df

# ---------- Sidebar Configuration ----------
SOURCE = st.sidebar.radio("Watchlist Source", ["Google Sheet", "Upload Excel", "Manual Input"])

df = None

if SOURCE == "Google Sheet":
    sheet_name = st.sidebar.text_input("Google Sheet Name", "Master_Watchlist")
    worksheet_name = st.sidebar.text_input("Worksheet Name (optional)", "")

    if st.sidebar.button("Load from Google Sheets"):
        df = get_gsheet_dataframe(sheet_name, worksheet_name)

elif SOURCE == "Upload Excel":
    uploaded_file = st.sidebar.file_uploader("Upload an Excel file", type=["xlsx"])
    if uploaded_file:
        excel_df = pd.read_excel(uploaded_file)
        col_candidates = [col for col in excel_df.columns if "symbol" in col.lower()]
        if col_candidates:
            df = pd.DataFrame({"YFinance_Symbol": excel_df[col_candidates[0]].astype(str)})
        else:
            st.error("Excel file must contain a column with ticker symbols.")

elif SOURCE == "Manual Input":
    tickers_raw = st.sidebar.text_area("Enter tickers (comma-separated)", "AAPL, TSLA, 9618.HK")
    tickers = [t.strip() for t in tickers_raw.split(",") if t.strip()]
    df = pd.DataFrame({"YFinance_Symbol": tickers})

# ---------- Main App Logic ----------
if df is not None and not df.empty:
    st.write("### Original Watchlist", df)

    with st.spinner("Validating tickers with Yahoo Finance..."):
        valid_df = filter_valid_tickers(df, symbol_col="YFinance_Symbol")

    n_removed = len(df) - len(valid_df)
    if n_removed > 0:
        st.warning(f"{n_removed} invalid ticker(s) removed (not found on Yahoo Finance).")

    if valid_df.empty:
        st.error("No valid tickers found!")
    else:
        st.success(f"**{len(valid_df)} valid ticker(s) loaded:**")
        st.dataframe(valid_df)

        selected_ticker = st.selectbox("Select a valid ticker for analysis", valid_df["YFinance_Symbol"])

        # Download and plot data for selected ticker
        data = yf.download(selected_ticker, period="6mo")
        if not data.empty:
            st.subheader(f"{selected_ticker} Closing Prices (6 Months)")
            st.line_chart(data["Close"])
        else:
            st.error(f"No historical data found for {selected_ticker}.")

else:
    st.info("Select a source and load your watchlist to begin.")

st.caption("Ensure tickers follow Yahoo Finance format (e.g., '9618.HK', 'AAPL', etc.).")
