import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import ta  # Technical analysis library
from io import BytesIO
import numpy as np
import traceback

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
    .error-box {
        background-color: #ffebee;
        border-left: 4px solid #f44336;
        padding: 12px;
        margin: 10px 0;
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
            uploaded_file.seek(0)
            df = pd.read_excel(uploaded_file, sheet_name=selected_sheet)
            
            required_columns = {'Symbol', 'Exchange'}
            if not required_columns.issubset(df.columns):
                missing = required_columns - set(df.columns)
                st.error(f"Missing required columns: {', '.join(missing)}")
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

@st.cache_data
def load_stock_data(ticker, start_date, end_date):
    try:
        if not ticker:
            st.error("No ticker symbol provided")
            return None
            
        # Clean ticker symbol
        ticker = str(ticker).strip()
        if ticker.endswith('.HK.HK'):
            ticker = ticker.replace('.HK.HK', '.HK')
        
        # Convert dates to string format expected by yfinance
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        st.info(f"Fetching data for {ticker} from {start_str} to {end_str}...")
        
        data = yf.download(ticker, start=start_str, end=end_str, progress=False)
        
        if data.empty:
            st.error(f"No data found for {ticker}. Possible reasons:")
            st.error("- Ticker symbol might be incorrect")
            st.error("- No data available for the selected date range")
            st.error("- Yahoo Finance doesn't have data for this ticker")
            return None
        
        # Ensure numeric data and proper formatting
        numeric_cols = ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
        for col in numeric_cols:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
        
        data = data.dropna()
        
        if isinstance(data['Close'], pd.DataFrame):
            data['Close'] = data['Close'].squeeze()
            
        return data
    except Exception as e:
        st.error(f"Error downloading data for {ticker}: {str(e)}")
        return None

def calculate_indicators(df):
    if df is None or df.empty:
        return df
    
    df = df.copy()
    
    try:
        close_prices = df['Close'].squeeze()
        
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
        
        return df
    except Exception as e:
        st.error(f"Error calculating indicators: {str(e)}")
        return df

def main():
    try:
        sheet_names = get_sheet_names(uploaded_file)
        
        if uploaded_file:
            st.sidebar.success(f"File loaded: {uploaded_file.name}")
        
        if len(sheet_names) > 1:
            selected_sheet = st.selectbox("Select sheet to use", sheet_names, key="sheet_selector")
            st.markdown(f"<div class='sheet-selector'>Using sheet: <strong>{selected_sheet}</strong></div>", unsafe_allow_html=True)
        elif len(sheet_names) == 1:
            selected_sheet = sheet_names[0]
        else:
            selected_sheet = None
        
        if len(sheet_names) > 1:
            st.info(f"Available sheets: {', '.join(sheet_names)}")
        
        tickers_df = load_tickers_from_sheet(uploaded_file, selected_sheet)
        
        if tickers_df is not None:
            selected_display = st.selectbox("Select a ticker to analyze", tickers_df['Display_Name'])
            selected_row = tickers_df[tickers_df['Display_Name'] == selected_display].iloc[0]
            base_symbol = selected_row['YFinance_Symbol']
            
            stock_data = load_stock_data(base_symbol, start_date, end_date)
            
            if stock_data is not None:
                stock_data = calculate_indicators(stock_data)
                
                try:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        last_close = float(stock_data['Close'].iloc[-1]) if not stock_data.empty else np.nan
                        st.metric(f"{selected_display} Current Price", 
                                 f"${last_close:.2f}" if not np.isnan(last_close) else "N/A")
                    
                    with col2:
                        if len(stock_data) > 1:
                            prev_close = float(stock_data['Close'].iloc[-2])
                            change = float(stock_data['Close'].iloc[-1]) - prev_close
                            pct_change = (change / prev_close) * 100
                            st.metric("Daily Change", f"${change:.2f}", f"{pct_change:.2f}%")
                        else:
                            st.metric("Daily Change", "N/A")
                    
                    with col3:
                        last_volume = int(stock_data['Volume'].iloc[-1]) if not stock_data.empty else 0
                        st.metric("Volume", f"{last_volume:,}" if last_volume > 0 else "N/A")
                
                except Exception as e:
                    st.error(f"Error displaying metrics: {str(e)}")
                
                if not stock_data.empty:
                    try:
                        st.subheader(f"{selected_display} Price Chart")
                        fig, ax = plt.subplots(figsize=(12, 6))
                        ax.plot(stock_data.index, stock_data['Close'], label='Close Price', color='blue')
                        
                        if show_sma and 'SMA_20' in stock_data.columns:
                            ax.plot(stock_data.index, stock_data['SMA_20'], label='SMA 20', color='orange', alpha=0.7)
                            ax.plot(stock_data.index, stock_data['SMA_50'], label='SMA 50', color='green', alpha=0.7)
                        
                        if show_ema and 'EMA_20' in stock_data.columns:
                            ax.plot(stock_data.index, stock_data['EMA_20'], label='EMA 20', color='purple', alpha=0.7)
                        
                        if show_bollinger and 'BB_Upper' in stock_data.columns:
                            ax.plot(stock_data.index, stock_data['BB_Upper'], label='Upper Band', color='red', alpha=0.5, linestyle='--')
                            ax.plot(stock_data.index, stock_data['BB_Lower'], label='Lower Band', color='red', alpha=0.5, linestyle='--')
                            ax.fill_between(stock_data.index, stock_data['BB_Lower'], stock_data['BB_Upper'], color='red', alpha=0.1)
                        
                        ax.set_title(f"{selected_display} Price Chart")
                        ax.legend()
                        ax.grid(True)
                        st.pyplot(fig)
                        
                        if show_rsi or show_macd:
                            st.subheader("Technical Indicators")
                            cols = st.columns(2)
                            
                            if show_rsi and 'RSI_14' in stock_data.columns:
                                with cols[0]:
                                    st.markdown("**Relative Strength Index (RSI)**")
                                    fig_rsi, ax_rsi = plt.subplots(figsize=(12, 3))
                                    ax_rsi.plot(stock_data.index, stock_data['RSI_14'], label='RSI 14', color='blue')
                                    ax_rsi.axhline(70, color='red', linestyle='--', alpha=0.5)
                                    ax_rsi.axhline(30, color='green', linestyle='--', alpha=0.5)
                                    ax_rsi.set_ylim(0, 100)
                                    ax_rsi.legend()
                                    ax_rsi.grid(True)
                                    st.pyplot(fig_rsi)
                            
                            if show_macd and 'MACD' in stock_data.columns:
                                with cols[1]:
                                    st.markdown("**MACD Indicator**")
                                    fig_macd, ax_macd = plt.subplots(figsize=(12, 3))
                                    ax_macd.plot(stock_data.index, stock_data['MACD'], label='MACD', color='blue')
                                    ax_macd.plot(stock_data.index, stock_data['MACD_Signal'], label='Signal', color='orange')
                                    ax_macd.bar(stock_data.index, stock_data['MACD_Hist'], label='Histogram', color='gray', alpha=0.5)
                                    ax_macd.axhline(0, color='black', linestyle='-', alpha=0.5)
                                    ax_macd.legend()
                                    ax_macd.grid(True)
                                    st.pyplot(fig_macd)
                        
                        st.subheader("Recent Data")
                        st.dataframe(stock_data.tail(20))
                        
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                            stock_data.to_excel(writer, sheet_name='Technical_Analysis')
                        output.seek(0)
                        
                        st.download_button(
                            label="Download Analysis Data",
                            data=output,
                            file_name=f"{selected_display.replace('.', '_')}_analysis.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    
                    except Exception as e:
                        st.error(f"Error plotting charts: {str(e)}")
    
    except Exception as e:
        st.markdown(f"""
        <div class="error-box">
            <h4>An error occurred:</h4>
            <p>{str(e)}</p>
        </div>
        """, unsafe_allow_html=True)
        st.error("Please check your input and try again")
        st.stop()

if __name__ == "__main__":
    main()
