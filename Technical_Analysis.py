import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import ta  # Technical analysis library
from io import BytesIO

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
    start_date = st.date_input("Start date", pd.to_datetime("2020-01-01"))
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
            # Read the Excel file
            df = pd.read_excel(uploaded_file)
            
            # Check if required columns exist
            if 'Symbol' not in df.columns or 'Exchange' not in df.columns:
                st.error("The uploaded file must contain 'Symbol' and 'Exchange' columns.")
                return None
            
            return df
        except Exception as e:
            st.error(f"Error reading file: {e}")
            return None
    return None

# Download stock data
@st.cache_data
def load_stock_data(ticker, start_date, end_date):
    try:
        data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if data.empty:
            st.error(f"No data found for {ticker}")
            return None
        
        # Ensure the data is clean and has the required columns
        if 'Close' not in data.columns:
            st.error(f"Data for {ticker} doesn't contain 'Close' prices")
            return None
            
        return data
    except Exception as e:
        st.error(f"Error downloading data for {ticker}: {e}")
        return None

# Calculate technical indicators
def calculate_indicators(df):
    # Make a copy to avoid modifying the original dataframe
    df = df.copy()
    
    # Ensure we have enough data points for calculations
    if len(df) < 50:
        st.warning("Insufficient data points for some indicators (need at least 50)")
    
    try:
        # Moving Averages
        if show_sma:
            df['SMA_20'] = ta.trend.sma_indicator(df['Close'], window=20)
            df['SMA_50'] = ta.trend.sma_indicator(df['Close'], window=50)
        
        if show_ema:
            df['EMA_20'] = ta.trend.ema_indicator(df['Close'], window=20)
        
        # RSI
        if show_rsi:
            df['RSI_14'] = ta.momentum.rsi(df['Close'], window=14)
        
        # MACD
        if show_macd:
            macd = ta.trend.MACD(df['Close'])
            df['MACD'] = macd.macd()
            df['MACD_Signal'] = macd.macd_signal()
            df['MACD_Hist'] = macd.macd_diff()
        
        # Bollinger Bands
        if show_bollinger:
            bollinger = ta.volatility.BollingerBands(df['Close'])
            df['BB_Upper'] = bollinger.bollinger_hband()
            df['BB_Lower'] = bollinger.bollinger_lband()
        
        return df
    except Exception as e:
        st.error(f"Error calculating indicators: {e}")
        return df  # Return the original df if indicator calculation fails

# Main app logic
def main():
    # Load tickers if file is uploaded
    tickers_df = load_tickers(uploaded_file)
    
    if tickers_df is not None:
        st.success(f"Successfully loaded {len(tickers_df)} tickers")
        
        # Create full ticker symbol (Symbol.Exchange)
        tickers_df['Full_Symbol'] = tickers_df['Symbol'] + '.' + tickers_df['Exchange']
        
        # Select ticker
        selected_ticker = st.selectbox(
            "Select a ticker to analyze",
            tickers_df['Full_Symbol']
        )
        
        # Get base symbol without exchange for yfinance
        base_symbol = selected_ticker.split('.')[0]
        
        # Download stock data
        stock_data = load_stock_data(base_symbol, start_date, end_date)
        
        if stock_data is not None:
            # Calculate indicators
            stock_data = calculate_indicators(stock_data)
            
            # Display basic info
            st.subheader(f"Technical Analysis for {selected_ticker}")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Current Price", f"${stock_data['Close'].iloc[-1]:.2f}")
            with col2:
                change = stock_data['Close'].iloc[-1] - stock_data['Close'].iloc[-2]
                pct_change = (change / stock_data['Close'].iloc[-2]) * 100
                st.metric("Daily Change", f"${change:.2f}", f"{pct_change:.2f}%")
            with col3:
                st.metric("Volume", f"{stock_data['Volume'].iloc[-1]:,}")
            
            # Plot price chart
            st.subheader("Price Chart")
            fig, ax = plt.subplots(figsize=(12, 6))
            ax.plot(stock_data.index, stock_data['Close'], label='Close Price', color='blue')
            
            if show_sma and 'SMA_20' in stock_data.columns:
                ax.plot(stock_data.index, stock_data['SMA_20'], label='SMA 20', color='orange', alpha=0.7)
                ax.plot(stock_data.index, stock_data['SMA_50'], label='SMA 50', color='green', alpha=0.7)
            
            if show_ema and 'EMA_20' in stock_data.columns:
                ax.plot(stock_data.index, stock_data['EMA_20'], label='EMA 20', color='purple', alpha=0.7)
            
            if show_bollinger and 'BB_Upper' in stock_data.columns:
                ax.plot(stock_data.index, stock_data['BB_Upper'], label='Upper Bollinger Band', color='red', alpha=0.5, linestyle='--')
                ax.plot(stock_data.index, stock_data['BB_Lower'], label='Lower Bollinger Band', color='red', alpha=0.5, linestyle='--')
                ax.fill_between(stock_data.index, stock_data['BB_Lower'], stock_data['BB_Upper'], color='red', alpha=0.1)
            
            ax.set_title(f"{selected_ticker} Price and Moving Averages")
            ax.set_xlabel("Date")
            ax.set_ylabel("Price")
            ax.legend()
            ax.grid(True)
            st.pyplot(fig)
            
            # Plot indicators
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
                        st.markdown("**Moving Average Convergence Divergence (MACD)**")
                        fig_macd, ax_macd = plt.subplots(figsize=(12, 3))
                        ax_macd.plot(stock_data.index, stock_data['MACD'], label='MACD', color='blue')
                        ax_macd.plot(stock_data.index, stock_data['MACD_Signal'], label='Signal', color='orange')
                        ax_macd.bar(stock_data.index, stock_data['MACD_Hist'], label='Histogram', color='gray', alpha=0.5)
                        ax_macd.axhline(0, color='black', linestyle='-', alpha=0.5)
                        ax_macd.legend()
                        ax_macd.grid(True)
                        st.pyplot(fig_macd)
            
            # Show raw data
            st.subheader("Raw Data")
            st.dataframe(stock_data.tail(20))
            
            # Download button for the analyzed data
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                stock_data.to_excel(writer, sheet_name='Technical_Analysis')
            output.seek(0)
            
            st.download_button(
                label="Download Analysis Data",
                data=output,
                file_name=f"{selected_ticker}_technical_analysis.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    else:
        st.info("Please upload an XLSX file with 'Symbol' and 'Exchange' columns to begin.")

if __name__ == "__main__":
    main()
