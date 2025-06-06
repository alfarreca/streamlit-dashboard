import streamlit as st
import pandas as pd
import yfinance as yf
from ta import add_all_ta_features
import io

# ----------- UTILITIES ---------------

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
    debug_log = ""
    try:
        data = yf.download(ticker, period=period, interval=interval, progress=False)
        debug_log += f"Downloaded shape: {data.shape}\nColumns: {data.columns}\n"
        # ---- FLATTEN MULTIINDEX COLUMNS if needed ---
        if isinstance(data.columns, pd.MultiIndex):
            try:
                data = data.xs(ticker.upper(), axis=1, level=1)
                debug_log += f"Flattened MultiIndex using {ticker.upper()}\n"
            except Exception:
                data.columns = data.columns.get_level_values(0)
                debug_log += f"Flattened by get_level_values(0)\n"
        data = data.dropna()
        if data.empty or len(data) < 2:
            return pd.DataFrame(), "No data (empty/yfinance error)", debug_log
        # Add all TA features
        try:
            data = add_all_ta_features(
                data, open="Open", high="High", low="Low", close="Close", volume="Volume"
            )
            debug_log += f"Added TA features: shape {data.shape}\n"
            return data, None, debug_log
        except Exception as e:
            debug_log += f"TA error: {e}\n"
            return pd.DataFrame(), f"TA error: {e}", debug_log
    except Exception as e:
        debug_log += f"Yahoo error: {e}\n"
        return pd.DataFrame(), f"Yahoo error: {e}", debug_log

def score_momentum(data):
    # Use RSI as "momentum" proxy
    if data is None or data.empty or 'momentum_rsi' not in data.columns:
        return 0
    return data['momentum_rsi'].iloc[-1]

def to_excel(df):
    # For download as Excel
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return out.getvalue()

# ----------- PAGE SETUP ---------------
st.set_page_config("Swing Trading Scanner Pro", page_icon="📈", layout="wide")

st.title("📈 Swing Trading Scanner Pro")
st.markdown(
    "Your professional dashboard for swing trading opportunities — with technicals, charts, Excel export, and full debug logging."
)

# ----------- SIDEBAR: UPLOAD & SETTINGS ---------------
st.sidebar.header("Configuration")
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
        st.sidebar.error("Could not find 'Ticker' or 'Symbol' column in the uploaded file.")

DEFAULT_TICKERS = ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'TSLA', 'NVDA', 'PYPL', 'ADBE', 'NFLX']
watchlist = excel_ticker_list or clean_tickers(DEFAULT_TICKERS)

st.sidebar.markdown("#### Current Universe")
for t in watchlist:
    st.sidebar.write(f"- {t}")

period_options = ['6mo', '3mo', '1y']
interval_options = ['1d', '1wk']

time_frame = st.sidebar.selectbox("Time Frame", interval_options, index=0)
min_score = st.sidebar.slider("Minimum Quality Score", 0, 100, 18)
max_results = st.sidebar.slider("Max Results", 5, 50, 15)

# ----------- MAIN: SCAN BUTTON ---------------
if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = None
if 'failed' not in st.session_state:
    st.session_state['failed'] = []

if st.button("Run Scan", type="primary"):
    results = []
    failed = []
    logs = []
    progress = st.progress(0)
    for i, ticker in enumerate(watchlist):
        data, err, debug = get_stock_data(ticker, period='6mo', interval=time_frame)
        if data is not None and not data.empty and err is None:
            score = score_momentum(data)
            results.append({
                "Ticker": ticker,
                "Score": score,
                "RSI": data['momentum_rsi'].iloc[-1] if 'momentum_rsi' in data.columns else None,
            })
        else:
            failed.append(f"{ticker}: {err}")
        logs.append({ticker: debug})
        progress.progress((i + 1) / len(watchlist))
    df_results = pd.DataFrame(results)
    if not df_results.empty:
        df_results = df_results.sort_values("Score", ascending=False).head(max_results)
    st.session_state['scan_results'] = df_results
    st.session_state['failed'] = failed
    st.session_state['debug_logs'] = logs

# ----------- MAIN: SCAN RESULTS ---------------
if st.session_state.get('scan_results') is not None:
    scan_df = st.session_state['scan_results']
    if not scan_df.empty:
        st.header("Scan Results")
        st.dataframe(scan_df, use_container_width=True)
        st.download_button(
            "Download Results as CSV",
            scan_df.to_csv(index=False).encode(),
            "scan_results.csv",
            "text/csv"
        )
        st.download_button(
            "Download Results as Excel",
            to_excel(scan_df),
            "scan_results.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("No scan results: Either all tickers failed, or none passed the score filter. Try lowering the minimum score or check your ticker list/data.")

# ----------- MAIN: FAILED/DEBUG LOGS ---------------
if st.session_state.get('failed'):
    with st.expander("Failed to fetch data for tickers. See below:"):
        st.write(st.session_state['failed'])

if 'debug_logs' in st.session_state:
    with st.expander("Debug Info / Raw Log"):
        for log in st.session_state['debug_logs']:
            st.code(log)

# ----------- SINGLE TICKER DIAGNOSTIC BLOCK ---------------
st.markdown("---")
st.subheader("Single Ticker Data Test (Diagnostics)")
col1, col2, col3 = st.columns([3,2,2])
with col1:
    single_ticker = st.text_input("Test a ticker (e.g. MC.PA, AAPL, ORA.PA, SAN.PA):", value=watchlist[0])
with col2:
    test_period = st.selectbox("Test period", period_options, index=0)
with col3:
    test_interval = st.selectbox("Test interval", interval_options, index=0)

if st.button("Fetch Ticker Data"):
    st.markdown(f"**Ticker:** {single_ticker}   **Period:** {test_period}   **Interval:** {test_interval}")
    df, err, debug = get_stock_data(single_ticker, period=test_period, interval=test_interval)
    with st.expander("Debug Info / Raw Log", expanded=True):
        st.code(f"Error: {err}\n{debug}")
        if df is not None and not df.empty:
            st.write("Returned DataFrame shape:", df.shape)
            st.write("Returned columns:", df.columns)
            st.write("Returned head (first 3 rows):")
            st.dataframe(df.head(3))
            st.write("Returned tail (last 3 rows):")
            st.dataframe(df.tail(3))
        else:
            st.warning("No data returned for this ticker/period/interval combo.")
    # Chart (optional)
    if df is not None and not df.empty:
        import plotly.graph_objs as go
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name="Close Price"))
        if 'momentum_rsi' in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df['momentum_rsi'], name="RSI", yaxis="y2"))
            fig.update_layout(
                yaxis2=dict(
                    title="RSI",
                    overlaying='y',
                    side='right'
                )
            )
        fig.update_layout(title=f"{single_ticker.upper()} Price & RSI", xaxis_title="Date", yaxis_title="Price")
        st.plotly_chart(fig, use_container_width=True)
        st.write("With TA features (last 5 rows):")
        st.dataframe(df.tail(5))

st.caption("Made with 💹 by your AI assistant.")
