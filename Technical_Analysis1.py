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
    .sheet-selector {
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
        type=["xlsx"],
        accept_multiple_files=False
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

def get_sheet_names(uploaded_file):
    if uploaded_file is not None:
        try:
            # Reset file pointer to beginning
            uploaded_file.seek(0)
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
            # Reset file pointer to beginning
            uploaded_file.seek(0)
            df = pd.read_excel(uploaded_file, sheet_name=selected_sheet)
            
            if 'Symbol' not in df.columns or 'Exchange' not in df.columns:
                st.error("The selected sheet must contain 'Symbol' and 'Exchange' columns.")
                return None
            
            df['YFinance_Symbol'] = df.apply(lambda row: 
                f"{row['Symbol']}.HK" if row['Exchange'] == 'HKEX' else 
                f"{row['Symbol']}", axis=1)
            
            df['Display_Name'] = df.apply(lambda row: 
                f"{row['Symbol']}.HK" if row['Exchange'] == 'HKEX' else 
                f"{row['Symbol']}.{row['Exchange']}", axis=1)
            
            return df
        except Exception as e:
            st.error(f"Error reading sheet {selected_sheet}: {e}")
            return None
    return None

# [Rest of your existing functions remain unchanged...]

def main():
    # Get sheet names first (not cached)
    sheet_names = get_sheet_names(uploaded_file)
    
    # Debug information
    if uploaded_file:
        st.sidebar.info(f"File uploaded: {uploaded_file.name}")
    
    # Let user select which sheet to use (outside cached function)
    if len(sheet_names) > 1:
        selected_sheet = st.selectbox("Select sheet to use", sheet_names, key="sheet_selector")
        st.markdown(f"<div class='sheet-selector'>Using sheet: <strong>{selected_sheet}</strong></div>", unsafe_allow_html=True)
    elif len(sheet_names) == 1:
        selected_sheet = sheet_names[0]
    else:
        selected_sheet = None
    
    if len(sheet_names) > 1:
        st.info(f"Available sheets: {', '.join(sheet_names)}")
    
    # Load tickers from selected sheet (cached)
    tickers_df = load_tickers_from_sheet(uploaded_file, selected_sheet)
    
    if tickers_df is not None:
        selected_display = st.selectbox("Select a ticker to analyze", tickers_df['Display_Name'])
        selected_row = tickers_df[tickers_df['Display_Name'] == selected_display].iloc[0]
        base_symbol = selected_row['YFinance_Symbol']
        
        stock_data = load_stock_data(base_symbol, start_date, end_date)
        
        if stock_data is not None:
            stock_data = calculate_indicators(stock_data)
            
            # [Rest of your existing display logic remains unchanged...]
    
    else:
        if uploaded_file is not None:
            st.info("Please select a valid sheet with 'Symbol' and 'Exchange' columns")
        else:
            st.info("Please upload an XLSX file with 'Symbol' and 'Exchange' columns to begin.")

if __name__ == "__main__":
    main()
