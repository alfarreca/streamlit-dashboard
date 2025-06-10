import streamlit as st
import pandas as pd
import time

# --- XLSX Upload Section ---
uploaded_file = st.sidebar.file_uploader("Upload XLSX Watchlist", type=["xlsx"])
if uploaded_file is not None:
    df_uploaded = pd.read_excel(uploaded_file)
    if 'Ticker' in df_uploaded.columns:
        st.session_state.watchlist = df_uploaded['Ticker'].dropna().astype(str).tolist()
        st.success("Watchlist updated from uploaded file!")
    else:
        st.error("No 'Ticker' column found in uploaded file.")

# --- Initialize watchlist if not set ---
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ['AAPL', 'GOOG', 'TSLA']

# --- Mocked/Required Constants & Functions (Replace with your actual logic) ---
ACCOUNT_EQUITY = 10000
RISK_PER_TRADE = 0.01
MAX_CONCURRENT_TRADES = 3

def get_stock_data(ticker, period='6mo'):
    # Dummy data for demonstration, replace with your real function
    idx = pd.date_range(end=pd.Timestamp.today(), periods=30)
    return pd.DataFrame({
        'momentum_rsi': [30 + i % 10 for i in range(30)],
        'trend_macd_diff': [0.5 - 0.03*i for i in range(30)],
        'volatility_bbp': [0.2 + 0.01*i for i in range(30)],
        'Close': [100 + i for i in range(30)],
        'volatility_atr': [2 + 0.1*i for i in range(30)],
        'Volume': [100000 + 500*i for i in range(30)],
    }, index=idx)

def get_higher_tf_data(ticker):
    idx = pd.date_range(end=pd.Timestamp.today(), periods=200)
    return pd.DataFrame({
        'MA50': [100 + i*0.2 for i in range(200)],
        'MA200': [95 + i*0.18 for i in range(200)],
    }, index=idx)

# --- SIDEBAR FILTERS WITH ADJUSTABLE THRESHOLDS ---
st.sidebar.title("Swing Trading Scanner Pro (Adjustable)")
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

st.sidebar.markdown("#### Current Universe")
for ticker in st.session_state.watchlist:
    st.sidebar.write(f"- {ticker}")

# --- ADJUSTABLE STRATEGY FUNCTION ---
def adjustable_swing_strategy(
    data, higher_tf, active_trades,
    rsi_thresh=rsi_thresh, macd_thresh=macd_thresh, bbp_thresh=bbp_thresh,
    vol_filter=vol_filter, weekly_ma_filter=weekly_ma_filter,
    account_equity=ACCOUNT_EQUITY, risk_per_trade=RISK_PER_TRADE
):
    if data.empty or (weekly_ma_filter and higher_tf.empty):
        return {
            'Trade': False, 'Reason': 'Insufficient data', 'PositionSize': 0, 'StopLoss': None, 'TakeProfit': None,
            'EntryPrice': None, 'EntrySignal': '', 'ExitSignal': ''
        }
    rsi = data['momentum_rsi'].iloc[-1]
    macd = data['trend_macd_diff'].iloc[-1]
    bbp = data['volatility_bbp'].iloc[-1]
    close = data['Close'].iloc[-1]
    atr = data['volatility_atr'].iloc[-1]
    volume = data['Volume'].iloc[-1]
    avg_vol = data['Volume'].rolling(20).mean().iloc[-1]

    uptrend = True  # Default to True if filter is off
    if weekly_ma_filter:
        uptrend = False
        if not higher_tf.empty and len(higher_tf) >= 200:
            ma50 = higher_tf['MA50'].iloc[-1]
            ma200 = higher_tf['MA200'].iloc[-1]
            uptrend = (ma50 > ma200)

    vol_ok = True if not vol_filter else (volume > avg_vol)

    entry_signal = (
        (rsi < rsi_thresh) and
        (macd > macd_thresh) and
        (bbp < bbp_thresh) and
        vol_ok and
        uptrend and
        (active_trades < MAX_CONCURRENT_TRADES)
    )

    stop_loss = close - 1.5 * atr if atr > 0 else None
    take_profit = close + 3 * atr if atr > 0 else None
    risk_per_share = close - stop_loss if stop_loss is not None else None
    pos_size = int((account_equity * risk_per_trade) / risk_per_share) if (risk_per_share and risk_per_share > 0) else 0

    prev_rsi = data['momentum_rsi'].iloc[-2] if len(data) > 1 else None
    prev_macd = data['trend_macd_diff'].iloc[-2] if len(data) > 1 else None
    exit_signal = (
        ((prev_rsi is not None and prev_rsi < 50 and rsi >= 50)) or
        ((prev_macd is not None and prev_macd > 0 and macd <= 0))
    )
    exit_descr = "RSI crosses 50, MACD crosses <0, or stop/TP hit"

    descr = f"RSI<{rsi_thresh}, MACD>{macd_thresh}, BB%<{bbp_thresh}" \
            f"{', Vol>Avg' if vol_filter else ''}" \
            f"{', Uptrend(Weekly)' if weekly_ma_filter else ''}"

    return {
        'Trade': entry_signal,
        'Reason': 'All adjustable criteria met' if entry_signal else 'Did not meet entry criteria',
        'PositionSize': pos_size if entry_signal else 0,
        'StopLoss': stop_loss if entry_signal else None,
        'TakeProfit': take_profit if entry_signal else None,
        'EntryPrice': close if entry_signal else None,
        'EntrySignal': descr if entry_signal else '',
        'ExitSignal': exit_descr if entry_signal else ''
    }

# --- MAIN PAGE (ADJUSTED) ---
if st.sidebar.button("Run Adjustable Scan", type="primary"):
    results = []
    failed = []
    active_trades = 0
    with st.spinner(f"Scanning {len(st.session_state.watchlist)} stocks (adjustable rules)..."):
        progress_bar = st.progress(0)
        for i, ticker in enumerate(st.session_state.watchlist):
            try:
                data = get_stock_data(ticker, period='6mo')
                higher_tf = get_higher_tf_data(ticker) if weekly_ma_filter else pd.DataFrame()
                strat = adjustable_swing_strategy(
                    data, higher_tf, active_trades,
                    rsi_thresh, macd_thresh, bbp_thresh,
                    vol_filter, weekly_ma_filter,
                    account_equity=ACCOUNT_EQUITY, risk_per_trade=RISK_PER_TRADE
                )
                if strat['Trade']:
                    active_trades += 1
                results.append({
                    'Ticker': ticker,
                    'Trade Signal': 'TRADE' if strat['Trade'] else '',
                    'Reason': strat['Reason'],
                    'Entry Price': strat['EntryPrice'],
                    'Position Size': strat['PositionSize'],
                    'Stop Loss': strat['StopLoss'],
                    'Take Profit': strat['TakeProfit'],
                    'Entry Signal': strat['EntrySignal'],
                    'Exit Signal': strat['ExitSignal'],
                })
            except Exception as e:
                st.warning(f"Error processing {ticker}: {str(e)}")
                failed.append(ticker)
                continue
            progress_bar.progress((i + 1) / len(st.session_state.watchlist))
            time.sleep(0.08)
        st.session_state.scanned_results = pd.DataFrame(results)
        st.session_state.failed_tickers = failed

if "scanned_results" in st.session_state and not st.session_state.scanned_results.empty:
    st.subheader("Adjustable Scan Results")
    st.dataframe(st.session_state.scanned_results)
    if 'failed_tickers' in st.session_state and st.session_state.failed_tickers:
        st.warning(f"Failed to fetch data for {len(st.session_state.failed_tickers)} tickers. See list below:")
        with st.expander("Show Failed Tickers"):
            st.write(st.session_state.failed_tickers)
else:
    st.info("Click 'Run Adjustable Scan' to scan for swing trades with your chosen thresholds.")
