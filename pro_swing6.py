import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from ta import add_all_ta_features
import time

# --- CONFIGURABLES ---
ACCOUNT_EQUITY = 10_000
RISK_PER_TRADE = 0.01
MAX_CONCURRENT_TRADES = 3

# --- UTILITIES ---
def get_stock_data(ticker, period='6mo'):
    data = yf.download(ticker, period=period, interval='1d', progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(-1)
    if data.empty or len(data) < 20:
        return pd.DataFrame()
    try:
        data = add_all_ta_features(
            data, open="Open", high="High", low="Low", close="Close", volume="Volume"
        )
    except Exception as e:
        st.warning(f"TA error for {ticker}: {e}")
        return pd.DataFrame()
    return data

def get_higher_tf_data(ticker, period='2y'):
    data = yf.download(ticker, period=period, interval='1wk', progress=False)
    if data.empty or len(data) < 60:
        return pd.DataFrame()
    data['MA50'] = data['Close'].rolling(window=50).mean()
    data['MA200'] = data['Close'].rolling(window=200).mean()
    return data

# --- UI & UPLOAD ---
st.set_page_config(page_title="Swing Trading Scanner Pro", page_icon="📈", layout="wide")
st.title("Swing Trading Scanner Pro")

if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ['AAPL', 'GOOG', 'TSLA']
if 'scanned_results' not in st.session_state:
    st.session_state.scanned_results = pd.DataFrame()
if 'failed_tickers' not in st.session_state:
    st.session_state.failed_tickers = []

st.sidebar.title("Swing Trading Scanner Pro (Adjustable)")

uploaded_file = st.sidebar.file_uploader(
    "Upload XLSX Watchlist", type=["xlsx"],
    help="Upload Excel file with 'Symbol' column"
)
if uploaded_file is not None:
    try:
        df_uploaded = pd.read_excel(uploaded_file)
        if 'Symbol' in df_uploaded.columns:
            st.session_state.watchlist = (
                df_uploaded['Symbol']
                .dropna()
                .astype(str)
                .str.upper()
                .unique()
                .tolist()
            )
            st.sidebar.success(f"Watchlist updated with {len(st.session_state.watchlist)} unique symbols!")
        else:
            st.sidebar.error("Uploaded file must contain a 'Symbol' column")
    except Exception as e:
        st.sidebar.error(f"Error reading file: {str(e)}")

# --- SIDEBAR FILTERS ---
st.sidebar.subheader("Trade Management")
account_equity = st.sidebar.number_input("Account Equity (€)", min_value=1000, max_value=1_000_000, value=ACCOUNT_EQUITY, step=1000)
risk_per_trade = st.sidebar.slider("Risk per trade (%)", 0.5, 5.0, RISK_PER_TRADE*100, step=0.1) / 100
max_concurrent_trades = st.sidebar.slider("Max concurrent trades", 1, 20, MAX_CONCURRENT_TRADES)

st.sidebar.subheader("Entry Criteria (Adjustable)")
rsi_thresh = st.sidebar.slider("RSI Threshold (max value to trigger entry)", 20, 50, 35)
macd_thresh = st.sidebar.slider("MACD Threshold (min value to trigger entry)", -2.0, 2.0, 0.0, step=0.1)
bbp_thresh = st.sidebar.slider("BB% Threshold (max value to trigger entry)", 0.0, 0.5, 0.2, step=0.01)
vol_filter = st.sidebar.checkbox("Require above average volume?", value=True)
weekly_ma_filter = st.sidebar.checkbox("Require weekly MA50 > MA200 uptrend?", value=True)

st.sidebar.markdown("#### Current Watchlist")
if st.session_state.watchlist:
    for ticker in st.session_state.watchlist[:30]:  # show up to 30 in sidebar
        st.sidebar.code(ticker)
    if len(st.session_state.watchlist) > 30:
        st.sidebar.markdown(f"...(+{len(st.session_state.watchlist) - 30} more)")
else:
    st.sidebar.warning("Watchlist is empty - upload a file or add symbols")

# --- STRATEGY LOGIC ---
def adjustable_swing_strategy(
    data, higher_tf, active_trades,
    rsi_thresh, macd_thresh, bbp_thresh,
    vol_filter, weekly_ma_filter,
    account_equity, risk_per_trade,
    max_concurrent_trades
):
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
    if data.empty or len(data) < 2:
        return response
    if weekly_ma_filter and (higher_tf.empty or len(higher_tf) < 200):
        response['Reason'] = 'Insufficient higher timeframe data'
        return response
    current = data.iloc[-1]
    prev = data.iloc[-2]
    rsi = current['momentum_rsi']
    macd = current['trend_macd_diff']
    bbp = current['volatility_bbp']
    close = current['Close']
    atr = current['volatility_atr']
    volume = current['Volume']
    avg_vol = data['Volume'].rolling(20).mean().iloc[-1]
    uptrend = True
    if weekly_ma_filter:
        ma50 = higher_tf['MA50'].iloc[-1]
        ma200 = higher_tf['MA200'].iloc[-1]
        uptrend = (ma50 > ma200)
    vol_ok = not vol_filter or (volume > avg_vol)
    entry_signal = all([
        (rsi < rsi_thresh),
        (macd > macd_thresh),
        (bbp < bbp_thresh),
        vol_ok,
        uptrend,
        (active_trades < max_concurrent_trades)
    ])
    if entry_signal:
        stop_loss = close - 1.5 * atr
        take_profit = close + 3 * atr
        risk_per_share = close - stop_loss
        pos_size = int((account_equity * risk_per_trade) / risk_per_share) if risk_per_share > 0 else 0
        exit_descr = "RSI crosses 50, MACD crosses <0, or stop/TP hit"
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
if st.sidebar.button("Run Adjustable Scan", type="primary"):
    results = []
    st.session_state.failed_tickers = []
    active_trades = 0
    tickers = st.session_state.watchlist
    with st.spinner(f"Scanning {len(tickers)} stocks (real Yahoo data)..."):
        progress_bar = st.progress(0)
        for i, ticker in enumerate(tickers):
            try:
                data = get_stock_data(ticker)
                higher_tf = get_higher_tf_data(ticker) if weekly_ma_filter else pd.DataFrame()
                strat = adjustable_swing_strategy(
                    data, higher_tf, active_trades,
                    rsi_thresh, macd_thresh, bbp_thresh,
                    vol_filter, weekly_ma_filter,
                    account_equity, risk_per_trade,
                    max_concurrent_trades
                )
                if strat['Trade']:
                    active_trades += 1
                results.append({
                    'Symbol': ticker,
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
            progress_bar.progress((i + 1) / len(tickers))
            time.sleep(0.1)  # Sleep for API friendliness
        st.session_state.scanned_results = pd.DataFrame(results)
        st.success("Scan completed!")

if not st.session_state.scanned_results.empty:
    st.subheader("Scan Results")
    buy_signals = st.session_state.scanned_results[st.session_state.scanned_results['Signal'] == 'BUY']
    other_results = st.session_state.scanned_results[st.session_state.scanned_results['Signal'] != 'BUY']
    if not buy_signals.empty:
        st.success(f"Found {len(buy_signals)} potential trades:")
        st.dataframe(buy_signals)
        for _, row in buy_signals.iterrows():
            with st.expander(f"Trade Details: {row['Symbol']}"):
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
        st.warning(f"Failed to process {len(st.session_state.failed_tickers)} symbols")
        with st.expander("Show failed symbols"):
            st.write(st.session_state.failed_tickers)
else:
    st.info("Configure your scan criteria and click 'Run Adjustable Scan' to begin")
