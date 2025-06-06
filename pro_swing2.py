import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from ta import add_all_ta_features
import plotly.graph_objs as go
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

def get_stock_data(ticker, period='6mo', interval='1d'):
    data = yf.download(ticker, period=period, interval=interval)
    debug = {}
    debug['raw_shape'] = data.shape
    debug['columns'] = list(data.columns)
    debug['head'] = data.head(2).to_dict()
    # MultiIndex fix
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    debug['flat_columns'] = list(data.columns)
    if data.empty or len(data) < 2:
        debug['error'] = 'Empty DataFrame'
        return pd.DataFrame(), debug
    try:
        data = add_all_ta_features(
            data, open="Open", high="High", low="Low", close="Close", volume="Volume"
        )
        debug['ta_cols'] = list(data.columns)
    except Exception as e:
        debug['ta_error'] = str(e)
        return pd.DataFrame(), debug
    return data, debug

def score_momentum(data):
    if data.empty or 'momentum_rsi' not in data.columns:
        return np.nan
    return data['momentum_rsi'].iloc[-1]

# --- Streamlit App Config ---
st.set_page_config(
    page_title="Swing Trading Scanner Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📝 Swing Trading Scanner Pro")
st.markdown("""
Your professional dashboard for swing trading opportunities — with technicals, charts, and Excel export.
""")

# --- Universe and Upload ---
SCAN_UNIVERSE = [
    'AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'TSLA', 'NVDA', 'PYPL', 'ADBE', 'NFLX'
]
TIME_FRAMES = ['1d', '1wk']

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
st.sidebar.title("Swing Trading Scanner Pro")
st.sidebar.subheader("Configuration")
with st.sidebar.expander("Scan Settings", expanded=True):
    time_frame = st.selectbox("Time Frame", TIME_FRAMES)
    min_score = st.slider("Minimum Quality Score", 0, 100, 18)
    max_results = st.slider("Max Results", 5, 50, 15)

st.sidebar.markdown("#### Current Universe")
for ticker in watchlist:
    st.sidebar.write(f"- {ticker}")

# --- Scanning Logic ---
def scan_universe(universe, period='6mo', interval='1d', min_score=0, max_results=10):
    results = []
    failed = []
    logs = []
    progress_bar = st.progress(0, text="Scanning universe...")
    for i, ticker in enumerate(universe):
        ticker_clean = ticker.strip()
        data, debug = get_stock_data(ticker_clean, period, interval)
        if not data.empty:
            score = score_momentum(data)
            if pd.notna(score) and score >= min_score:
                results.append({
                    'Ticker': ticker_clean,
                    'Score': score,
                    'RSI': round(data['momentum_rsi'].iloc[-1], 2) if 'momentum_rsi' in data.columns else np.nan,
                })
        else:
            failed.append(f"{ticker_clean}: Error: {debug.get('ta_error', debug.get('error',''))}")
        progress_bar.progress((i + 1) / len(universe), text=f"Scanning {ticker_clean}")
    df = pd.DataFrame(results).sort_values('Score', ascending=False).head(max_results) if results else pd.DataFrame()
    return df, failed

# --- Main Page ---
if st.button("Run Scan"):
    scan_df, failed = scan_universe(
        watchlist,
        period='6mo',
        interval=time_frame,
        min_score=min_score,
        max_results=max_results
    )
    st.session_state['scan_results'] = scan_df
    st.session_state['failed'] = failed

scan_df = st.session_state.get('scan_results', pd.DataFrame())
failed = st.session_state.get('failed', [])

if not scan_df.empty:
    st.subheader("Scan Results")
    st.dataframe(scan_df)
    st.download_button("Download Results as Excel",
                      data=scan_df.to_excel(index=False, engine="openpyxl"),
                      file_name="scan_results.xlsx")
elif failed:
    st.warning("No scan results: Either all tickers failed, or none passed the score filter. Try lowering the minimum score or check your ticker list/data.")

if failed:
    with st.expander("Debug Info / Raw Log"):
        st.write("Failed to fetch data for these tickers. See below:")
        st.json(failed)

# --- Single Ticker Test / Diagnostics ---
with st.expander("Single Ticker Data Test (Diagnostics)", expanded=True):
    col1, col2, col3 = st.columns([3,2,2])
    with col1:
        ticker_test = st.text_input("Test a ticker (e.g. MC.PA, AAPL, ORA.PA, SAN.PA):", value=watchlist[0] if watchlist else "AAPL")
    with col2:
        test_period = st.selectbox("Test period", ["6mo", "3mo", "1mo"], index=0)
    with col3:
        test_interval = st.selectbox("Test interval", ["1d", "1wk"], index=0)

    if st.button("Fetch Ticker Data"):
        data, debug = get_stock_data(ticker_test, test_period, test_interval)
        st.markdown(f"**Ticker:** {ticker_test}  \n**Period:** {test_period}  \n**Interval:** {test_interval}")
        if data.empty:
            st.error(f"No data returned! This ticker/interval/period combo is not supported by Yahoo, or market is closed.")
            with st.expander("Debug Info / Raw Log", expanded=True):
                st.write(debug)
        else:
            st.markdown("**Raw Yahoo data:**")
            st.dataframe(data.head(10))
            # Chart: Price & RSI
            if "momentum_rsi" in data.columns:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=data.index, y=data["Close"], name="Price", yaxis="y1"))
                fig.add_trace(go.Scatter(x=data.index, y=data["momentum_rsi"], name="RSI", yaxis="y2"))
                fig.update_layout(
                    title=f"{ticker_test} Price & RSI",
                    yaxis=dict(title="Price", side='left'),
                    yaxis2=dict(title="RSI", overlaying='y', side='right', range=[0,100]),
                    legend=dict(orientation="h"),
                )
                st.plotly_chart(fig, use_container_width=True)
            st.markdown("**With TA features (last 5 rows):**")
            st.dataframe(data.tail(5))

# --- End of Script ---
