import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import ta  # Technical analysis library
from io import BytesIO
import numpy as np

# Google Sheets integration
import os

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    st.warning("gspread and google-auth are required for Google Sheets integration.")

st.set_page_config(
    page_title="Stock Technical Analysis",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main { max-width: 1200px; }
    .stSelectbox { margin-bottom: 20px; }
    .stFileUploader { margin-bottom: 20px; }
    .metric-card { background-color: #f0f2f6; border-radius: 10px; padding: 15px; margin-bottom: 15px; }
    .sheet-selector { margin-bottom: 15px; }
    .company-comparison { margin-top: 30px; }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 Stock Technical Analysis Dashboard")

# --- GOOGLE SHEETS SETUP ---
def get_gsheet_dataframe(sheet_name, worksheet_name=None):
    # Prefer Streamlit secrets (Cloud); else try local credentials.json
    if "google_service_account" in st.secrets:
        import json
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
    if worksheet_name:
        ws = gc.open(sheet_name).worksheet(worksheet_name)
    else:
        ws = gc.open(sheet_name).sheet1
    df = pd.DataFrame(ws.get_all_records())
    return df

# --- SIDEBAR ---
with st.sidebar:
    st.header("Watchlist Source")
    watchlist_source = st.radio("Select ticker list source", [
        "Google Sheet",
        "Upload Excel",
        "Manual Ticker"
    ])
    sheet_name = None
    worksheet_name = None
    uploaded_file = None
    manual_ticker = None

    if watchlist_source == "Google Sheet":
        sheet_name = st.text_input("Google Sheet Name", "Master_Watchlist")
        worksheet_name = st.text_input("Worksheet Name (blank = first sheet)", "")
    elif watchlist_source == "Upload Excel":
        uploaded_file = st.file_uploader("Choose an XLSX file with 'Symbol' and 'Exchange' columns", type=["xlsx"])
    else:
        manual_ticker = st.text_input("Enter a single ticker (e.g. SPY, AAPL, 9618.HK)",
                                      help="For HKEX stocks use format XXXX.HK (e.g. 9618.HK)")

    st.header("Analysis Settings")
    analysis_type = st.radio("Analysis Type", ["Single Company", "Multi-Company Compare"])
    start_date = st.date_input("Start date", pd.to_datetime("2020-01-01"))
    end_date = st.date_input("End date", pd.to_datetime("today"))
    st.header("Technical Indicators")
    show_sma = st.checkbox("Show SMA (20, 50)", value=True)
    show_ema = st.checkbox("Show EMA (20)", value=True)
    show_rsi = st.checkbox("Show RSI (14)", value=True)
    show_macd = st.checkbox("Show MACD", value=True)
    show_bollinger = st.checkbox("Show Bollinger Bands", value=True)

# --- SUPPORT FUNCTIONS (Unchanged) ---
def fetch_live_price(ticker):
    try:
        info = yf.Ticker(ticker)
        price = info.fast_info['last_price']
        return price
    except Exception:
        return None

def get_sheet_names(uploaded_file):
    if uploaded_file is not None:
        try:
            xls = pd.ExcelFile(uploaded_file)
            return xls.sheet_names
        except Exception as e:
            st.error(f"Error reading file: {e}")
            return []
    return []

@st.cache_data
def load_tickers_from_sheet(uploaded_file, selected_sheet):
    if uploaded_file is not None and selected_sheet is not None:
        try:
            df = pd.read_excel(uploaded_file, sheet_name=selected_sheet)
            if 'Symbol' not in df.columns or 'Exchange' not in df.columns:
                st.error("The selected sheet must contain 'Symbol' and 'Exchange' columns.")
                return None
            df['YFinance_Symbol'] = df.apply(lambda row: 
                f"{row['Symbol']}.HK" if row['Exchange'] == 'HKEX' else 
                f"{row['Symbol']}", axis=1)
            df['Display_Name'] = df.apply(lambda row: 
                f"{row['Symbol']}.HK" if row['Exchange'] == 'HKEX' else 
                f"{row['Symbol']}", axis=1)
            return df
        except Exception as e:
            st.error(f"Error reading sheet {selected_sheet}: {e}")
            return None
    return None

@st.cache_data
def load_stock_data(ticker, start_date, end_date):
    try:
        if ticker.endswith('.HK.HK'):
            ticker = ticker.replace('.HK.HK', '.HK')
        data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if data.empty:
            st.error(f"No data found for {ticker}. Please verify:")
            st.error("- For HKEX stocks, use format 'XXXX.HK' (e.g., '9618.HK')")
            st.error("- Check if the ticker exists on Yahoo Finance")
            return None
        data = data.apply(pd.to_numeric, errors='coerce')
        data = data.dropna()
        # Flatten columns if MultiIndex
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = ['_'.join([str(i) for i in col if i]) for col in data.columns.values]
        return data
    except Exception as e:
        st.error(f"Error downloading data for {ticker}: {e}")
        return None

def calculate_indicators(df):
    if df is None or df.empty:
        return df
    df = df.copy()
    close_col = [c for c in df.columns if c.startswith('Close')][0]
    vol_col = [c for c in df.columns if c.startswith('Volume')][0]
    close_prices = df[close_col].squeeze()
    try:
        if show_sma:
            df['SMA_20'] = ta.trend.sma_indicator(close=close_prices, window=20)
            df['SMA_50'] = ta.trend.sma_indicator(close=close_prices, window=50)
        if show_ema:
            df['EMA_20'] = ta.trend.ema_indicator(close=close_prices, window=20)
        if show_rsi:
            df['RSI_14'] = ta.momentum.rsi(close=close_prices, window=14)
        if show_macd:
            macd = ta.trend.MACD(close=close_prices)
            df['MACD'] = macd.macd()
            df['MACD_Signal'] = macd.macd_signal()
            df['MACD_Hist'] = macd.macd_diff()
        if show_bollinger:
            bb = ta.volatility.BollingerBands(close=close_prices)
            df['BB_Upper'] = bb.bollinger_hband()
            df['BB_Lower'] = bb.bollinger_lband()
        # --- Volume SMA 20 ---
        df['Volume_SMA_20'] = df[vol_col].rolling(window=20).mean()
        return df
    except Exception as e:
        st.error(f"Error calculating indicators: {str(e)}")
        return df

# --- [All your plot and metrics functions remain unchanged here] ---

def main():
    # --- Load ticker list from chosen source ---
    tickers_df = None
    base_symbol = None
    selected_display = None
    sheet_names = []

    if watchlist_source == "Google Sheet":
        try:
            gsheet_df = get_gsheet_dataframe(sheet_name, worksheet_name if worksheet_name else None)
            if 'Symbol' not in gsheet_df.columns:
                st.error("Google Sheet must have a 'Symbol' column.")
                return
            # Try to infer Exchange column if missing (default to US)
            if 'Exchange' not in gsheet_df.columns:
                gsheet_df['Exchange'] = 'US'
            gsheet_df['YFinance_Symbol'] = gsheet_df.apply(lambda row: 
                f"{row['Symbol']}.HK" if row['Exchange'] == 'HKEX' else 
                f"{row['Symbol']}", axis=1)
            gsheet_df['Display_Name'] = gsheet_df.apply(lambda row: 
                f"{row['Symbol']}.HK" if row['Exchange'] == 'HKEX' else 
                f"{row['Symbol']}", axis=1)
            tickers_df = gsheet_df
        except Exception as e:
            st.error(f"Error loading Google Sheet: {e}")
            return
    elif watchlist_source == "Upload Excel" and uploaded_file is not None:
        sheet_names = get_sheet_names(uploaded_file)
        if len(sheet_names) > 1:
            selected_sheet = st.selectbox("Select sheet to use", sheet_names, key="sheet_selector")
        elif len(sheet_names) == 1:
            selected_sheet = sheet_names[0]
        else:
            selected_sheet = None
        tickers_df = load_tickers_from_sheet(uploaded_file, selected_sheet)
    elif watchlist_source == "Manual Ticker":
        if manual_ticker:
            tickers_df = pd.DataFrame({
                'Symbol': [manual_ticker],
                'Exchange': ['MANUAL'],
                'YFinance_Symbol': [manual_ticker],
                'Display_Name': [manual_ticker]
            })

    # --- Main app logic (unchanged) ---
    # (Continue with the rest of your main function as before)
    # ... [copy all logic from your previous main() from here onward] ...

if __name__ == "__main__":
    main()
