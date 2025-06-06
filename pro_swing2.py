import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
from ta import add_all_ta_features
import io

# --- Utilities ---
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

def fetch_and_flatten_ticker(ticker, period='6mo', interval='1d'):
    debug = {}
    try:
        raw = yf.download(ticker, period=period, interval=interval)
        debug['download_shape'] = raw.shape
        debug['columns'] = str(raw.columns)
        # Handle MultiIndex as returned by yfinance for some tickers
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        if raw.empty or len(raw) < 5:
            debug['error'] = "Empty or insufficient rows"
            return pd.DataFrame(), debug
        raw['Ticker'] = ticker  # keep for debug
        # Add TA features
        ta_df = add_all_ta_features(
            raw, open="Open", high="High", low="Low", close="Close", volume="Volume", fillna=True
        )
        debug['ta_shape'] = ta_df.shape
        return ta_df, debug
    except Exception as e:
        debug['error'] = f"TA error: {str(e)}"
        return pd.DataFrame(), debug

def score_momentum(df):
    if df.empty or 'momentum_rsi' not in df.columns:
        return np.nan
    return df['momentum_rsi'].iloc[-1]

# --- Streamlit Config ---
st.set_page_config(page_title="Swing Trading Scanner Pro", layout="wide")

st.title("📈 Swing Trading Scanner Pro")
st.write("Your professional dashboard for swing trading opportunities — with technicals, charts, Excel export, and diagnostics.")

# --- Excel Upload ---
uploaded_file = st.sidebar.file_uploader(
    "Upload an Excel file (.xlsx) with a column named 'Ticker' or 'Symbol'", type=["xlsx"]
)
excel_ticker_list = None
if uploaded_file:
    df_excel = pd.read_excel(uploaded_file)
    ticker_col = next((col for col in df_excel.columns if col.lower() in ['ticker', 'symbol']), None)
    if ticker_col:
        excel_ticker_list = clean_tickers(df_excel[ticker_col].tolist())
        st.sidebar.success(f"Loaded {len(excel_ticker_list)} tickers from Excel: {ticker_col}")
    else:
        st.sidebar.error("Could not find 'Ticker' or 'Symbol' column.")

# --- Watchlist Setup ---
DEFAULT_TICKERS = [
    'AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'TSLA', 'NVDA', 'PYPL', 'ADBE', 'NFLX'
]
watchlist = excel_ticker_list or clean_tickers(DEFAULT_TICKERS)

st.sidebar.markdown("### Current Universe")
for ticker in watchlist:
    st.sidebar.write(f"- {ticker}")

# --- Controls ---
st.sidebar.header("Scan Settings")
TIME_FRAMES = ['1d', '1wk']
time_frame = st.sidebar.selectbox("Time Frame", TIME_FRAMES)
min_score = st.sidebar.slider("Minimum Quality Score", 0, 100, 18)
max_results = st.sidebar.slider("Max Results", 5, 50, 15)

# --- Scan Button & Logic ---
if 'scan_results' not in st.session_state:
    st.session_state.scan_results = pd.DataFrame()
if 'debug_log' not in st.session_state:
    st.session_state.debug_log = {}

if st.button("Run Scan", type="primary"):
    results = []
    debug_log = {}
    for ticker in watchlist:
        df, dbg = fetch_and_flatten_ticker(ticker, period='6mo', interval=time_frame)
        debug_log[ticker] = dbg
        if df.empty or 'error' in dbg:
            continue
        score = score_momentum(df)
        rsi = df['momentum_rsi'].iloc[-1] if 'momentum_rsi' in df.columns else None
        macd = df['trend_macd'].iloc[-1] if 'trend_macd' in df.columns else None
        close = df['Close'].iloc[-1] if 'Close' in df.columns else None
        volume = df['Volume'].iloc[-1] if 'Volume' in df.columns else None
        results.append({
            'Ticker': ticker, 'Score': score, 'RSI': rsi, 'MACD': macd,
            'Price': close, 'Volume': volume
        })

    scan_df = pd.DataFrame(results)

    if not scan_df.empty and 'Score' in scan_df.columns:
        scan_df = scan_df[scan_df['Score'] >= min_score].sort_values("Score", ascending=False).head(max_results)
        st.session_state.scan_results = scan_df
        st.session_state.debug_log = debug_log
        st.success(f"Scan complete: {len(scan_df)} tickers found.")
    else:
        st.session_state.scan_results = pd.DataFrame()
        st.session_state.debug_log = debug_log
        st.warning("No valid scan results. Check the debug info below for details on failed tickers.")

# --- Show Results Table ---
scan_df = st.session_state.scan_results
if not scan_df.empty:
    st.subheader("Scan Results")
    st.dataframe(scan_df, use_container_width=True)
    # --- Download Buttons ---
    st.download_button(
        "Download Results as CSV", data=scan_df.to_csv(index=False), file_name="scan_results.csv", mime="text/csv"
    )
    # Excel Download (OpenPyXL)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        scan_df.to_excel(writer, index=False)
    st.download_button(
        "Download Results as Excel", data=output.getvalue(), file_name="scan_results.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("Run a scan to see results.")

# --- Debug/Log Info ---
with st.expander("Debug Info / Raw Log", expanded=False):
    debug_log = st.session_state.get('debug_log', {})
    # Failed tickers (those not in results)
    failed = [k for k, v in debug_log.items() if 'error' in v]
    if failed:
        st.warning(f"Failed to fetch data for {len(failed)} tickers. See below:")
        st.write([{k: v['error']} for k, v in debug_log.items() if 'error' in v])
    st.write(debug_log)

# --- Diagnostics (Single Ticker Test) ---
with st.expander("Single Ticker Data Test (Diagnostics)", expanded=False):
    col1, col2, col3 = st.columns([3,1,1])
    with col1:
        single_ticker = st.text_input("Test a ticker (e.g. MC.PA, AAPL, ORA.PA, SAN.PA):", value=watchlist[0] if watchlist else "AAPL")
    with col2:
        single_period = st.selectbox("Test period", ['6mo', '1y', '3mo'], index=0)
    with col3:
        single_interval = st.selectbox("Test interval", ['1d', '1wk'], index=0)
    if st.button("Fetch Ticker Data"):
        df, dbg = fetch_and_flatten_ticker(single_ticker, period=single_period, interval=single_interval)
        st.write(f"**Ticker:** {single_ticker}  **Period:** {single_period}  **Interval:** {single_interval}")
        if not df.empty:
            st.write("Returned DataFrame shape:", df.shape)
            st.dataframe(df.head(3))
            st.write("Returned columns:", list(df.columns))
        else:
            st.error(f"No data returned! Debug info: {dbg}")
        with st.expander("Show Debug Info", expanded=False):
            st.write(dbg)

