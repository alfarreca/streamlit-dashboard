import streamlit as st
import pandas as pd
import yfinance as yf
from ta import add_all_ta_features

st.set_page_config(
    page_title="Swing Trading Scanner Pro",
    page_icon="📈",
    layout="wide"
)

def fetch_and_flatten_ticker(ticker, period='6mo', interval='1d'):
    df = yf.download(ticker, period=period, interval=interval, group_by='ticker')
    debug_info = {}
    debug_info['raw_shape'] = df.shape
    debug_info['raw_columns'] = str(df.columns)

    # Handle MultiIndex from yfinance (batch or region-ticker cases)
    if isinstance(df.columns, pd.MultiIndex):
        # Try match by upper (most common for yfinance .upper() tickers)
        if ticker.upper() in [c[1] for c in df.columns]:
            df = df.xs(ticker.upper(), axis=1, level=1, drop_level=True)
            debug_info['flattened'] = f'Flattened MultiIndex using {ticker.upper()}'
        elif ticker.lower() in [c[1].lower() for c in df.columns]:
            col_map = {c: c[0] for c in df.columns if c[1].lower() == ticker.lower()}
            df = df[list(col_map.keys())]
            df.columns = list(col_map.values())
            debug_info['flattened'] = f'Flattened MultiIndex using fallback {ticker}'
        else:
            debug_info['flattened'] = f'MultiIndex present but ticker not found in columns ({ticker})'
    else:
        debug_info['flattened'] = 'No MultiIndex, already flat'

    # Check for missing or malformed data
    if df.empty or not set(['Open', 'High', 'Low', 'Close', 'Volume']).issubset(df.columns):
        debug_info['error'] = 'Missing OHLCV columns after flattening'
        return pd.DataFrame(), debug_info

    try:
        df_ta = add_all_ta_features(df, open="Open", high="High", low="Low", close="Close", volume="Volume")
        debug_info['ta_shape'] = df_ta.shape
        return df_ta, debug_info
    except Exception as e:
        debug_info['error'] = f"TA error: {e}"
        return df, debug_info

def score_momentum(df):
    # You can expand this scoring logic!
    try:
        if 'momentum_rsi' in df.columns:
            return float(df['momentum_rsi'].iloc[-1])
        elif 'rsi_14' in df.columns:
            return float(df['rsi_14'].iloc[-1])
        else:
            return float(df['Close'].iloc[-1])  # fallback: price
    except Exception:
        return 0

# --- UI: Sidebar, Universe, Excel Upload ---
st.sidebar.title("Swing Trading Scanner Pro")
st.sidebar.markdown("Upload an Excel file (.xlsx) with a column named 'Ticker' or 'Symbol'")

uploaded_file = st.sidebar.file_uploader("Drag and drop file here", type=["xlsx"])
watchlist = None
if uploaded_file:
    df_xl = pd.read_excel(uploaded_file)
    col = next((c for c in df_xl.columns if c.lower() in ['ticker', 'symbol']), None)
    if col:
        watchlist = pd.Series(df_xl[col].dropna().astype(str).str.strip().str.upper().unique()).tolist()
        st.sidebar.success(f"Loaded {len(watchlist)} tickers from Excel: {col}")
    else:
        st.sidebar.error("Could not find 'Ticker' or 'Symbol' column in Excel.")
else:
    # Default universe if nothing uploaded
    watchlist = ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'TSLA', 'NVDA', 'PYPL', 'ADBE', 'NFLX']

st.sidebar.markdown("#### Current Universe")
for t in watchlist:
    st.sidebar.write(f"- {t}")

time_frame = st.sidebar.selectbox("Time Frame", ["1d", "1wk"], index=0)
min_score = st.sidebar.slider("Minimum Quality Score", 0, 100, 18)
max_results = st.sidebar.slider("Max Results", 5, 50, 15)

st.title("📈 Swing Trading Scanner Pro")
st.caption("Your professional dashboard for swing trading opportunities — with technicals, charts, Excel export, and diagnostics.")

# --- Scan Button ---
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
        # Example: RSI, MACD, Volume, Price, etc.
        rsi = df['momentum_rsi'].iloc[-1] if 'momentum_rsi' in df.columns else None
        macd = df['trend_macd'].iloc[-1] if 'trend_macd' in df.columns else None
        close = df['Close'].iloc[-1] if 'Close' in df.columns else None
        volume = df['Volume'].iloc[-1] if 'Volume' in df.columns else None
        results.append({'Ticker': ticker, 'Score': score, 'RSI': rsi, 'MACD': macd, 'Price': close, 'Volume': volume})
    scan_df = pd.DataFrame(results)
    scan_df = scan_df[scan_df['Score'] >= min_score].sort_values("Score", ascending=False).head(max_results)
    st.session_state.scan_results = scan_df
    st.session_state.debug_log = debug_log

scan_df = st.session_state.scan_results
debug_log = st.session_state.debug_log

# --- Results Table ---
if not scan_df.empty:
    st.subheader("Scan Results")
    st.dataframe(scan_df, use_container_width=True)
    st.download_button("Download Results as CSV", scan_df.to_csv(index=False), "scan_results.csv")
    # Optional: Excel export (only if openpyxl is in requirements)
    try:
        import io
        output = io.BytesIO()
        scan_df.to_excel(output, index=False, engine='openpyxl')
        st.download_button("Download Results as Excel", output.getvalue(), "scan_results.xlsx")
    except Exception:
        pass
else:
    st.info("Run a scan to see results.")

# --- Debug Info / Raw Log ---
with st.expander("Debug Info / Raw Log", expanded=False):
    st.write("Full debug info for each ticker (data shapes, errors, flattening status, etc):")
    st.json(debug_log)

# --- Single Ticker Diagnostics + Chart ---
st.markdown("### Single Ticker Data Test (Diagnostics)")
col1, col2, col3 = st.columns(3)
with col1:
    test_ticker = st.text_input("Test a ticker (e.g. MC.PA, AAPL, ORA.PA, SAN.PA):", value=watchlist[0])
with col2:
    test_period = st.selectbox("Test period", ["6mo", "1y"], index=0)
with col3:
    test_interval = st.selectbox("Test interval", ["1d", "1wk"], index=0)
if st.button("Fetch Ticker Data"):
    df, dbg = fetch_and_flatten_ticker(test_ticker, period=test_period, interval=test_interval)
    st.markdown(f"**Ticker:** {test_ticker}  \n**Period:** {test_period}  \n**Interval:** {test_interval}")
    st.code(str(dbg))
    if not df.empty:
        st.dataframe(df.tail(10), use_container_width=True)
        # Example chart: Price + RSI
        try:
            import plotly.graph_objs as go
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name="Price"))
            if 'momentum_rsi' in df.columns:
                fig.add_trace(go.Scatter(x=df.index, y=df['momentum_rsi'], name="RSI", yaxis="y2"))
                fig.update_layout(
                    yaxis2=dict(overlaying='y', side='right', title='RSI', range=[0, 100]),
                    title=f"{test_ticker.upper()} Price & RSI",
                    xaxis_title="Date", yaxis_title="Price"
                )
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.warning(f"Chart error: {e}")
    else:
        st.warning("No data returned or TA error for this ticker/period/interval.")

