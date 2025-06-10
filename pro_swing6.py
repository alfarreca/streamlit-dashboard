import streamlit as st
import pandas as pd
import time

# --- Initialize session state ---
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ['AAPL', 'GOOG', 'TSLA']
if 'scanned_results' not in st.session_state:
    st.session_state.scanned_results = pd.DataFrame()
if 'failed_tickers' not in st.session_state:
    st.session_state.failed_tickers = []

# --- XLSX Upload Section with improved validation ---
st.sidebar.title("Swing Trading Scanner Pro (Adjustable)")
uploaded_file = st.sidebar.file_uploader("Upload XLSX Watchlist", type=["xlsx"], 
                                        help="Upload Excel file with 'Ticker' column")

if uploaded_file is not None:
    try:
        df_uploaded = pd.read_excel(uploaded_file)
        if 'Ticker' in df_uploaded.columns:
            st.session_state.watchlist = (
                df_uploaded['Ticker']
                .dropna()
                .astype(str)
                .str.upper()  # Ensure consistent ticker formatting
                .unique()  # Remove duplicates
                .tolist()
            )
            st.sidebar.success(f"Watchlist updated with {len(st.session_state.watchlist)} unique tickers!")
        else:
            st.sidebar.error("Uploaded file must contain a 'Ticker' column")
    except Exception as e:
        st.sidebar.error(f"Error reading file: {str(e)}")

# --- Mocked/Required Constants & Functions ---
ACCOUNT_EQUITY = 10000
RISK_PER_TRADE = 0.01
MAX_CONCURRENT_TRADES = 3

def get_stock_data(ticker, period='6mo'):
    """Mock stock data function - replace with real API calls"""
    try:
        idx = pd.date_range(end=pd.Timestamp.today(), periods=30)
        return pd.DataFrame({
            'momentum_rsi': [30 + i % 10 for i in range(30)],
            'trend_macd_diff': [0.5 - 0.03*i for i in range(30)],
            'volatility_bbp': [0.2 + 0.01*i for i in range(30)],
            'Close': [100 + i for i in range(30)],
            'volatility_atr': [2 + 0.1*i for i in range(30)],
            'Volume': [100000 + 500*i for i in range(30)],
        }, index=idx)
    except Exception as e:
        st.warning(f"Error generating mock data for {ticker}: {str(e)}")
        return pd.DataFrame()

def get_higher_tf_data(ticker):
    """Mock higher timeframe data - replace with real API calls"""
    try:
        idx = pd.date_range(end=pd.Timestamp.today(), periods=200)
        return pd.DataFrame({
            'MA50': [100 + i*0.2 for i in range(200)],
            'MA200': [95 + i*0.18 for i in range(200)],
        }, index=idx)
    except Exception as e:
        st.warning(f"Error generating higher TF data for {ticker}: {str(e)}")
        return pd.DataFrame()

# --- SIDEBAR FILTERS ---
st.sidebar.subheader("Configuration")

with st.sidebar.expander("Trade Management", expanded=True):
    st.write(f"Account Equity: €{ACCOUNT_EQUITY:,}")
    st.write(f"Risk per trade: {int(RISK_PER_TRADE*100)}%")
    st.write(f"Max concurrent trades: {MAX_CONCURRENT_TRADES}")

with st.sidebar.expander("Entry Criteria (Adjustable)", expanded=True):
    rsi_thresh = st.slider("RSI Threshold (max value to trigger entry)", 20, 50, 35)
    macd_thresh = st.slider("MACD Threshold (min value to trigger entry)", -2.0, 2.0, 0.0, step=0.1)
    bbp_thresh = st.slider("BB% Threshold (max value to trigger entry)", 0.0, 0.5, 0.2, step=0.01)
    vol_filter = st.checkbox("Require above average volume?", value=True)
    weekly_ma_filter = st.checkbox("Require weekly MA50 > MA200 uptrend?", value=True)

st.sidebar.markdown("#### Current Watchlist")
if st.session_state.watchlist:
    for ticker in st.session_state.watchlist:
        st.sidebar.code(ticker)
else:
    st.sidebar.warning("Watchlist is empty - upload a file or add tickers")

# --- Improved Strategy Function ---
def adjustable_swing_strategy(
    data, higher_tf, active_trades,
    rsi_thresh, macd_thresh, bbp_thresh,
    vol_filter, weekly_ma_filter,
    account_equity=ACCOUNT_EQUITY, risk_per_trade=RISK_PER_TRADE
):
    # Initialize default response
    response = {
        'Trade': False, 
        'Reason': 'Insufficient data', 
        'PositionSize': 0, 
        'StopLoss': None, 
        'TakeProfit': None,
        'EntryPrice': None, 
        'EntrySignal': '', 
        'ExitSignal': ''
    }
    
    # Check for valid data
    if data.empty or len(data) < 2:
        return response
    
    if weekly_ma_filter and (higher_tf.empty or len(higher_tf) < 200):
        response['Reason'] = 'Insufficient higher timeframe data'
        return response
    
    # Get current values
    current = data.iloc[-1]
    prev = data.iloc[-2]
    
    rsi = current['momentum_rsi']
    macd = current['trend_macd_diff']
    bbp = current['volatility_bbp']
    close = current['Close']
    atr = current['volatility_atr']
    volume = current['Volume']
    avg_vol = data['Volume'].rolling(20).mean().iloc[-1]

    # Check uptrend condition if filter is enabled
    uptrend = True
    if weekly_ma_filter:
        ma50 = higher_tf['MA50'].iloc[-1]
        ma200 = higher_tf['MA200'].iloc[-1]
        uptrend = (ma50 > ma200)
    
    # Check volume condition if filter is enabled
    vol_ok = not vol_filter or (volume > avg_vol)
    
    # Check entry conditions
    entry_signal = all([
        (rsi < rsi_thresh),
        (macd > macd_thresh),
        (bbp < bbp_thresh),
        vol_ok,
        uptrend,
        (active_trades < MAX_CONCURRENT_TRADES)
    ])
    
    # Calculate trade parameters if entry is signaled
    if entry_signal:
        stop_loss = close - 1.5 * atr
        take_profit = close + 3 * atr
        risk_per_share = close - stop_loss
        pos_size = int((account_equity * risk_per_trade) / risk_per_share) if risk_per_share > 0 else 0
        
        # Exit conditions
        exit_descr = "RSI crosses 50, MACD crosses <0, or stop/TP hit"
        
        # Entry description
        descr = f"RSI<{rsi_thresh}, MACD>{macd_thresh}, BB%<{bbp_thresh}"
        if vol_filter:
            descr += ", Vol>Avg"
        if weekly_ma_filter:
            descr += ", Uptrend(Weekly)"
            
        response.update({
            'Trade': True,
            'Reason': 'All adjustable criteria met',
            'PositionSize': pos_size,
            'StopLoss': stop_loss,
            'TakeProfit': take_profit,
            'EntryPrice': close,
            'EntrySignal': descr,
            'ExitSignal': exit_descr
        })
    else:
        response['Reason'] = 'Did not meet entry criteria'
    
    return response

# --- MAIN PAGE ---
st.title("Swing Trading Scanner Pro")

if st.sidebar.button("Run Adjustable Scan", type="primary"):
    results = []
    st.session_state.failed_tickers = []
    active_trades = 0
    
    if not st.session_state.watchlist:
        st.warning("Watchlist is empty - upload a file or add tickers")
    else:
        with st.spinner(f"Scanning {len(st.session_state.watchlist)} stocks..."):
            progress_bar = st.progress(0)
            
            for i, ticker in enumerate(st.session_state.watchlist):
                try:
                    data = get_stock_data(ticker)
                    higher_tf = get_higher_tf_data(ticker) if weekly_ma_filter else pd.DataFrame()
                    
                    strat = adjustable_swing_strategy(
                        data, higher_tf, active_trades,
                        rsi_thresh, macd_thresh, bbp_thresh,
                        vol_filter, weekly_ma_filter
                    )
                    
                    if strat['Trade']:
                        active_trades += 1
                    
                    results.append({
                        'Ticker': ticker,
                        'Signal': 'BUY' if strat['Trade'] else '-',
                        'Reason': strat['Reason'],
                        'Price': f"{strat['EntryPrice']:.2f}" if strat['EntryPrice'] else '-',
                        'Size': strat['PositionSize'] or '-',
                        'Stop': f"{strat['StopLoss']:.2f}" if strat['StopLoss'] else '-',
                        'Target': f"{strat['TakeProfit']:.2f}" if strat['TakeProfit'] else '-',
                        'Conditions': strat['EntrySignal'],
                        'Exit Rules': strat['ExitSignal']
                    })
                except Exception as e:
                    st.session_state.failed_tickers.append(ticker)
                    continue
                
                progress_bar.progress((i + 1) / len(st.session_state.watchlist))
                time.sleep(0.05)  # Reduced sleep time
            
            st.session_state.scanned_results = pd.DataFrame(results)
            st.success("Scan completed!")

# Display results
if not st.session_state.scanned_results.empty:
    st.subheader("Scan Results")
    
    # Separate buy signals from other results
    buy_signals = st.session_state.scanned_results[st.session_state.scanned_results['Signal'] == 'BUY']
    other_results = st.session_state.scanned_results[st.session_state.scanned_results['Signal'] != 'BUY']
    
    if not buy_signals.empty:
        st.success(f"Found {len(buy_signals)} potential trades:")
        st.dataframe(buy_signals)
        
        # Show trade details in expanders
        for _, row in buy_signals.iterrows():
            with st.expander(f"Trade Details: {row['Ticker']}"):
                st.write(f"**Entry Price:** {row['Price']}")
                st.write(f"**Position Size:** {row['Size']} shares")
                st.write(f"**Stop Loss:** {row['Stop']}")
                st.write(f"**Take Profit:** {row['Target']}")
                st.write(f"**Entry Conditions:** {row['Conditions']}")
                st.write(f"**Exit Rules:** {row['Exit Rules']}")
    
    if not other_results.empty:
        st.write(f"\nOther results ({len(other_results)}):")
        st.dataframe(other_results)
    
    if st.session_state.failed_tickers:
        st.warning(f"Failed to process {len(st.session_state.failed_tickers)} tickers")
        with st.expander("Show failed tickers"):
            st.write(st.session_state.failed_tickers)
else:
    st.info("Configure your scan criteria and click 'Run Adjustable Scan' to begin")
