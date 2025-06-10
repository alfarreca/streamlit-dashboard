import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from ta import add_all_ta_features

# --- CONFIGURABLES ---
ACCOUNT_EQUITY = 10_000
RISK_PER_TRADE = 0.01
MAX_CONCURRENT_TRADES = 3

def get_stock_data(ticker, period='6mo'):
    try:
        data = yf.download(ticker, period=period, interval='1d', progress=False)
        if data.empty:
            st.warning(f"No data found for {ticker} (Yahoo Finance may not support this ticker or exchange).")
            return pd.DataFrame()
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(-1)
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        have_cols = [col for col in required_cols if col in data.columns]
        if len(have_cols) < 5 and "Adj Close" in data.columns:
            st.warning(f"Only 'Adj Close' found for {ticker}. Using it as 'Close'; other OHLCV will be NaN.")
            data['Close'] = data['Adj Close']
            for col in ['Open', 'High', 'Low', 'Volume']:
                if col not in data.columns:
                    data[col] = np.nan
            have_cols = [col for col in required_cols if col in data.columns]
        if not all(col in data.columns for col in required_cols):
            missing = [col for col in required_cols if col not in data.columns]
            st.warning(f"Missing columns for {ticker}: {', '.join(missing)}")
            return pd.DataFrame()
        try:
            data = add_all_ta_features(
                data, open="Open", high="High", low="Low", close="Close", volume="Volume"
            )
            ta_cols = ['momentum_rsi', 'trend_macd_diff', 'volatility_bbp', 'volatility_atr']
            if not all(col in data.columns for col in ta_cols):
                missing_ta = [col for col in ta_cols if col not in data.columns]
                st.warning(f"Missing TA columns for {ticker}: {', '.join(missing_ta)}")
                return pd.DataFrame()
        except Exception as ta_error:
            st.warning(f"TA calculation failed for {ticker}: {str(ta_error)}")
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
st.set_page_config(page_title="Swing Trading Dashboard", layout="wide")
st.title("Swing Trading Strategy Dashboard")
st.markdown("Test and visualize swing trading signals using TA indicators.")

st.sidebar.header("Strategy Settings")
file = st.sidebar.file_uploader(
    "Upload XLSX file (OHLCV or 'Symbol'/'Symbols' columns)", type=["xlsx"]
)

ticker = st.sidebar.text_input("Stock Ticker", value="AAPL")
rsi_thresh = st.sidebar.slider("RSI Threshold (Entry Below)", min_value=10, max_value=70, value=30)
macd_thresh = st.sidebar.slider("MACD Threshold (Entry Above)", min_value=-10, max_value=10, value=0)
bbp_thresh = st.sidebar.slider("BB% Threshold (Entry Below)", min_value=0.0, max_value=1.0, value=0.2, step=0.01)
vol_filter = st.sidebar.checkbox("Filter by Volume > Avg", value=True)
weekly_ma_filter = st.sidebar.checkbox("Filter by Weekly Uptrend (MA50 > MA200)", value=True)

if st.sidebar.button("Run Strategy"):
    st.info("Running strategy. Please wait for results below.")
    with st.spinner("Fetching data and running strategy..."):
        if file is not None:
            try:
                df = pd.read_excel(file)
                df.columns = [c.strip() for c in df.columns]
                required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
                # OHLCV data upload
                if all(col in df.columns for col in required_cols):
                    st.info("Detected OHLCV data. Using uploaded file for analysis.")
                    if 'Date' in df.columns:
                        df.set_index('Date', inplace=True, drop=True)
                        df.index = pd.to_datetime(df.index)
                    data = add_all_ta_features(
                        df, open="Open", high="High", low="Low", close="Close", volume="Volume"
                    )
                    higher_tf = pd.DataFrame()
                    active_trades = 0
                    result = adjustable_swing_strategy(
                        data, higher_tf, active_trades,
                        rsi_thresh, macd_thresh, bbp_thresh,
                        vol_filter, weekly_ma_filter,
                        ACCOUNT_EQUITY, RISK_PER_TRADE, MAX_CONCURRENT_TRADES
                    )
                    st.subheader("Latest Signal for Uploaded Data")
                    st.write("**Entry Signal:**", result['EntrySignal'])
                    st.write("**Reason:**", result['Reason'])
                    if result['Trade']:
                        st.success(f"Trade Signal: BUY {result['PositionSize']} shares at {result['EntryPrice']:.2f}")
                        st.write(f"- Stop Loss: {result['StopLoss']:.2f}")
                        st.write(f"- Take Profit: {result['TakeProfit']:.2f}")
                        st.write(f"- Exit Condition: {result['ExitSignal']}")
                    else:
                        st.warning("No trade signal at this time.")
                    st.write("Recent Data Snapshot:")
                    st.dataframe(data.tail(10))
                # Symbols/Exchange watchlist upload (supports "Symbol" or "Symbols")
                elif "Symbol" in df.columns or "Symbols" in df.columns:
                    symbol_col = "Symbol" if "Symbol" in df.columns else "Symbols"
                    st.info(f"Detected watchlist column '{symbol_col}'. Will fetch live data for each symbol.")
                    summary = []
                    progress_bar = st.progress(0)
                    total = len(df)
                    for idx, row in enumerate(df.itertuples(index=False)):
                        symbol = getattr(row, symbol_col, None)
                        if pd.isna(symbol):
                            progress_bar.progress(min(int((idx + 1) / total * 100), 100))
                            continue
                        yf_symbol = str(symbol)
                        data = get_stock_data(yf_symbol)
                        higher_tf = get_higher_tf_data(yf_symbol) if weekly_ma_filter else pd.DataFrame()
                        active_trades = 0
                        result = adjustable_swing_strategy(
                            data, higher_tf, active_trades,
                            rsi_thresh, macd_thresh, bbp_thresh,
                            vol_filter, weekly_ma_filter,
                            ACCOUNT_EQUITY, RISK_PER_TRADE, MAX_CONCURRENT_TRADES
                        )
                        summary.append({
                            "Symbol": yf_symbol,
                            "Trade": "YES" if result['Trade'] else "NO",
                            "Reason": result['Reason'],
                            "EntryPrice": result['EntryPrice'],
                            "PositionSize": result['PositionSize'],
                            "StopLoss": result['StopLoss'],
                            "TakeProfit": result['TakeProfit']
                        })
                        progress_bar.progress(min(int((idx + 1) / total * 100), 100))
                    st.subheader("Batch Results")
                    st.dataframe(pd.DataFrame(summary))
                else:
                    st.error("XLSX must contain either OHLCV columns (Open, High, Low, Close, Volume, Date) or at least a 'Symbol' or 'Symbols' column.")
            except Exception as e:
                st.error(f"Failed to process XLSX: {e}")
        else:
            data = get_stock_data(ticker)
            higher_tf = get_higher_tf_data(ticker) if weekly_ma_filter else pd.DataFrame()
            active_trades = 0
            result = adjustable_swing_strategy(
                data, higher_tf, active_trades,
                rsi_thresh, macd_thresh, bbp_thresh,
                vol_filter, weekly_ma_filter,
                ACCOUNT_EQUITY, RISK_PER_TRADE, MAX_CONCURRENT_TRADES
            )
            if data.empty:
                st.error("No valid data for analysis.")
            else:
                st.subheader(f"Latest Signal for {ticker}")
                st.write("**Entry Signal:**", result['EntrySignal'])
                st.write("**Reason:**", result['Reason'])
                if result['Trade']:
                    st.success(f"Trade Signal: BUY {result['PositionSize']} shares at {result['EntryPrice']:.2f}")
                    st.write(f"- Stop Loss: {result['StopLoss']:.2f}")
                    st.write(f"- Take Profit: {result['TakeProfit']:.2f}")
                    st.write(f"- Exit Condition: {result['ExitSignal']}")
                else:
                    st.warning("No trade signal at this time.")
                st.write("Recent Data Snapshot:")
                st.dataframe(data.tail(10))
else:
    st.info("Upload an XLSX file (with OHLCV or with Symbol/Symbols) or enter a ticker and strategy settings, then click 'Run Strategy'.")
