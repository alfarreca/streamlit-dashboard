import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import ta  # Technical analysis library
from io import BytesIO
import numpy as np

# Set page configuration
st.set_page_config(
    page_title="Stock Technical Analysis",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better appearance
st.markdown("""
    <style>
    .main {
        max-width: 1200px;
    }
    .stSelectbox {
        margin-bottom: 20px;
    }
    .stFileUploader {
        margin-bottom: 20px;
    }
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

# App title
st.title("📊 Stock Technical Analysis Dashboard")

# Sidebar for file upload and settings
with st.sidebar:
    st.header("Upload Ticker List")
    uploaded_file = st.file_uploader(
        "Choose an XLSX file with 'Symbol' and 'Exchange' columns",
        type=["xlsx"]
    )
    
    st.header("Analysis Settings")
    start_date = st.date_input("Start date", pd.to_datetime("2025-01-01"))
    end_date = st.date_input("End date", pd.to_datetime("today"))
    
    st.header("Technical Indicators")
    show_sma = st.checkbox("Show SMA (20, 50)", value=True)
    show_ema = st.checkbox("Show EMA (20)", value=True)
    show_rsi = st.checkbox("Show RSI (14)", value=True)
    show_macd = st.checkbox("Show MACD", value=True)
    show_bollinger = st.checkbox("Show Bollinger Bands", value=True)

# Load ticker data from uploaded file
@st.cache_data
def load_tickers(uploaded_file):
    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            if 'Symbol' not in df.columns or 'Exchange' not in df.columns:
                st.error("The uploaded file must contain 'Symbol' and 'Exchange' columns.")
                return None
            
            # Create proper symbols for yfinance based on exchange
            df['YFinance_Symbol'] = df.apply(lambda row: 
                f"{row['Symbol']}.HK" if row['Exchange'] == 'HKEX' else 
                f"{row['Symbol']}", axis=1)
            
            # Create display names
            df['Display_Name'] = df['Symbol'] + '.' + df['Exchange']
            
            return df
        except Exception as e:
            st.error(f"Error reading file: {e}")
            return None
    return None

# Download stock data with proper ticker handling
@st.cache_data
def load_stock_data(ticker, start_date, end_date):
    try:
        # Ensure ticker is in correct format for yfinance
        ticker = str(ticker).strip()
        
        # For HKEX stocks, ensure proper .HK suffix
        if '.HK' in ticker and not ticker.endswith('.HK'):
            ticker = ticker.split('.')[0] + '.HK'
        
        # Convert dates to strings
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        # Download data
        data = yf.download(ticker, start=start_str, end=end_str, progress=False)
        
        if data.empty:
            st.error(f"No data found for {ticker}. Please check:")
            st.error("- Ticker format is correct (e.g., '9880.HK' for HKEX)")
            st.error("- Ticker exists on Yahoo Finance")
            st.error("- Date range contains trading days")
            return None
        
        # Ensure proper data formatting
        data = data.apply(pd.to_numeric, errors='coerce')
        data = data.dropna()
        
        if isinstance(data['Close'], pd.DataFrame):
            data['Close'] = data['Close'].squeeze()
            
        return data
    except Exception as e:
        st.error(f"Error downloading data for {ticker}: {str(e)}")
        return None

# [Rest of your existing functions (calculate_indicators, etc.) remain the same...]

def main():
    tickers_df = load_tickers(uploaded_file)
    
    if tickers_df is not None:
        tickers_df['Full_Symbol'] = tickers_df['Symbol'] + '.' + tickers_df['Exchange']
        selected_ticker = st.selectbox("Select a ticker to analyze", tickers_df['Full_Symbol'])
        
        # Get the proper yfinance symbol
        selected_row = tickers_df[tickers_df['Full_Symbol'] == selected_ticker].iloc[0]
        base_symbol = selected_row['YFinance_Symbol']
        
        stock_data = load_stock_data(base_symbol, start_date, end_date)
        
        if stock_data is not None:
            stock_data = calculate_indicators(stock_data)
            
            # [Rest of your existing display logic...]

if __name__ == "__main__":
    main()
