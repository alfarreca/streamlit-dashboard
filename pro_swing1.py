import streamlit as st
import pandas as pd
import yfinance as yf
from ta import add_all_ta_features
import plotly.graph_objs as go
import time

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
    try:
        data = yf.download(ticker, period=period, interval=interval)
        if data.empty or len(data) < 2:
            return pd.DataFrame(), "No data returned!"
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        try:
            data_ta = add_all_ta_features(
                data, open="Open", high="High", low="Low", close="Close", volume="Volume"
            )
            return data_ta, "Downloaded OK with TA"
        except Exception as e:
            return data, f"TA error: {str(e)}"
    except Exception as e:
        return pd.DataFrame(), f"Download error: {str(e)}"
    return pd.DataFrame(), "Unknown error"

def score_momentum(data):
    # Simple scoring: latest RSI, can expand to multi-factor scoring
    if data.empty or 'momentum_rsi' not in data.columns:
        return 0
    return data['momentum_rsi'].iloc[-1]

# --- Streamlit App Config ---
st.set_page_config(
    page_title="Swing Trading Scanner Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
# <img src="https://cdn-icons-png.flaticon.com/512/9202/9202750.png" width="48" style="vertical-align:middle"> Swing Trading Scanner Pro

Your professional dashboard for swing trading opportunities — with technicals, charts, and Excel export.
""", unsafe_allow_html=True)

# --- Universe and Upload ---
SCAN_UNIVERSE = [
    'AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'TSLA', 'NVDA', 'PYPL', 'ADBE', 'NFLX'
]
TIME_FRAMES = ['1d', '1wk']

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

watchlist = excel_ticker_list or clean_tickers(SCAN_UNIVERSE)

# --- Sidebar Filters ---
time_frame = st.sidebar.selectbox("Time Frame", TIME_FRAMES, index=0)
min_score = st.sidebar.slider("Minimum Quality Score", 0, 100, 18)
max_results = st.sidebar.slider("Max Results", 5, 50, 15)

# Display current universe
st.sidebar.markdown("#### Current Universe")
for ticker in watchlist:
    st.sidebar.write(f"- {ticker}")

# --- Main SCAN LOGIC ---
def scan_universe(universe, period='6mo', interval='1d', min_score=0, max_results=10):
    results = []
    failed = []
    progress_bar = st.progress(0)
    for i, ticker in enumerate(universe):
        ticker_clean = ticker.strip()
        data, msg = get_stock_data(ticker_clean, period, interval)
        if not data.empty:
            score = score_momentum(data)
            if score >= min_score:
                results.append({'Ticker': ticker_clean, 'Score': score, 'RSI': round(data['momentum_rsi'].iloc[-1], 2) if 'momentum_rsi' in data.columns else None})
        else:
            failed.append(f"{ticker_clean}: {msg}")
        progress_bar.progress((i + 1) / len(universe))
        time.sleep(0.08)  # To avoid rate limit
    df = pd.DataFrame(results).sort_values('Score', ascending=False).head(max_results) if results else pd.DataFrame()
    return df, failed

if 'scan_results' not in st.session_state:
    st.session_state['scan_results'] = pd.DataFrame()
if 'failed' not in st.session_state:
    st.session_state['failed'] = []

if st.button("Run Scan"):
    scan_df, failed = scan_universe(
        watchlist, period='6mo', interval=time_frame, min_score=min_score, max_results=max_results
    )
    st.session_state['scan_results'] = scan_df
    st.session_state['failed'] = failed

# --- RESULTS TABLE ---
if not st.session_state['scan_results'].empty:
    st.subheader("Scan Results")
    st.dataframe(st.session_state['scan_results'], use_container_width=True)
    csv = st.session_state['scan_results'].to_csv(index=False).encode('utf-8')
    st.download_button(
        "Download Results as CSV",
        csv,
        "scan_results.csv",
        "text/csv",
        key='download-csv'
    )
else:
    st.info("Run a scan to see results.")

# --- Failed tickers
if st.session_state['failed']:
    with st.expander("Show Failed Tickers / Log"):
        st.warning(f"Failed to fetch data for {len(st.session_state['failed'])} tickers.")
        st.write(st.session_state['failed'])

# --- Single Ticker Diagnostic Panel ---
st.markdown("---")
st.subheader("Single Ticker Data Test (Diagnostics)")
col1, col2, col3 = st.columns(3)
with col1:
    test_ticker = st.text_input(
        "Test a ticker (e.g. MC.PA, AAPL, ORA.PA, SAN.PA):", "su.pa"
    )
with col2:
    test_period = st.selectbox("Test period", ["1mo", "3mo", "6mo", "1y"], index=2)
with col3:
    test_interval = st.selectbox("Test interval", TIME_FRAMES, index=0)

debug_message = ""
debug_df = pd.DataFrame()
data_ta = pd.DataFrame()

if st.button("Fetch Ticker Data"):
    try:
        data = yf.download(test_ticker, period=test_period, interval=test_interval)
        debug_df = data.copy()
        debug_message = f"Downloaded OK: shape={data.shape}"
        if not data.empty:
            # Flatten multiindex if needed
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
                debug_message += " | Flattened MultiIndex columns"
            try:
                data_ta = add_all_ta_features(
                    data, open="Open", high="High", low="Low", close="Close", volume="Volume"
                )
                debug_message += " | TA features added"
            except Exception as e:
                debug_message += f" | TA error: {str(e)}"
                data_ta = pd.DataFrame()
        else:
            debug_message = "No data returned! This ticker/interval/period combo is not supported by Yahoo, or market is closed."
            data_ta = pd.DataFrame()
    except Exception as e:
        debug_message = f"Download error: {str(e)}"
        data_ta = pd.DataFrame()

    st.markdown(f"**Ticker:** `{test_ticker}`  \n**Period:** {test_period}  \n**Interval:** {test_interval}")

    # Debug info/root-level expander
    with st.expander("Debug Info / Raw Log", expanded=True):
        st.code(f"{debug_message}\n\nReturned DataFrame shape: {debug_df.shape}\nColumns: {list(debug_df.columns)}")
        st.write("Returned head (first 3 rows):")
        st.dataframe(debug_df.head(3))
        st.write("Returned tail (last 3 rows):")
        st.dataframe(debug_df.tail(3))

    # Quick price chart (if price column exists)
    if not debug_df.empty:
        price_col = None
        for candidate in ["Close", "close", debug_df.columns[0]]:
            if candidate in debug_df.columns:
                price_col = candidate
                break
        if price_col:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=debug_df.index,
                y=debug_df[price_col],
                mode='lines',
                name='Price'
            ))
            fig.update_layout(
                title=f"{test_ticker.upper()} Price & RSI",
                xaxis_title="Date",
                yaxis_title="Price"
            )
            st.plotly_chart(fig, use_container_width=True)

    # Show last 5 rows of TA
    if not data_ta.empty:
        st.write("With TA features (last 5 rows):")
        st.dataframe(data_ta.tail(5))
