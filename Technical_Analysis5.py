import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import ta  # Technical analysis library
from io import BytesIO
import numpy as np
import requests
from datetime import datetime, timedelta

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
    .company-comparison {
        margin-top: 30px;
    }
    .intraday-warning {
        background-color: #fff3cd;
        padding: 10px;
        border-radius: 5px;
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
    
    st.header("OR")
    manual_ticker = st.text_input("Enter a single ticker (e.g. SPY, AAPL, 9618.HK)", 
                                help="For HKEX stocks use format XXXX.HK (e.g. 9618.HK)")
    
    st.header("Analysis Settings")
    analysis_type = st.radio("Analysis Type", ["Single Company", "Multi-Company Compare"])
    data_granularity = st.radio("Data Granularity", ["Daily", "Intraday (15min)"], 
                               help="Intraday data available for last 60 days only")
    start_date = st.date_input("Start date", pd.to_datetime("2020-01-01"))
    end_date = st.date_input("End date", pd.to_datetime("today"))
    
    st.header("Technical Indicators")
    show_sma = st.checkbox("Show SMA (20, 50)", value=True)
    show_ema = st.checkbox("Show EMA (20)", value=True)
    show_rsi = st.checkbox("Show RSI (14)", value=True)
    show_macd = st.checkbox("Show MACD", value=True)
    show_bollinger = st.checkbox("Show Bollinger Bands", value=True)

# Get sheet names from uploaded file
def get_sheet_names(uploaded_file):
    if uploaded_file is not None:
        try:
            xls = pd.ExcelFile(uploaded_file)
            return xls.sheet_names
        except Exception as e:
            st.error(f"Error reading file: {e}")
            return []
    return []

# Load ticker data from specific sheet
@st.cache_data
def load_tickers_from_sheet(uploaded_file, selected_sheet):
    if uploaded_file is not None and selected_sheet is not None:
        try:
            df = pd.read_excel(uploaded_file, sheet_name=selected_sheet)
            
            if 'Symbol' not in df.columns or 'Exchange' not in df.columns:
                st.error("The selected sheet must contain 'Symbol' and 'Exchange' columns.")
                return None
            
            # Create proper symbols for yfinance based on exchange
            df['YFinance_Symbol'] = df.apply(lambda row: 
                f"{row['Symbol']}.HK" if row['Exchange'] == 'HKEX' else 
                f"{row['Symbol']}", axis=1)
            
            # Create display names (without double .HK)
            df['Display_Name'] = df.apply(lambda row: 
                f"{row['Symbol']}.HK" if row['Exchange'] == 'HKEX' else 
                f"{row['Symbol']}.{row['Exchange']}", axis=1)
            
            return df
        except Exception as e:
            st.error(f"Error reading sheet {selected_sheet}: {e}")
            return None
    return None

# Download stock data from Yahoo Finance with enhanced intraday handling
@st.cache_data
def load_stock_data(ticker, start_date, end_date, granularity="Daily"):
    try:
        # Remove any duplicate .HK suffix if present
        if ticker.endswith('.HK.HK'):
            ticker = ticker.replace('.HK.HK', '.HK')
            
        if granularity == "Intraday (15min)":
            # For intraday data, limit to last 60 days and adjust dates accordingly
            max_start_date = datetime.now() - timedelta(days=60)
            
            if start_date < max_start_date.date():
                new_start = max_start_date.date()
                st.markdown(f"""
                <div class='intraday-warning'>
                ⚠️ Intraday data limited to last 60 days. <br>
                Adjusted start date from {start_date} to {new_start}
                </div>
                """, unsafe_allow_html=True)
                start_date = new_start
            
            if end_date > datetime.now().date():
                new_end = datetime.now().date()
                st.markdown(f"""
                <div class='intraday-warning'>
                ⚠️ Intraday data cannot be in the future. <br>
                Adjusted end date from {end_date} to {new_end}
                </div>
                """, unsafe_allow_html=True)
                end_date = new_end
            
            # Add buffer days to ensure we get complete data
            buffer_start = start_date - timedelta(days=2)
            data = yf.download(ticker, start=buffer_start, end=end_date, interval="15m", progress=False)
            
            # Filter to the exact requested date range
            if not data.empty:
                mask = (data.index >= pd.to_datetime(start_date)) & (data.index <= pd.to_datetime(end_date))
                data = data.loc[mask]
        else:
            # For daily data, no special handling needed
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
            
        if data.empty:
            st.error(f"No data found for {ticker}. Please verify:")
            st.error("- For HKEX stocks, use format 'XXXX.HK' (e.g., '9618.HK')")
            st.error("- Check if the ticker exists on Yahoo Finance")
            return None
        
        # Ensure we have numeric data and proper formatting
        data = data.apply(pd.to_numeric, errors='coerce')
        data = data.dropna()
        
        # Ensure Close prices are properly formatted
        if isinstance(data['Close'], pd.DataFrame):
            data['Close'] = data['Close'].squeeze()
            
        return data
    except Exception as e:
        st.error(f"Error downloading data for {ticker}: {e}")
        return None

# Enhanced Google Finance data fetcher with intraday support
def get_google_finance_data(ticker, start_date, end_date, granularity="Daily"):
    try:
        if granularity == "Intraday (15min)":
            # Google Finance doesn't officially support intraday API, so we'll use a different approach
            st.warning("Google Finance intraday data is not reliably available. Using Yahoo Finance instead.")
            return load_stock_data(ticker, start_date, end_date, granularity)
        
        # For daily data, use the traditional Google Finance API
        # Convert dates to timestamp format
        period1 = int(datetime.combine(start_date, datetime.min.time()).timestamp())
        period2 = int(datetime.combine(end_date, datetime.min.time()).timestamp())
        
        url = f"https://finance.google.com/finance/getprices?q={ticker}&x=NASD&i=86400&p=40Y&f=d,c,v,k,o,h,l&df=cpct"
        response = requests.get(url)
        
        if response.status_code != 200:
            return None
            
        lines = response.text.split('\n')
        data = []
        base_date = None
        
        for line in lines[7:]:  # Skip header lines
            if not line:
                continue
                
            cols = line.split(',')
            if cols[0].startswith('a'):  # New base date
                base_date = datetime.fromtimestamp(int(cols[0][1:]))
                data.append([base_date, float(cols[1]), float(cols[2]), float(cols[3]), 
                           float(cols[4]), float(cols[5]), float(cols[6])])
            else:
                offset = int(cols[0])
                current_date = base_date + timedelta(days=offset)
                data.append([current_date, float(cols[1]), float(cols[2]), float(cols[3]), 
                           float(cols[4]), float(cols[5]), float(cols[6])])
        
        df = pd.DataFrame(data, columns=['Date', 'Close', 'High', 'Low', 'Open', 'Volume', 'Adj Close'])
        df.set_index('Date', inplace=True)
        
        # Filter by date range
        mask = (df.index >= pd.to_datetime(start_date)) & (df.index <= pd.to_datetime(end_date))
        df = df.loc[mask]
        
        return df if not df.empty else None
    except Exception as e:
        st.error(f"Error fetching Google Finance data: {e}")
        return None

# Calculate technical indicators with proper data formatting
def calculate_indicators(df, granularity="Daily"):
    if df is None or df.empty:
        return df
    
    # Create a copy to avoid SettingWithCopyWarning
    df = df.copy()
    
    try:
        # Ensure Close prices are properly formatted as 1D pandas Series
        close_prices = df['Close'].squeeze()  # Convert to Series if it's a DataFrame column
        
        # Adjust window sizes for intraday data
        if granularity == "Intraday (15min)":
            # For intraday data, use shorter windows that make sense for higher frequency data
            sma_window_short = 20 * 6.5  # ~1 trading day (6.5 hours/day * 4 15min intervals/hour)
            sma_window_long = 20 * 6.5 * 5  # ~1 trading week
            ema_window = 20 * 6.5  # ~1 trading day
            rsi_window = 14  # Keep same for intraday
        else:
            # For daily data, use standard windows
            sma_window_short = 20
            sma_window_long = 50
            ema_window = 20
            rsi_window = 14
        
        # Moving Averages
        if show_sma:
            df['SMA_20'] = ta.trend.sma_indicator(close=close_prices, window=int(sma_window_short))
            df['SMA_50'] = ta.trend.sma_indicator(close=close_prices, window=int(sma_window_long))
        
        if show_ema:
            df['EMA_20'] = ta.trend.ema_indicator(close=close_prices, window=int(ema_window))
        
        # RSI
        if show_rsi:
            df['RSI_14'] = ta.momentum.rsi(close=close_prices, window=rsi_window)
        
        # MACD
        if show_macd:
            macd = ta.trend.MACD(close=close_prices)
            df['MACD'] = macd.macd()
            df['MACD_Signal'] = macd.macd_signal()
            df['MACD_Hist'] = macd.macd_diff()
        
        # Bollinger Bands
        if show_bollinger:
            bb = ta.volatility.BollingerBands(close=close_prices)
            df['BB_Upper'] = bb.bollinger_hband()
            df['BB_Lower'] = bb.bollinger_lband()
        
        return df
    except Exception as e:
        st.error(f"Error calculating indicators: {str(e)}")
        return df

# Plot price chart for a single company
def plot_single_price_chart(stock_data, selected_display, granularity="Daily"):
    st.subheader(f"{selected_display} Price Chart ({granularity})")
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
    
    ax.set_title(f"{selected_display} Price Chart ({granularity})")
    ax.legend()
    ax.grid(True)
    
    # Format x-axis differently for intraday data
    if granularity == "Intraday (15min)":
        fig.autofmt_xdate()
        # Show fewer x-axis labels for cleaner display
        ax.xaxis.set_major_locator(plt.MaxNLocator(10))
    
    st.pyplot(fig)

# Plot comparison chart for multiple companies
def plot_comparison_chart(comparison_data, selected_companies, granularity="Daily"):
    st.subheader(f"Price Comparison ({granularity})")
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Normalize prices to percentage change for fair comparison
    for company in selected_companies:
        if company in comparison_data:
            normalized_prices = (comparison_data[company]['Close'] / comparison_data[company]['Close'].iloc[0]) * 100
            ax.plot(comparison_data[company].index, normalized_prices, label=company)
    
    ax.set_title(f"Normalized Price Comparison (Base=100) ({granularity})")
    ax.legend()
    ax.grid(True)
    
    # Format x-axis differently for intraday data
    if granularity == "Intraday (15min)":
        fig.autofmt_xdate()
        # Show fewer x-axis labels for cleaner display
        ax.xaxis.set_major_locator(plt.MaxNLocator(10))
    
    st.pyplot(fig)

# Display metrics for a single company
def display_single_metrics(stock_data, selected_display, granularity="Daily"):
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

# Display comparison metrics for multiple companies
def display_comparison_metrics(comparison_data, selected_companies, granularity="Daily"):
    st.subheader(f"Comparison Metrics ({granularity})")
    
    # Create metrics for each company
    metrics = []
    for company in selected_companies:
        if company in comparison_data:
            data = comparison_data[company]
            if not data.empty:
                try:
                    last_close = float(data['Close'].iloc[-1])
                    prev_close = float(data['Close'].iloc[-2]) if len(data) > 1 else last_close
                    change = last_close - prev_close
                    pct_change = (change / prev_close) * 100 if prev_close != 0 else 0
                    last_volume = int(data['Volume'].iloc[-1])
                    
                    metrics.append({
                        'Company': company,
                        'Price': f"${last_close:.2f}",
                        'Change': f"${change:.2f}",
                        'Pct Change': f"{pct_change:.2f}%",
                        'Volume': f"{last_volume:,}"
                    })
                except Exception as e:
                    st.error(f"Error processing metrics for {company}: {str(e)}")
    
    if metrics:
        st.table(pd.DataFrame(metrics))
    else:
        st.warning("No metrics available for the selected companies")

# Main app logic
def main():
    # Get sheet names first (not cached)
    sheet_names = get_sheet_names(uploaded_file)
    
    # Let user select which sheet to use (outside cached function)
    if len(sheet_names) > 1:
        selected_sheet = st.selectbox("Select sheet to use", sheet_names, key="sheet_selector")
        st.markdown(f"<div class='sheet-selector'>Using sheet: <strong>{selected_sheet}</strong></div>", unsafe_allow_html=True)
    elif len(sheet_names) == 1:
        selected_sheet = sheet_names[0]
    else:
        selected_sheet = None
    
    # Show available sheets info
    if len(sheet_names) > 1:
        st.info(f"Available sheets: {', '.join(sheet_names)}")
    
    # Load tickers from selected sheet (cached) or use manual ticker
    if manual_ticker and not uploaded_file:
        # Create a dummy DataFrame for manual ticker entry
        tickers_df = pd.DataFrame({
            'Symbol': [manual_ticker],
            'Exchange': ['MANUAL'],
            'YFinance_Symbol': [manual_ticker],
            'Display_Name': [manual_ticker]
        })
        analysis_type = "Single Company"  # Force single company mode for manual entry
    else:
        tickers_df = load_tickers_from_sheet(uploaded_file, selected_sheet)
    
    if tickers_df is not None:
        if analysis_type == "Single Company":
            # Single company analysis mode
            if manual_ticker and not uploaded_file:
                selected_display = manual_ticker
                base_symbol = manual_ticker
            else:
                selected_display = st.selectbox("Select a ticker to analyze", tickers_df['Display_Name'])
                selected_row = tickers_df[tickers_df['Display_Name'] == selected_display].iloc[0]
                base_symbol = selected_row['YFinance_Symbol']
            
            # Data source selection
            data_source = st.radio("Data Source", ["Yahoo Finance", "Google Finance"], 
                                 help="Google Finance may have limited historical data")
            
            if data_source == "Yahoo Finance":
                stock_data = load_stock_data(base_symbol, start_date, end_date, data_granularity)
            else:
                stock_data = get_google_finance_data(base_symbol, start_date, end_date, data_granularity)
            
            if stock_data is not None:
                stock_data = calculate_indicators(stock_data, data_granularity)
                display_single_metrics(stock_data, selected_display, data_granularity)
                
                if not stock_data.empty:
                    plot_single_price_chart(stock_data, selected_display, data_granularity)
                    
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
                                st.markdown("**MACD Indicator**")
                                fig_macd, ax_macd = plt.subplots(figsize=(12, 3))
                                ax_macd.plot(stock_data.index, stock_data['MACD'], label='MACD', color='blue')
                                ax_macd.plot(stock_data.index, stock_data['MACD_Signal'], label='Signal', color='orange')
                                ax_macd.bar(stock_data.index, stock_data['MACD_Hist'], label='Histogram', color='gray', alpha=0.5)
                                ax_macd.axhline(0, color='black', linestyle='-', alpha=0.5)
                                ax_macd.legend()
                                ax_macd.grid(True)
                                st.pyplot(fig_macd)
                    
                    # Show data
                    st.subheader("Recent Data")
                    st.dataframe(stock_data.tail(20))
                    
                    # Download option
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
        
        elif analysis_type == "Multi-Company Compare":
            # Multi-company comparison mode
            if manual_ticker and not uploaded_file:
                st.warning("Multi-company comparison requires an uploaded file with multiple tickers")
            else:
                st.markdown("<div class='company-comparison'>", unsafe_allow_html=True)
                selected_companies = st.multiselect(
                    "Select companies to compare (2-5)", 
                    tickers_df['Display_Name'],
                    default=tickers_df['Display_Name'].head(2).tolist()
                )
                
                if len(selected_companies) < 2:
                    st.warning("Please select at least 2 companies for comparison")
                elif len(selected_companies) > 5:
                    st.warning("Please select no more than 5 companies for better visualization")
                else:
                    comparison_data = {}
                    for company in selected_companies:
                        selected_row = tickers_df[tickers_df['Display_Name'] == company].iloc[0]
                        base_symbol = selected_row['YFinance_Symbol']
                        stock_data = load_stock_data(base_symbol, start_date, end_date, data_granularity)
                        
                        if stock_data is not None:
                            comparison_data[company] = stock_data
                    
                    if len(comparison_data) >= 2:
                        display_comparison_metrics(comparison_data, selected_companies, data_granularity)
                        plot_comparison_chart(comparison_data, selected_companies, data_granularity)
                
                st.markdown("</div>", unsafe_allow_html=True)
    
    else:
        if not manual_ticker:
            if uploaded_file is not None:
                st.info("Please select a valid sheet with 'Symbol' and 'Exchange' columns")
            else:
                st.info("Please upload an XLSX file or enter a ticker manually to begin.")

if __name__ == "__main__":
    main()
