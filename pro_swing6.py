import streamlit as st
import pandas as pd
import yfinance as yf
from ta import add_all_ta_features
import time
import matplotlib.pyplot as plt
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURATION ---
CONFIG = {
    'DEFAULT_PERIOD': '6mo',
    'DEFAULT_INTERVAL': '1d',
    'MIN_DATA_ROWS': 15,
    'SCORE_WEIGHTS': {
        'RSI': 0.5,
        'MACD': 0.25,
        'BB': 0.25,
        'VOLUME': 0.1
    },
    'DEFAULT_UNIVERSE': [
        'AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 
        'TSLA', 'NVDA', 'PYPL', 'ADBE', 'NFLX'
    ],
    'MAX_WORKERS': 5,
    'TIME_FRAMES': ['1d', '1wk']
}

# --- UTILITIES ---
@st.cache_data(ttl=3600)  # Cache for 1 hour
def clean_tickers(ticker_list):
    """
    Clean and standardize a list of ticker symbols.
    
    Args:
        ticker_list (list): List of ticker symbols
        
    Returns:
        list: Cleaned list of unique ticker symbols in uppercase
    """
    return (
        pd.Series(ticker_list)
        .dropna()
        .astype(str)
        .str.replace(r'^"|"$', '', regex=True)
        .str.strip()
        .str.upper()
        .unique()
        .tolist()
    )

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_stock_data(ticker, period='6mo', interval='1d'):
    """
    Download stock data and calculate technical indicators.
    
    Args:
        ticker (str): Stock ticker symbol
        period (str): Time period for data
        interval (str): Data interval
        
    Returns:
        DataFrame: Processed stock data with technical indicators
    """
    try:
        data = yf.download(ticker, period=period, interval=interval, progress=False)
    except Exception as e:
        if "No data found" in str(e):
            print(f"No data available for {ticker}")
        elif "symbol may be delisted" in str(e):
            print(f"Ticker {ticker} may be delisted")
        else:
            print(f"Error downloading {ticker}: {e}")
        return pd.DataFrame()

    # Flatten MultiIndex columns if present
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(-1)
        if len(data.columns) == 5 and len(set(data.columns)) == 1:
            data.columns = ['Open', 'High', 'Low', 'Close', 'Volume']

    if data.empty or len(data) < 2:
        return pd.DataFrame()

    if len(data) < CONFIG['MIN_DATA_ROWS']:
        return pd.DataFrame()

    try:
        # Calculate moving averages for trend analysis
        data['MA20'] = data['Close'].rolling(window=20).mean()
        data['MA50'] = data['Close'].rolling(window=50).mean()
        data['MA200'] = data['Close'].rolling(window=200).mean()

        # Add all technical indicators
        data = add_all_ta_features(
            data, open="Open", high="High", low="Low", close="Close", volume="Volume"
        )

        # MACD Cross Detection
        if 'trend_macd' in data and 'trend_macd_signal' in data:
            macd = data['trend_macd']
            signal = data['trend_macd_signal']
            macd_prev = macd.shift(1)
            signal_prev = signal.shift(1)
            data['macd_cross'] = np.where(
                (macd_prev < signal_prev) & (macd > signal), 'cross up',
                np.where((macd_prev > signal_prev) & (macd < signal), 'cross down', '')
            )

    except Exception as e:
        print(f"TA error for {ticker}: {e}")
        return pd.DataFrame()
    
    return data

def calculate_opportunity_score(data):
    """
    Calculate a composite opportunity score based on multiple technical indicators.
    
    Args:
        data (DataFrame): DataFrame containing technical indicators
        
    Returns:
        float: Opportunity score between 0-100, higher values indicate stronger opportunities
        
    Scoring Breakdown:
    - RSI: 50% weight (closer to middle = better)
    - MACD: 25% weight (positive values = better)
    - Bollinger %B: 25% weight (closer to middle = better)
    - Volume: 10% weight (higher volume = better)
    """
    if data.empty:
        return 0
    
    weights = CONFIG['SCORE_WEIGHTS']
    score = 0
    
    # RSI scoring (50 is neutral)
    rsi = data['momentum_rsi'].iloc[-1] if 'momentum_rsi' in data else float('nan')
    if not pd.isna(rsi):
        score += (100 - abs(rsi - 50)) * weights['RSI']
    
    # MACD scoring (positive is better)
    macd = data['trend_macd_diff'].iloc[-1] if 'trend_macd_diff' in data else float('nan')
    if not pd.isna(macd):
        score += (macd * 100) * weights['MACD']
    
    # Bollinger Band scoring (0.5 is middle)
    bbp = data['volatility_bbp'].iloc[-1] if 'volatility_bbp' in data else float('nan')
    if not pd.isna(bbp):
        score += (100 - abs(bbp - 0.5) * 200) * weights['BB']
    
    # Volume scoring (relative to 20-day average)
    if 'Volume' in data:
        volume_ma = data['Volume'].rolling(20).mean().iloc[-1]
        volume_ratio = data['Volume'].iloc[-1] / volume_ma if volume_ma > 0 else 1
        score += min(volume_ratio * 10, 10) * weights['VOLUME']
    
    return round(score, 1)

def generate_strategy(data):
    """
    Generate trading strategy based on technical indicators.
    
    Args:
        data (DataFrame): DataFrame containing stock data and indicators
        
    Returns:
        dict: Dictionary containing entry rules, exit rules, stop loss and take profit levels
    """
    entry, exit = [], []
    stop_loss, take_profit = None, None
    
    if not data.empty:
        # Get indicator values
        rsi = data['momentum_rsi'].iloc[-1] if 'momentum_rsi' in data else None
        macd = data['trend_macd_diff'].iloc[-1] if 'trend_macd_diff' in data else None
        bbp = data['volatility_bbp'].iloc[-1] if 'volatility_bbp' in data else None
        close = data['Close'].iloc[-1]
        
        # Trend analysis
        ma20 = data['MA20'].iloc[-1] if 'MA20' in data else None
        ma50 = data['MA50'].iloc[-1] if 'MA50' in data else None
        ma200 = data['MA200'].iloc[-1] if 'MA200' in data else None
        
        if all(v is not None for v in [close, ma20, ma50, ma200]):
            if close > ma20 > ma50 > ma200:
                entry.append("Strong Uptrend (Price > 20MA > 50MA > 200MA)")
            elif close < ma20 < ma50 < ma200:
                entry.append("Strong Downtrend (Price < 20MA < 50MA < 200MA)")
        
        # RSI rules
        if rsi is not None:
            if rsi < 35: 
                entry.append(f"RSI ({rsi:.1f}) < 35 (Oversold)")
            elif rsi > 65: 
                entry.append(f"RSI ({rsi:.1f}) > 65 (Overbought)")
            
            if rsi < 30 or rsi > 70: 
                exit.append(f"RSI crosses {'40' if rsi<30 else '60'}")
        
        # MACD rules
        if macd is not None:
            entry.append("MACD positive" if macd > 0 else "MACD negative")
            exit.append("MACD crosses signal line (opp. dir)")
        
        # Bollinger Band rules
        if bbp is not None:
            if bbp < 0.2: 
                entry.append("Price near lower Bollinger Band")
            elif bbp > 0.8: 
                entry.append("Price near upper Bollinger Band")
        
        # Risk management
        atr = data['volatility_atr'].iloc[-1] if 'volatility_atr' in data else None
        if atr is not None:
            stop_loss = f"{close - atr * 1.5:.2f} (1.5x ATR)"
            take_profit = f"{close + atr * 3:.2f} (3x ATR)"
    
    return {
        'entry_rules': entry,
        'exit_rules': exit,
        'stop_loss': stop_loss,
        'take_profit': take_profit
    }

def process_ticker(ticker, period):
    """Helper function for parallel processing"""
    try:
        data = get_stock_data(ticker, period)
        if not data.empty:
            score = calculate_opportunity_score(data)
            strategy = generate_strategy(data)
            if score is not None and strategy is not None:
                return {
                    'Ticker': ticker,
                    'Score': score,
                    'Price': data['Close'].iloc[-1],
                    'Change %': (data['Close'].iloc[-1] / data['Close'].iloc[-2] - 1) * 100,
                    'Volume': data['Volume'].iloc[-1],
                    'RSI': data['momentum_rsi'].iloc[-1] if 'momentum_rsi' in data else float('nan'),
                    'MACD': data['trend_macd_diff'].iloc[-1] if 'trend_macd_diff' in data else float('nan'),
                    'MACD Cross': data['macd_cross'].iloc[-1] if 'macd_cross' in data else '',
                    'BB %': data['volatility_bbp'].iloc[-1] * 100 if 'volatility_bbp' in data else float('nan'),
                    'Strategy': strategy
                }
    except Exception as e:
        print(f"Error processing {ticker}: {e}")
    return None

def scan_universe(universe, period='6mo'):
    """
    Scan a universe of tickers for trading opportunities.
    
    Args:
        universe (list): List of ticker symbols to scan
        period (str): Time period for data
        
    Returns:
        tuple: (DataFrame of results, list of failed tickers)
    """
    results = []
    failed = []
    
    with st.spinner(f"Scanning {len(universe)} stocks..."):
        progress_bar = st.progress(0)
        
        with ThreadPoolExecutor(max_workers=CONFIG['MAX_WORKERS']) as executor:
            futures = {executor.submit(process_ticker, ticker, period): ticker for ticker in universe}
            
            for i, future in enumerate(as_completed(futures)):
                ticker = futures[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    failed.append(ticker)
                    st.warning(f"Error processing {ticker}: {str(e)}")
                
                progress_bar.progress((i + 1) / len(universe))
    
    if not results:
        return pd.DataFrame(columns=['Ticker', 'Score', 'Price', 'Change %', 'Volume', 'RSI', 'MACD', 'MACD Cross', 'BB %', 'Strategy']), failed
    
    return pd.DataFrame(results).sort_values('Score', ascending=False), failed

# --- UI CONFIG ---
st.set_page_config(
    page_title="Swing Trading Scanner Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- UNIVERSE & UPLOAD ---
uploaded_file = st.file_uploader(
    "Upload an Excel file (.xlsx) with a column named 'Ticker' or 'Symbol'", 
    type=["xlsx"]
)

excel_ticker_list = None
if uploaded_file:
    df_excel = pd.read_excel(uploaded_file)
    ticker_col = next((col for col in df_excel.columns if col.lower() in ['ticker', 'symbol']), None)
    if ticker_col:
        excel_ticker_list = clean_tickers(df_excel[ticker_col].tolist())
        st.success(f"Loaded {len(excel_ticker_list)} tickers from Excel: {ticker_col}")
    else:
        st.error("Could not find 'Ticker' or 'Symbol' column.")

st.session_state.watchlist = excel_ticker_list or clean_tickers(CONFIG['DEFAULT_UNIVERSE'])

# --- SIDEBAR FILTERS ---
st.sidebar.title("Swing Trading Scanner Pro")
st.sidebar.subheader("Configuration")

with st.sidebar.expander("Scan Settings", expanded=True):
    time_frame = st.selectbox("Time Frame", CONFIG['TIME_FRAMES'])
    min_score = st.slider("Minimum Quality Score", 0, 100, 18)
    max_results = st.slider("Max Results", 5, 50, 15)

st.sidebar.markdown("#### Current Universe")
for ticker in st.session_state.watchlist:
    st.sidebar.write(f"- {ticker}")

# --- MAIN PAGE ---
if st.sidebar.button("Run Scan", type="primary"):
    results, failed = scan_universe(
        st.session_state.watchlist,
        period=CONFIG['DEFAULT_PERIOD']
    )
    
    # Filter by minimum score
    results = results[results['Score'] >= min_score]
    
    st.session_state.scanned_results = results.head(max_results) if not results.empty else results
    st.session_state.failed_tickers = failed

if "scanned_results" in st.session_state and not st.session_state.scanned_results.empty:
    st.subheader("Scan Results")
    st.dataframe(st.session_state.scanned_results)
    
    if 'failed_tickers' in st.session_state and st.session_state.failed_tickers:
        st.warning(f"Failed to fetch data for {len(st.session_state.failed_tickers)} tickers. See list below:")
        with st.expander("Show Failed Tickers"):
            st.write(st.session_state.failed_tickers)
else:
    st.info("Click 'Run Scan' to find swing trading opportunities")

# --- Single Ticker Data Test (Diagnostics) ---
with st.expander("Single Ticker Data Test (Diagnostics)", expanded=False):
    ticker = st.text_input(
        "Test a ticker",
        value="",
        placeholder="e.g. MC.PA, AAPL, ORA.PA, SAN.PA"
    )
    
    period = st.selectbox("Test period", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=2, key='test_period')
    interval = st.selectbox("Test interval", CONFIG['TIME_FRAMES'], index=0, key='test_interval')
    
    if st.button("Fetch Ticker Data"):
        if not ticker:
            st.warning("Please enter a ticker symbol.")
        else:
            st.write(f"**Ticker:** {ticker}  \n**Period:** {period}  \n**Interval:** {interval}")
            
            data = yf.download(ticker, period=period, interval=interval, progress=False)
            
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(-1)
                if len(data.columns) == 5 and len(set(data.columns)) == 1:
                    data.columns = ['Open', 'High', 'Low', 'Close', 'Volume']

            st.write("Raw Yahoo data:")
            st.write(data.tail(10))

            if data.empty:
                st.error("No data returned! This ticker/interval/period combo is not supported by Yahoo, or market is closed.")
            elif len(data) < CONFIG['MIN_DATA_ROWS']:
                st.warning(f"Not enough data to compute indicators (need at least {CONFIG['MIN_DATA_ROWS']} rows, got {len(data)})")
            else:
                # Calculate moving averages
                data['MA20'] = data['Close'].rolling(window=20).mean()
                data['MA50'] = data['Close'].rolling(window=50).mean()
                data['MA200'] = data['Close'].rolling(window=200).mean()
                
                # Calculate Bollinger Bands
                data['BB_Middle'] = data['Close'].rolling(window=20).mean()
                data['BB_Std'] = data['Close'].rolling(window=20).std()
                data['BB_Upper'] = data['BB_Middle'] + 2 * data['BB_Std']
                data['BB_Lower'] = data['BB_Middle'] - 2 * data['BB_Std']
                
                # Add technical indicators
                try:
                    ta_data = add_all_ta_features(
                        data, open="Open", high="High", low="Low", close="Close", volume="Volume"
                    )
                    
                    # MACD Cross Detection
                    if 'trend_macd' in ta_data and 'trend_macd_signal' in ta_data:
                        macd = ta_data['trend_macd']
                        signal = ta_data['trend_macd_signal']
                        macd_prev = macd.shift(1)
                        signal_prev = signal.shift(1)
                        ta_data['macd_cross'] = np.where(
                            (macd_prev < signal_prev) & (macd > signal), 'cross up',
                            np.where((macd_prev > signal_prev) & (macd < signal), 'cross down', '')
                        )
                    
                    # Create comprehensive visualization
                    fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(12, 14), sharex=True)
                    
                    # Price chart with MAs and Bollinger Bands
                    ax1.plot(data.index, data['Close'], label='Close Price', color='black')
                    ax1.plot(data.index, data['MA20'], label='20-day MA', color='blue', alpha=0.7)
                    ax1.plot(data.index, data['MA50'], label='50-day MA', color='green', alpha=0.7)
                    ax1.plot(data.index, data['MA200'], label='200-day MA', color='red', alpha=0.7)
                    ax1.plot(data.index, data['BB_Upper'], label='Bollinger Upper', linestyle='--', color='magenta', alpha=0.7)
                    ax1.plot(data.index, data['BB_Lower'], label='Bollinger Lower', linestyle='--', color='cyan', alpha=0.7)
                    ax1.fill_between(data.index, data['BB_Lower'], data['BB_Upper'], color='gray', alpha=0.1)
                    ax1.set_title(f"{ticker} Price Analysis")
                    ax1.legend(loc='upper left')
                    
                    # Volume chart
                    ax2.bar(data.index, data['Volume'], label='Volume', color='blue', alpha=0.5)
                    ax2.plot(data.index, data['Volume'].rolling(20).mean(), label='20-day Avg Volume', color='red')
                    ax2.set_title('Volume')
                    ax2.legend(loc='upper left')
                    
                    # RSI chart
                    if 'momentum_rsi' in ta_data:
                        ax3.plot(ta_data.index, ta_data['momentum_rsi'], label='RSI', color='purple')
                        ax3.axhline(70, linestyle='--', color='red', alpha=0.7)
                        ax3.axhline(30, linestyle='--', color='green', alpha=0.7)
                        ax3.set_title('RSI (14)')
                        ax3.legend(loc='upper left')
                    
                    # MACD chart
                    if 'trend_macd' in ta_data and 'trend_macd_signal' in ta_data:
                        ax4.plot(ta_data.index, ta_data['trend_macd'], label='MACD', color='blue')
                        ax4.plot(ta_data.index, ta_data['trend_macd_signal'], label='Signal', color='red')
                        ax4.bar(ta_data.index, ta_data['trend_macd_diff'], label='Histogram', color='gray', alpha=0.3)
                        
                        # Highlight crosses
                        cross_up = ta_data[ta_data['macd_cross'] == 'cross up'].index
                        cross_down = ta_data[ta_data['macd_cross'] == 'cross down'].index
                        ax4.scatter(cross_up, ta_data.loc[cross_up, 'trend_macd'], color='green', marker='^', label='Bullish Cross')
                        ax4.scatter(cross_down, ta_data.loc[cross_down, 'trend_macd'], color='red', marker='v', label='Bearish Cross')
                        
                        ax4.set_title('MACD (12,26,9)')
                        ax4.legend(loc='upper left')
                    
                    plt.tight_layout()
                    st.pyplot(fig)
                    
                    # Show technical data
                    st.write("With TA features (last 5 rows):")
                    st.write(ta_data.tail())
                    
                    # Show MACD cross events
                    st.write("MACD Cross Events (last 20 rows):")
                    st.write(ta_data[['Close', 'trend_macd', 'trend_macd_signal', 'macd_cross']].tail(20))
                    
                    # Calculate and display opportunity score
                    score = calculate_opportunity_score(ta_data)
                    st.write(f"**Opportunity Score:** {score}")
                    
                    # Display strategy
                    strategy = generate_strategy(ta_data)
                    st.write("**Suggested Strategy:**")
                    st.write("**Entry Rules:**")
                    st.write(strategy['entry_rules'])
                    st.write("**Exit Rules:**")
                    st.write(strategy['exit_rules'])
                    st.write(f"**Stop Loss:** {strategy['stop_loss']}")
                    st.write(f"**Take Profit:** {strategy['take_profit']}")
                    
                except Exception as e:
                    st.warning(f"TA error: {e}")
