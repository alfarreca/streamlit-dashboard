import streamlit as st
import pandas as pd
import yfinance as yf
from ta import add_all_ta_features
import plotly.graph_objs as go
import io
import xlsxwriter  # Assumes installed via requirements.txt

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
        raw_msg = f"Downloaded shape: {data.shape} Columns: {data.columns.tolist()}"
        if data.empty or len(data) < 2:
            return pd.DataFrame(), "Returned data is empty or too short."
        data = add_all_ta_features(
            data, open="Open", high="High", low="Low", close="Close", volume="Volume"
        )
        return data, raw_msg
    except Exception as e:
        return pd.DataFrame(), f"Error: {e}"

def score_momentum(data):
    if data.empty or 'momentum_rsi' not in data.columns:
        return 0
    return data['momentum_rsi'].iloc[-1]

def to_excel(df):
    output = io.BytesIO()
    try:
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        return output.getvalue()
    except Exception as e:
        st.error(f"Excel export failed: {e}")
        return None

# --- Streamlit Config ---
st.set_page_config(page_title="Swing Trading Scanner Pro", layout="wide")
st.title("📈 Swing Trading Scanner Pro")
st.caption("Your professional dashboard for swing trading opportunities — with technicals, charts, and Excel export.")

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

# --- Watchlist and Sidebar Controls ---
DEFAULT_UNIVERSE = [
    'AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'TSLA', 'NVDA', 'PYPL', 'ADBE', 'NFLX'
]
watchlist = excel_ticker_list or clean_tickers(DEFAULT_UNIVERSE)
st.sidebar.markdown("#### Current Universe")
for ticker in watchlist:
    st.sidebar.write(f"- {ticker}")

TIME_FRAMES = ['1d', '1wk']
scan_type = st.sidebar.selectbox("Time Frame", TIME_FRAMES)
min_score = st.sidebar.slider("Minimum Quality Score", 0, 100, 18)
max_results = st.sidebar.slider("Max Results", 5, 50, 15)

# --- Run Scan Logic ---
def scan_universe(universe, period='6mo', interval='1d', min_score=0, max_results=10):
    results = []
    failed = []
    debug_logs = []
    progress_bar = st.progress(0)
    for i, ticker in enumerate(universe):
        ticker_clean = ticker.strip()
        data, raw_log = get_stock_data(ticker_clean, period, interval)
        if not data.empty:
            score = score_momentum(data)
            if score >= min_score:
                results.append({'Ticker': ticker_clean, 'Score': score, 'RSI': data['momentum_rsi'].iloc[-1]})
        else:
            failed.append(f"{ticker_clean}: {raw_log}")
        debug_logs.append(f"{ticker_clean}: {raw_log}")
        progress_bar.progress((i + 1) / len(universe))
    df = pd.DataFrame(results).sort_values('Score', ascending=False).head(max_results) if results else pd.DataFrame()
    return df, failed, debug_logs

# --- Scan Button ---
if st.button("Run Scan"):
    scan_df, failed, debug_logs = scan_universe(
        watchlist, period='6mo', interval=scan_type, min_score=min_score, max_results=max_results
    )
    st.session_state['scan_results'] = scan_df
    st.session_state['failed'] = failed
    st.session_state['debug_logs'] = debug_logs

scan_df = st.session_state.get('scan_results', pd.DataFrame())
failed = st.session_state.get('failed', [])
debug_logs = st.session_state.get('debug_logs', [])

# --- Show Results Table ---
if not scan_df.empty:
    st.subheader("Scan Results")
    st.dataframe(scan_df, use_container_width=True)
    # Download as CSV
    st.download_button("Download Results as CSV", scan_df.to_csv(index=False), "scan_results.csv")
    # Download as Excel (now robust)
    excel_bytes = to_excel(scan_df)
    if excel_bytes:
        st.download_button("Download Results as Excel", excel_bytes, "scan_results.xlsx")
else:
    st.warning("No scan results: Either all tickers failed, or none passed the score filter. Try lowering the minimum score or check your ticker list/data.")

# --- Show Debug Info ---
if debug_logs:
    with st.expander("Debug Info / Raw Log"):
        st.code("\n".join(debug_logs), language='text')
if failed:
    st.warning(f"Failed to fetch data for {len(failed)} tickers. See below:")
    st.write(failed)

# --- Single Ticker Diagnostic & Live Chart ---
with st.expander("Single Ticker Data Test (Diagnostics)", expanded=True):
    test_ticker = st.text_input("Test a ticker (e.g. MC.PA, AAPL, ORA.PA, SAN.PA):", value=watchlist[0])
    test_period = st.selectbox("Test period", ['6mo', '1y', '3mo', '1mo'], index=0)
    test_interval = st.selectbox("Test interval", TIME_FRAMES, index=0)
    if st.button("Fetch Ticker Data"):
        diag_df, diag_log = get_stock_data(test_ticker, test_period, test_interval)
        st.write(f"**Ticker:** {test_ticker}  **Period:** {test_period}  **Interval:** {test_interval}")
        if diag_df.empty:
            st.error("No data returned! This ticker/interval/period combo is not supported by Yahoo, or market is closed.")
        else:
            st.dataframe(diag_df.tail(10))
            # Plotly live chart (candlestick + RSI)
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=diag_df.index,
                open=diag_df['Open'],
                high=diag_df['High'],
                low=diag_df['Low'],
                close=diag_df['Close'],
                name="Price"
            ))
            if 'momentum_rsi' in diag_df.columns:
                fig.add_trace(go.Scatter(
                    x=diag_df.index,
                    y=diag_df['momentum_rsi'],
                    yaxis='y2',
                    name="RSI",
                    line=dict(color='blue')
                ))
                fig.update_layout(
                    yaxis2=dict(title='RSI', overlaying='y', side='right'),
                    title=f"{test_ticker} Price & RSI"
                )
            st.plotly_chart(fig, use_container_width=True)
        with st.expander("Show Debug Info / Raw Log (Single Ticker)"):
            st.code(diag_log)

# --- End of App ---
