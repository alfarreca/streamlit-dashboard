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

# --- DATA FETCHING FUNCTIONS ---
def get_stock_data(ticker, period='6mo'):
    try:
        data = yf.download(ticker, period=period, interval='1d', progress=False)
        if data.empty or len(data) < 20:
            st.warning(f"Insufficient data for {ticker}")
            return pd.DataFrame()
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(-1)
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in data.columns for col in required_cols):
            st.warning(f"Missing columns for {ticker}: {', '.join([col for col in required_cols if col not in data.columns])}")
            return pd.DataFrame()
        data = add_all_ta_features(
            data, open="Open", high="High", low="Low", close="Close", volume="Volume"
        )
        ta_cols = ['momentum_rsi', 'trend_macd_diff', 'volatility_bbp', 'volatility_atr']
        if not all(col in data.columns for col in ta_cols):
            st.warning(f"Missing TA columns for {ticker}: {', '.join([col for col in ta_cols if col not in data.columns])}")
            return pd.DataFrame()
        return data
    except Exception as e:
        st.warning(f"Error downloading data for {ticker}: {str(e)}")
        return pd.DataFrame()

def get_higher_tf_data(ticker, period='2y'):
    try:
        data = yf.download(ticker, period=period, interval='1wk', progress=False)
        if data.empty or len(data) < 60:
            return pd.DataFrame()
        data['MA50'] = data['Close'].rolling(window=50, min_periods=40).mean()
        data['MA200'] = data['Close'].rolling(window=200, min_periods=150).mean()
        if pd.isna(data['MA50'].iloc[-1]) or pd.isna(data['MA200'].iloc[-1]):
            return pd.DataFrame()
        return data
    except Exception as e:
        st.warning(f"Error getting weekly data for {ticker}: {str(e)}")
        return pd.DataFrame()

# --- STRATEGY FUNCTION ---
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
    required_cols = ['momentum_rsi', 'trend_macd_diff', 'volatility_bbp', 'Close', 'volatility_atr', 'Volume']
    if not all(col in data.columns for col in required_cols):
        response['Reason'] = 'Missing required data columns'
        return response
    try:
        current = data.iloc[-1]
        prev = data.iloc[-2]
        rsi = current['momentum_rsi']
        macd = current['trend_macd_diff']
        bbp = current['volatility_bbp']
        close = current['Close']
        atr = current['volatility_atr']
        volume = current['Volume']
        avg_vol = data['Volume'].rolling(20).mean().iloc[-1]
    except Exception as e:
        response['Reason'] = f'Error reading data: {str(e)}'
        return response
    uptrend = True
    if weekly_ma_filter:
        if higher_tf.empty or len(higher_tf) < 200:
            response['Reason'] = 'Insufficient weekly data'
            return response
        try:
            ma50 = higher_tf['MA50'].iloc[-1]
            ma200 = higher_tf['MA200'].iloc[-1]
            uptrend = (ma50 > ma200)
        except Exception as e:
            response['Reason'] = 'Error checking weekly trend'
            return response
    vol_ok = True
    if vol_filter:
        try:
            vol_ok = (volume > avg_vol) if not pd.isna(avg_vol) else False
        except:
            vol_ok = False
    entry_signal = all([
        (rsi < rsi_thresh),
        (macd > macd_thresh),
        (bbp < bbp_thresh),
        vol_ok,
        uptrend,
        (active_trades < max_concurrent_trades)
    ])
    if entry_signal:
        try:
            stop_loss = close - 1.5 * atr
            take_profit = close + 3 * atr
            risk_per_share = close - stop_loss
            if risk_per_share > 0:
                pos_size = int((account_equity * risk_per_trade) / risk_per_share)
            else:
                pos_size = 0
                response['Reason'] = 'Invalid risk calculation'
                return response
            exit_descr = "RSI crosses 50, MACD crosses <0, or stop/TP hit"
            descr = f"RSI<{rsi_thresh}, MACD>{macd_thresh}, BB%<{bbp_thresh}"
            if vol_filter:
                descr += ", Vol>Avg"
            if weekly_ma_filter:
                descr += ", Uptrend(Weekly)"
            response.update({
                'Trade': True,
                'Reason': 'All criteria met',
                'PositionSize': pos_size,
                'StopLoss': stop_loss,
                'TakeProfit': take_profit,
                'EntryPrice': close,
                'EntrySignal': descr,
                'ExitSignal': exit_descr
            })
        except Exception as e:
            response['Reason'] = f'Error calculating trade params: {str(e)}'
    else:
        reasons = []
        if rsi >= rsi_thresh:
            reasons.append(f"RSI ≥ {rsi_thresh}")
        if macd <= macd_thresh:
            reasons.append(f"MACD ≤ {macd_thresh}")
        if bbp >= bbp_thresh:
            reasons.append(f"BB% ≥ {bbp_thresh}")
        if vol_filter and not vol_ok:
            reasons.append("Volume ≤ Avg")
        if weekly_ma_filter and not uptrend:
            reasons.append("Not in uptrend")
        if active_trades >= max_concurrent_trades:
            reasons.append("Max trades reached")
        response['Reason'] = "Failed: " + ", ".join(reasons) if reasons else "Unknown reason"
    return response

# --- STREAMLIT UI ---
st.set_page_config(page_title="Swing Trading Batch Scanner", layout="wide")
st.title("Swing Trading Batch Scanner")
st.markdown("Upload your ticker list, set your entry rules, and scan for swing setups across the market.")

st.sidebar.header("Strategy Settings")

uploaded_file = st.sidebar.file_uploader(
    "Upload XLSX Watchlist", type=["xlsx"],
    help="Upload Excel file with 'Symbol' or 'Ticker' column"
)

if uploaded_file:
    df_uploaded = pd.read_excel(uploaded_file)
    ticker_col = None
    for col in df_uploaded.columns:
        if col.strip().lower() in ['symbol', 'ticker']:
            ticker_col = col
            break
    if not ticker_col:
        st.sidebar.error("No 'Symbol' or 'Ticker' column found!")
        tickers = []
    else:
        tickers = df_uploaded[ticker_col].dropna().astype(str).str.upper().unique().tolist()
        st.sidebar.success(f"Loaded {len(tickers)} tickers.")
else:
    tickers = []
    st.sidebar.info("Please upload an Excel file to start batch scanning.")

account_equity = st.sidebar.number_input("Account Equity (€)", min_value=1000, max_value=1_000_000, value=ACCOUNT_EQUITY, step=1000)
risk_per_trade = st.sidebar.slider("Risk per trade (%)", 0.5, 5.0, RISK_PER_TRADE*100, step=0.1) / 100
max_concurrent_trades = st.sidebar.slider("Max concurrent trades", 1, 20, MAX_CONCURRENT_TRADES)
rsi_thresh = st.sidebar.slider("RSI Threshold (Entry Below)", min_value=10, max_value=70, value=30)
macd_thresh = st.sidebar.slider("MACD Threshold (Entry Above)", min_value=-10, max_value=10, value=0)
bbp_thresh = st.sidebar.slider("BB% Threshold (Entry Below)", min_value=0.0, max_value=1.0, value=0.2, step=0.01)
vol_filter = st.sidebar.checkbox("Filter by Volume > Avg", value=True)
weekly_ma_filter = st.sidebar.checkbox("Filter by Weekly Uptrend (MA50 > MA200)", value=True)

if uploaded_file and st.sidebar.button("Run Batch Scan"):
    results = []
    failed = []
    active_trades = 0
    with st.spinner(f"Scanning {len(tickers)} stocks..."):
        for i, ticker in enumerate(tickers):
            data = get_stock_data(ticker)
            higher_tf = get_higher_tf_data(ticker) if weekly_ma_filter else pd.DataFrame()
            result = adjustable_swing_strategy(
                data, higher_tf, active_trades,
                rsi_thresh, macd_thresh, bbp_thresh,
                vol_filter, weekly_ma_filter,
                account_equity, risk_per_trade,
                max_concurrent_trades
            )
            if result['Trade']:
                active_trades += 1
            results.append({
                'Symbol': ticker,
                'Signal': 'BUY' if result['Trade'] else '-',
                'Reason': result['Reason'],
                'Price': f"{result['EntryPrice']:.2f}" if result['EntryPrice'] else '-',
                'Size': result['PositionSize'] or '-',
                'Stop': f"{result['StopLoss']:.2f}" if result['StopLoss'] else '-',
                'Target': f"{result['TakeProfit']:.2f}" if result['TakeProfit'] else '-',
                'Conditions': result['EntrySignal'],
                'Exit Rules': result['ExitSignal']
            })
    results_df = pd.DataFrame(results)
    st.subheader("Batch Scan Results")
    if not results_df.empty:
        buy_signals = results_df[results_df['Signal'] == 'BUY']
        if not buy_signals.empty:
            st.success(f"Found {len(buy_signals)} trade signals!")
            st.dataframe(buy_signals)
        st.write("All Results:")
        st.dataframe(results_df)
    else:
        st.warning("No results to display.")
    st.success(f"Scanned {len(tickers)} stocks.")
elif not uploaded_file:
    st.info("Upload a ticker list and set your scan parameters, then click 'Run Batch Scan'.")
