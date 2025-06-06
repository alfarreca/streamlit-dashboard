import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import plotly.graph_objects as go
import io
from ta import add_all_ta_features

# --- CONFIG ---
st.set_page_config(
    page_title="Swing Trading Scanner Pro",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
)

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
    try:
        data = yf.download(ticker, period=period, interval=interval)
        if data.empty or len(data) < 2:
            return pd.DataFrame(), "No data (empty/yfinance error)"
        # Add all TA features
        try:
            data = add_all_ta_features(
                data, open="Open", high="High", low="Low", close="Close", volume="Volume"
            )
            return data, None
        except Exception as e:
            return pd.DataFrame(), f"TA error: {e}"
    except Exception as e:
        return pd.DataFrame(), f"Yahoo error: {e}"

def score_momentum(data):
    if data.empty or "momentum_rsi" not in data.columns:
        return np.nan
    return data['momentum_rsi'].iloc[-1]

# --- FILE UPLOAD ---
st.sidebar.title("Swing Trading Scanner Pro")
uploaded_file = st.sidebar.file_uploader(
    "Upload an Excel file (.xlsx) with a column named 'Ticker' or 'Symbol'", type=["xlsx"]
)
SCAN_UNIVERSE = [
    'AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'TSLA', 'NVDA', 'PYPL', 'ADBE', 'NFLX'
]
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

# --- SIDEBAR CONTROLS ---
st.sidebar.subheader("Configuration")
TIME_FRAMES = ['1d', '1wk']
period = st.sidebar.selectbox("Time Frame", TIME_FRAMES)
min_score = st.sidebar.slider("Minimum Quality Score", 0, 100, 18)
max_results = st.sidebar.slider("Max Results", 5, 50, 15)

# --- MAIN TITLE ---
st.markdown("<h1 style='color:#2357ad;font-weight:800;'>📈 Swing Trading Scanner Pro</h1>", unsafe_allow_html=True)
st.write("Your professional dashboard for swing trading opportunities — with technicals, charts, and Excel export.")

# --- SCANNING LOGIC ---
def scan_universe(universe, period, interval, min_score, max_results):
    results = []
    failed = []
    raw_log = []
    progress = st.progress(0)
    for i, ticker in enumerate(universe):
        data, error = get_stock_data(ticker, period=f"6mo", interval=interval)
        if error:
            failed.append(f"{ticker}: {error}")
            raw_log.append(f"{ticker}: {error}")
            continue
        if not data.empty:
            score = score_momentum(data)
            if pd.notnull(score) and score >= min_score:
                results.append({
                    'Ticker': ticker,
                    'Score': round(score, 2),
                    'RSI': round(score, 2)
                })
        else:
            failed.append(f"{ticker}: No data")
        progress.progress((i + 1) / len(universe))
    df = pd.DataFrame(results).sort_values('Score', ascending=False).head(max_results) if results else pd.DataFrame()
    return df, failed, raw_log

# --- SCAN BUTTON ---
if st.button("Run Scan"):
    scan_df, failed, raw_log = scan_universe(
        watchlist,
        period='6mo',
        interval=period,
        min_score=min_score,
        max_results=max_results,
    )
    st.session_state['scan_results'] = scan_df
    st.session_state['failed'] = failed
    st.session_state['raw_log'] = raw_log

scan_df = st.session_state.get('scan_results', pd.DataFrame())
failed = st.session_state.get('failed', [])
raw_log = st.session_state.get('raw_log', [])

if not scan_df.empty:
    st.subheader("Scan Results")
    st.dataframe(scan_df)
    # --- Download as Excel ---
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        scan_df.to_excel(writer, index=False)
    excel_data = output.getvalue()
    st.download_button(
        "Download Results as Excel",
        data=excel_data,
        file_name="scan_results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("Run a scan to see results.")

# --- FAILED LOG/DEBUG SECTION ---
if failed:
    with st.expander("Debug Info / Raw Log"):
        st.warning(f"Failed to fetch data for {len(failed)} tickers. See below:")
        st.write(failed)
        st.write("---")
        st.write("Raw Log:")
        st.write(raw_log)

# --- SINGLE TICKER DIAGNOSTIC ---
with st.expander("Single Ticker Data Test (Diagnostics)"):
    ticker = st.text_input("Test a ticker (e.g. MC.PA, AAPL, ORA.PA, SAN.PA):", value=watchlist[0] if watchlist else "AAPL")
    test_period = st.selectbox("Test period", ['6mo', '1y', '3mo'], key='period_test')
    test_interval = st.selectbox("Test interval", ['1d', '1wk'], key='interval_test')
    if st.button("Fetch Ticker Data"):
        data, error = get_stock_data(ticker, period=test_period, interval=test_interval)
        st.write(f"**Ticker:** {ticker}  \n**Period:** {test_period}  \n**Interval:** {test_interval}")
        if error:
            st.error(error)
        elif data.empty:
            st.warning("No data returned!")
        else:
            st.dataframe(data.head(10))
            st.write("TA Columns:", list(data.columns))
            # --- Chart ---
            if 'Close' in data.columns and 'momentum_rsi' in data.columns:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=data.index, y=data['Close'], name="Price"))
                fig.add_trace(go.Scatter(x=data.index, y=data['momentum_rsi'], name="RSI"))
                fig.update_layout(title=f"{ticker} Price & RSI", yaxis_title="Price / RSI")
                st.plotly_chart(fig, use_container_width=True)
