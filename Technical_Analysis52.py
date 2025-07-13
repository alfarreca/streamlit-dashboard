import streamlit as st
import pandas as pd
import yfinance as yf

# If using Google Sheets, import gspread and google-auth
try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    pass  # Not needed unless using Google Sheets

st.set_page_config(page_title="Stock Technical Analysis Dashboard", page_icon="📈", layout="wide")

st.title("📈 Stock Technical Analysis Dashboard (Validated Tickers)")

# ----------- TICKER INPUT SOURCES -----------
SOURCE = st.sidebar.radio("Select Watchlist Source", ["Google Sheet", "Upload Excel", "Manual"])

df = None

if SOURCE == "Google Sheet":
    sheet_name = st.sidebar.text_input("Google Sheet Name", "Master_Watchlist")
    worksheet_name = st.sidebar.text_input("Worksheet Name (optional)", "")
    # --- Google Sheets Integration ---
    try:
        # Streamlit Cloud: use secrets; else fallback to local credentials.json
        if "google_service_account" in st.secrets:
            from google.oauth2.service_account import Credentials
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
        ws = gc.open(sheet_name).worksheet(worksheet_name) if worksheet_name else gc.open(sheet_name).sheet1
        sheet_df = pd.DataFrame(ws.get_all_records())
        if 'Symbol' in sheet_df.columns:
            df = pd.DataFrame({"YFinance_Symbol": sheet_df['Symbol'].astype(str)})
        else:
            st.error("Sheet must have a column named 'Symbol'.")
    except Exception as e:
        st.error(f"Error loading Google Sheet: {e}")

elif SOURCE == "Upload Excel":
    uploaded_file = st.sidebar.file_uploader("Upload an Excel file", type=["xlsx"])
    if uploaded_file:
        excel_df = pd.read_excel(uploaded_file)
        # Try to auto-detect column name (case-insensitive)
        possible_cols = [c for c in excel_df.columns if "symbol" in c.lower()]
        if possible_cols:
            col = possible_cols[0]
            df = pd.DataFrame({"YFinance_Symbol": excel_df[col].astype(str)})
        else:
            st.error("Excel file must contain a column with ticker symbols (e.g. 'Symbol').")

elif SOURCE == "Manual":
    tickers_raw = st.sidebar.text_area("Enter tickers (comma-separated)", "AAPL, TSLA, 9618.HK, 700.HK, FAKE1, FAKE2.HK")
    tickers = [t.strip() for t in tickers_raw.split(",") if t.strip()]
    if tickers:
        df = pd.DataFrame({"YFinance_Symbol": tickers})

# ---------- VALIDATION FUNCTIONS ----------
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

# ----------- VALIDATE & DISPLAY -----------
if df is not None and not df.empty:
    st.write("### Original Watchlist", df)

    with st.spinner("Validating tickers with Yahoo Finance..."):
        valid_df = filter_valid_tickers(df, symbol_col="YFinance_Symbol")

    n_removed = len(df) - len(valid_df)
    if n_removed > 0:
        st.warning(f"{n_removed} invalid ticker(s) removed (not found on Yahoo Finance).")

    if valid_df.empty:
        st.error("No valid tickers found in your list!")
    else:
        st.success(f"**{len(valid_df)} valid ticker(s) remain:**")
        st.dataframe(valid_df)
        # Dropdown to select ticker for further analysis
        selected_ticker = st.selectbox("Select a valid ticker to analyze:", valid_df["YFinance_Symbol"])
        st.info(f"You selected: **{selected_ticker}**")

        # ------------- (Optional) Add your analysis/plotting here -------------
        data = yf.download(selected_ticker, period="6mo")
        st.line_chart(data["Close"])
else:
    st.info("Please provide ticker input to validate.")

st.caption("Works for US, HK, EU, and any Yahoo-supported tickers. Use format: '9618.HK', 'AAPL', etc.")

