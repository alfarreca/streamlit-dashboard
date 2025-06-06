import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objs as go
from ta import add_all_ta_features

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

def get_stock_data(ticker, period='6mo', interval='1d'):
    """Return: (data, debug_msg, error_msg)"""
    debug_msg = ""
    error_msg = ""
    try:
        raw = yf.download(ticker, period=period, interval=interval)
        debug_msg += f"Returned DataFrame shape: {raw.shape}\n"
        debug_msg += f"Columns: {list(raw.columns)}\n"
        if raw.empty:
            error_msg = "Yahoo returned an empty DataFrame (possibly unsupported combo or closed market)."
            return pd.DataFrame(), debug_msg, error_msg
        # Handle multi-index columns (e.g., ('Close', 'MC.PA')) as in EU tickers
        if isinstance(raw.columns, pd.MultiIndex):
            # Take only the relevant ticker
            subcols = [col for col in raw.columns if col[1].upper() == ticker.upper()]
            data = raw[subcols]
            data.columns = [col[0] for col in data.columns]
        else:
            data = raw
        # Standardize columns
        data = data.rename(
            columns={c: c.capitalize() for c in data.columns}
        )
        if not all(x in data.columns for x in ['Open', 'High', 'Low', 'Close', 'Volume']):
            error_msg = f"Yahoo missing required columns: {data.columns}"
            return pd.DataFrame(), debug_msg, error_msg
        # Add TA features
        data = add_all_ta_features(
            data, open="Open", high="High", low="Low", close="Close", volume="Volume"
        )
        return data, debug_msg, ""
    except Exception as e:
        error_msg = f"TA error: {e}"
        return pd.DataFrame(), debug_msg, error_msg

def score_momentum(data):
    if data.empty or 'momentum_rsi' not in data:
        return 0
    return data['momentum_rsi'].iloc[-1]

# --- Streamlit Config ---
st.set_page_config(
    page_title="Swing Trading Scanner Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(
    """
    <style>
    .big-title {font-size: 2.7rem !important; font-weight: 700;}
    .info-header {font-size: 1.18rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Header ---
st.markdown("<span class='big-title'>📈 Swing Trading Scanner Pro</span>", unsafe_allow_html=True)
st.markdown("<span class='info-header'>Your professional dashboard for swing trading opportunities — with technicals, charts, and Excel export.</span>", unsafe_allow_html=True)

# --- Sidebar Config ---
st.sidebar.title("Swing Trading Scanner Pro")
st.sidebar.subheader("Configuration")

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

SCAN_UNIVERSE = [
    'AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'TSLA', 'NVDA', 'PYPL', 'ADBE', 'NFLX'
]
TIME_FRAMES = ['1d', '1wk']
watchlist = excel_ticker_list or clean_tickers(SCAN_UNIVERSE)

st.sidebar.selectbox("Time Frame", TIME_FRAMES, key="time_frame")
st.sidebar.slider("Minimum Quality Score", 0, 100, 18, key="min_score")
st.sidebar.slider("Max Results", 5, 50, 15, key="max_results")

st.sidebar.markdown("#### Current Universe")
for ticker in watchlist:
    st.sidebar.write(f"- {ticker}")

# --- Scanning Logic ---
def scan_universe(universe, period='6mo', interval='1d', min_score=0, max_results=10):
    results = []
    failed = []
    for ticker in universe:
        data, dbg, err = get_stock_data(ticker, period, interval)
        if not data.empty:
            score = score_momentum(data)
            if score >= min_score:
                results.append({'Ticker': ticker, 'Score': score, 'RSI': data['momentum_rsi'].iloc[-1]})
        else:
            failed.append((ticker, dbg, err))
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values('Score', ascending=False).head(max_results)
    return df, failed

# --- Scan Results ---
if st.button("Run Scan"):
    scan_df, failed = scan_universe(
        watchlist,
        period='6mo',
        interval=st.session_state.time_frame,
        min_score=st.session_state.min_score,
        max_results=st.session_state.max_results,
    )
    st.session_state['scan_results'] = scan_df
    st.session_state['failed'] = failed

if 'scan_results' in st.session_state and not st.session_state.scan_results.empty:
    st.subheader("Scan Results")
    st.dataframe(st.session_state.scan_results, use_container_width=True)
    st.download_button("Download Results as CSV", st.session_state.scan_results.to_csv(index=False), "results.csv")
elif 'failed' in st.session_state and st.session_state.failed:
    st.warning("No results found. All tickers may have failed data download, or none meet the score threshold.")

# --- Single Ticker Diagnostics with Debug Info ---
with st.expander("Single Ticker Data Test (Diagnostics)"):
    col1, col2, col3 = st.columns([2,1,1])
    with col1:
        ticker_input = st.text_input("Test a ticker (e.g. MC.PA, AAPL, ORA.PA, SAN.PA):", value=watchlist[0] if watchlist else "")
    with col2:
        period_input = st.selectbox("Test period", ['6mo', '3mo', '1mo'], index=0)
    with col3:
        interval_input = st.selectbox("Test interval", TIME_FRAMES, index=0)
    if st.button("Fetch Ticker Data"):
        data, dbg, err = get_stock_data(ticker_input, period_input, interval_input)
        st.markdown(f"**Ticker:** {ticker_input} &nbsp; **Period:** {period_input} &nbsp; **Interval:** {interval_input}")
        with st.expander("Debug Info / Raw Log", expanded=True):
            st.code(
                f"Debug message: {err or 'No error.'}\n"
                f"Returned DataFrame shape: {data.shape}\n"
                f"Columns: {list(data.columns) if not data.empty else 'empty'}\n"
            )
            if dbg: st.text(dbg)
            if not data.empty:
                st.write("Returned head (first 3 rows):")
                st.dataframe(data.head(3))
                st.write("Returned tail (last 3 rows):")
                st.dataframe(data.tail(3))
        if not data.empty:
            st.markdown(f"#### {ticker_input.upper()} Price & RSI")
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=data.index, y=data['Close'], name="Close"))
            if 'momentum_rsi' in data:
                fig.add_trace(go.Scatter(x=data.index, y=data['momentum_rsi'], name="RSI"))
            fig.update_layout(xaxis_title="Date", yaxis_title="Price", legend_title="Legend")
            st.plotly_chart(fig, use_container_width=True)
            st.write("With TA features (last 5 rows):")
            st.dataframe(data.tail(5))
        else:
            st.error(err or "No data returned! This ticker/interval/period combo is not supported by Yahoo, or market is closed.")

# --- (Placeholder for Advanced Features) ---
# Add: sector filter, advanced indicators, Excel export, technical highlight cards, etc.
