import streamlit as st
import pandas as pd
import yfinance as yf
from ta import add_all_ta_features
import time
import matplotlib.pyplot as plt
import numpy as np

# --- CONFIG ---
ACCOUNT_EQUITY = 10_000
RISK_PER_TRADE = 0.02
MAX_CONCURRENT_TRADES = 5

def clean_tickers(ticker_list):
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

def get_stock_data(ticker, period='6mo', interval='1d'):
    data = yf.download(ticker, period=period, interval=interval)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(-1)
        if len(data.columns) == 5 and len(set(data.columns)) == 1:
            data.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    if data.empty or len(data) < 20:
        return pd.DataFrame()
    try:
        data = add_all_ta_features(
            data, open="Open", high="High", low="Low", close="Close", volume="Volume"
        )
    except Exception as e:
        print(f"TA error for {ticker}: {e}")
        return pd.DataFrame()
    return data

def get_higher_tf_data(ticker, period='2y', interval='1wk'):
    data = yf.download(ticker, period=period, interval=interval)
    if data.empty or len(data) < 60:
        return pd.DataFrame()
    data['MA50'] = data['Close'].rolling(window=50).mean()
    data['MA200'] = data['Close'].rolling(window=200).mean()
    return data

def strict_swing_strategy(data, higher_tf, active_trades, account_equity=ACCOUNT_EQUITY, risk_per_trade=RISK_PER_TRADE):
    if data.empty or higher_tf.empty:
        return {
            'Trade': False, 'Reason': 'Insufficient data', 'PositionSize': 0, 'StopLoss': None, 'TakeProfit': None,
            'EntryPrice': None, 'EntrySignal': '', 'ExitSignal': ''
        }
    # --- LATEST VALUES ---
    rsi = data['momentum_rsi'].iloc[-1]
    macd = data['trend_macd_diff'].iloc[-1]
    bbp = data['volatility_bbp'].iloc[-1]
    close = data['Close'].iloc[-1]
    atr = data['volatility_atr'].iloc[-1]
    volume = data['Volume'].iloc[-1]
    avg_vol = data['Volume'].rolling(20).mean().iloc[-1]

    # --- HIGHER TIMEFRAME UPTREND ---
    uptrend = False
    if not higher_tf.empty and len(higher_tf) >= 200:
        ma50 = higher_tf['MA50'].iloc[-1]
        ma200 = higher_tf['MA200'].iloc[-1]
        uptrend = (ma50 > ma200)

    # --- STRICT ENTRY CONDITIONS ---
    entry_signal = (
        (rsi < 35) and
        (macd > 0) and
        (bbp < 0.2) and
        (volume > avg_vol) and
        uptrend and
        (active_trades < MAX_CONCURRENT_TRADES)
    )

    # --- POSITION SIZING ---
    stop_loss = close - 1.5 * atr if atr > 0 else None
    take_profit = close + 3 * atr if atr > 0 else None
    risk_per_share = close - stop_loss if stop_loss is not None else None
    pos_size = int((account_equity * risk_per_trade) / risk_per_share) if (risk_per_share and risk_per_share > 0) else 0

    # --- STRICT EXIT CONDITIONS ---
    prev_rsi = data['momentum_rsi'].iloc[-2] if len(data) > 1 else None
    prev_macd = data['trend_macd_diff'].iloc[-2] if len(data) > 1 else None
    exit_signal = (
        ((prev_rsi is not None and prev_rsi < 50 and rsi >= 50)) or
        ((prev_macd is not None and prev_macd > 0 and macd <= 0))
    )
    exit_descr = "RSI crosses 50, MACD crosses <0, or stop/TP hit"

    return {
        'Trade': entry_signal,
        'Reason': 'All strict criteria met' if entry_signal else 'Did not meet entry criteria',
        'PositionSize': pos_size if entry_signal else 0,
        'StopLoss': stop_loss if entry_signal else None,
        'TakeProfit': take_profit if entry_signal else None,
        'EntryPrice': close if entry_signal else None,
        'EntrySignal': "RSI<35, MACD>0, BB%<0.2, Vol>Avg, Uptrend(Weekly), Trades<Max" if entry_signal else '',
        'ExitSignal': exit_descr if entry_signal else ''
    }

def scan_universe_strict(universe, period='6mo'):
    results = []
    failed = []
    active_trades = 0
    with st.spinner(f"Scanning {len(universe)} stocks (strict rules)..."):
        progress_bar = st.progress(0)
        for i, ticker in enumerate(universe):
            try:
                data = get_stock_data(ticker, period)
                higher_tf = get_higher_tf_data(ticker)
                strat = strict_swing_strategy(
                    data, higher_tf, active_trades,
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
            progress_bar.progress((i + 1) / len(universe))
            time.sleep(0.08)
    return pd.DataFrame(results), failed

# --- STREAMLIT UI CONFIG ---
st.set_page_config(
    page_title="Swing Trading Scanner Pro (Strict)",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

SCAN_UNIVERSE = [
    'AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'TSLA', 'NVDA', 'PYPL', 'ADBE', 'NFLX'
]
TIME_FRAMES = ['1d', '1wk']

uploaded_file = st.file_uploader(
    "Upload an Excel file (.xlsx) with a column named 'Ticker' or 'Symbol'", type=["xlsx"]
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

st.session_state.watchlist = excel_ticker_list or clean_tickers(SCAN_UNIVERSE)

# --- SIDEBAR FILTERS ---
st.sidebar.title("Swing Trading Scanner Pro (Strict)")
st.sidebar.subheader("Configuration")
with st.sidebar.expander("Trade Management", expanded=True):
    st.write(f"Account Equity: €{ACCOUNT_EQUITY:,}")
    st.write(f"Risk per trade: {int(RISK_PER_TRADE*100)}%")
    st.write(f"Max concurrent trades: {MAX_CONCURRENT_TRADES}")

st.sidebar.markdown("#### Current Universe")
for ticker in st.session_state.watchlist:
    st.sidebar.write(f"- {ticker}")

# --- MAIN PAGE ---
if st.sidebar.button("Run Strict Scan", type="primary"):
    results, failed = scan_universe_strict(
        st.session_state.watchlist,
        period='6mo'
    )
    st.session_state.scanned_results = results
    st.session_state.failed_tickers = failed

if "scanned_results" in st.session_state and not st.session_state.scanned_results.empty:
    st.subheader("Strict Scan Results")
    st.dataframe(st.session_state.scanned_results)
    if 'failed_tickers' in st.session_state and st.session_state.failed_tickers:
        st.warning(f"Failed to fetch data for {len(st.session_state.failed_tickers)} tickers. See list below:")
        with st.expander("Show Failed Tickers"):
            st.write(st.session_state.failed_tickers)
else:
    st.info("Click 'Run Strict Scan' to scan for high-probability swing trades.")
