import streamlit as st
import pandas as pd
import yfinance as yf
from ta import add_all_ta_features
import time
import matplotlib.pyplot as plt

# --- UTILITIES ---
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
    # Flatten MultiIndex columns if present
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(-1)
        # Remove duplicates if present
        if len(set(data.columns)) != len(data.columns):
            data = data.loc[:, ~data.columns.duplicated()]
        if len(data.columns) == 5 and len(set(data.columns)) == 1:
            data.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    if data.empty or len(data) < 2:
        return pd.DataFrame()
    min_rows = 15
    if len(data) < min_rows:
        return pd.DataFrame()
    try:
        data = add_all_ta_features(
            data, open="Open", high="High", low="Low", close="Close", volume="Volume"
        )
        # Remove duplicates after adding TA features
        if data.columns.duplicated().any():
            data = data.loc[:, ~data.columns.duplicated()]
    except Exception as e:
        print(f"TA error for {ticker}: {e}")
        return pd.DataFrame()
    return data

def calculate_opportunity_score(data):
    if data.empty:
        return 0
    rsi = data['momentum_rsi'].iloc[-1] if 'momentum_rsi' in data else float('nan')
    macd = data['trend_macd_diff'].iloc[-1] if 'trend_macd_diff' in data else float('nan')
    bbp = data['volatility_bbp'].iloc[-1] if 'volatility_bbp' in data else float('nan')
    score = 0
    if not pd.isna(rsi):
        score += (100 - abs(rsi - 50)) * 0.5
    if not pd.isna(macd):
        score += (macd * 100) * 0.25
    if not pd.isna(bbp):
        score += (100 - abs(bbp - 0.5) * 200) * 0.25
    return round(score, 1)

def generate_strategy(data):
    entry, exit = [], []
    stop_loss, take_profit = None, None
    if not data.empty:
        rsi = data['momentum_rsi'].iloc[-1] if 'momentum_rsi' in data else None
        macd = data['trend_macd_diff'].iloc[-1] if 'trend_macd_diff' in data else None
        bbp = data['volatility_bbp'].iloc[-1] if 'volatility_bbp' in data else None
        close = data['Close'].iloc[-1] if 'Close' in data.columns else None
        if rsi is not None:
            if rsi < 35: entry.append(f"RSI ({rsi:.1f}) < 35 (Oversold)")
            elif rsi > 65: entry.append(f"RSI ({rsi:.1f}) > 65 (Overbought)")
        if macd is not None:
            entry.append("MACD positive" if macd > 0 else "MACD negative")
        if bbp is not None:
            if bbp < 0.2: entry.append("Price near lower Bollinger Band")
            elif bbp > 0.8: entry.append("Price near upper Bollinger Band")
        if rsi is not None:
            if rsi < 30 or rsi > 70: exit.append(f"RSI crosses {'40' if rsi<30 else '60'}")
        exit.append("MACD crosses signal line (opp. dir)")
        atr = data['volatility_atr'].iloc[-1] if 'volatility_atr' in data else None
        if atr is not None and close is not None:
            stop_loss = f"{close - atr * 1.5:.2f} (1.5x ATR)"
            take_profit = f"{close + atr * 3:.2f} (3x ATR)"
    return {
        'entry_rules': entry,
        'exit_rules': exit,
        'stop_loss': stop_loss,
        'take_profit': take_profit
    }

def strategy_to_string(strategy):
    return (
        "Entry: " + (", ".join(strategy['entry_rules']) if strategy['entry_rules'] else "None") + "\n"
        "Exit: " + (", ".join(strategy['exit_rules']) if strategy['exit_rules'] else "None") + "\n"
        "Stop Loss: " + (str(strategy['stop_loss']) if strategy['stop_loss'] else "None") + "\n"
        "Take Profit: " + (str(strategy['take_profit']) if strategy['take_profit'] else "None")
    )

def safe_display(df, **kwargs):
    if isinstance(df, pd.DataFrame) and df.columns.duplicated().any():
        st.error(f"Duplicate columns found: {list(df.columns[df.columns.duplicated()])}")
        df = df.loc[:, ~df.columns.duplicated()]
    st.dataframe(df, **kwargs)

def scan_universe(universe, period='6mo'):
    results = []
    failed = []
    with st.spinner(f"Scanning {len(universe)} stocks..."):
        progress_bar = st.progress(0)
        for i, ticker in enumerate(universe):
            try:
                data = get_stock_data(ticker, period)
                if not data.empty:
                    score = calculate_opportunity_score(data)
                    strategy = generate_strategy(data)
                    if score is not None and strategy is not None:
                        results.append({
                            'Ticker': ticker,
                            'Score': score,
                            'Price': data['Close'].iloc[-1] if 'Close' in data.columns else float('nan'),
                            'Change %': (data['Close'].iloc[-1] / data['Close'].iloc[-2] - 1) * 100 if 'Close' in data.columns and len(data['Close']) > 1 else float('nan'),
                            'Volume': data['Volume'].iloc[-1] if 'Volume' in data.columns else float('nan'),
                            'RSI': data['momentum_rsi'].iloc[-1] if 'momentum_rsi' in data else float('nan'),
                            'MACD': data['trend_macd_diff'].iloc[-1] if 'trend_macd_diff' in data else float('nan'),
                            'BB %': data['volatility_bbp'].iloc[-1] * 100 if 'volatility_bbp' in data else float('nan'),
                            'Strategy': strategy_to_string(strategy)
                        })
                else:
                    failed.append(ticker)
            except Exception as e:
                st.warning(f"Error processing {ticker}: {str(e)}")
                failed.append(ticker)
                continue
            progress_bar.progress((i + 1) / len(universe))
            time.sleep(0.08)
    if not results:
        return pd.DataFrame(columns=['Ticker', 'Score', 'Price', 'Change %', 'Volume', 'RSI', 'MACD', 'BB %', 'Strategy']), failed
    return pd.DataFrame(results).sort_values('Score', ascending=False), failed

# --- UI CONFIG ---
st.set_page_config(
    page_title="Swing Trading Scanner Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- UNIVERSE & UPLOAD ---
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
st.sidebar.title("Swing Trading Scanner Pro")
st.sidebar.subheader("Configuration")
with st.sidebar.expander("Scan Settings", expanded=True):
    time_frame = st.selectbox("Time Frame", TIME_FRAMES)
    min_score = st.slider("Minimum Quality Score", 0, 100, 18)
    max_results = st.slider("Max Results", 5, 50, 15)

st.sidebar.markdown("#### Current Universe")
for ticker in st.session_state.watchlist:
    st.sidebar.write(f"- {ticker}")

# --- MAIN PAGE ---
if st.sidebar.button("Run Scan", type="primary"):
    results, failed = scan_universe(
        st.session_state.watchlist,
        period='6mo'
    )
    st.session_state.scanned_results = results.head(max_results) if not results.empty else results
    st.session_state.failed_tickers = failed

if "scanned_results" in st.session_state and not st.session_state.scanned_results.empty:
    st.subheader("Scan Results")
    safe_display(st.session_state.scanned_results)
    if 'failed_tickers' in st.session_state and st.session_state.failed_tickers:
        st.warning(f"Failed to fetch data for {len(st.session_state.failed_tickers)} tickers. See list below:")
        with st.expander("Show Failed Tickers"):
            st.write(st.session_state.failed_tickers)
else:
    st.info("Click 'Run Scan' to find swing trading opportunities")

# --- Single Ticker Data Test (Diagnostics) ---
with st.expander("Single Ticker Data Test (Diagnostics)", expanded=False):
    try:
        ticker = st.text_input(
            "Test a ticker",
            value="",
            placeholder="e.g. MC.PA, AAPL, ORA.PA, SAN.PA"
        )
    except TypeError:
        ticker = st.text_input(
            "Test a ticker (e.g. MC.PA, AAPL, ORA.PA, SAN.PA)",
            value=""
        )
    period = st.selectbox("Test period", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=2, key='test_period')
    interval = st.selectbox("Test interval", ["1d", "1wk"], index=0, key='test_interval')
    if st.button("Fetch Ticker Data"):
        if not ticker:
            st.warning("Please enter a ticker symbol.")
        else:
            st.write(f"**Ticker:** {ticker}  \n**Period:** {period}  \n**Interval:** {interval}")
            data = yf.download(ticker, period=period, interval=interval)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(-1)
                if data.columns.duplicated().any():
                    data = data.loc[:, ~data.columns.duplicated()]
                if len(data.columns) == 5 and len(set(data.columns)) == 1:
                    data.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            st.write("Raw Yahoo data:")
            safe_display(data.tail(10))
            min_rows = 15
            if data.empty:
                st.error("No data returned! This ticker/interval/period combo is not supported by Yahoo, or market is closed.")
            elif len(data) < min_rows:
                st.warning(f"Not enough data to compute indicators (need at least {min_rows} rows, got {len(data)})")
            else:
                # Calculate moving averages, if possible and 'Close' exists
                if 'Close' in data.columns:
                    for ma in ['MA20', 'MA50', 'MA200']:
                        if ma in data.columns:
                            data = data.drop(columns=[ma])
                    data['MA20'] = data['Close'].rolling(window=20).mean()
                    data['MA50'] = data['Close'].rolling(window=50).mean()
                    data['MA200'] = data['Close'].rolling(window=200).mean()
                    # Remove duplicates if any
                    if data.columns.duplicated().any():
                        data = data.loc[:, ~data.columns.duplicated()]
                    # Plot Close and MAs
                    fig, ax = plt.subplots(figsize=(10, 5))
                    ax.plot(data.index, data['Close'], label='Close Price')
                    ax.plot(data.index, data['MA20'], label='20-day MA')
                    ax.plot(data.index, data['MA50'], label='50-day MA')
                    ax.plot(data.index, data['MA200'], label='200-day MA')
                    ax.set_title(f"{ticker} Price with Moving Averages")
                    ax.set_xlabel("Date")
                    ax.set_ylabel("Price")
                    ax.legend()
                    st.pyplot(fig)
                else:
                    st.error("No 'Close' column found in price data! Cannot calculate moving averages. Check ticker, interval, or period.")
                # Existing TA features display
                try:
                    ta_data = add_all_ta_features(
                        data, open="Open", high="High", low="Low", close="Close", volume="Volume"
                    )
                    if ta_data.columns.duplicated().any():
                        ta_data = ta_data.loc[:, ~ta_data.columns.duplicated()]
                    st.write("With TA features (last 5 rows):")
                    safe_display(ta_data.tail())
                except Exception as e:
                    st.warning(f"TA error: {e}")
