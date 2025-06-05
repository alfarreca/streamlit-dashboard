import streamlit as st
import pandas as pd
import yfinance as yf
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
    data = yf.download(ticker, period=period, interval=interval)
    if data.empty or len(data) < 2:
        return pd.DataFrame()
    try:
        data = add_all_ta_features(
            data, open="Open", high="High", low="Low", close="Close", volume="Volume"
        )
    except Exception as e:
        print(f"TA error for {ticker}: {e}")
        return pd.DataFrame()
    return data

def score_momentum(data):
    if data.empty:
        return 0
    return data['momentum_rsi'].iloc[-1]

# --- Streamlit App Config ---
st.set_page_config(
    page_title="Swing Trading Scanner Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Universe and Upload ---
SCAN_UNIVERSE = ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'TSLA', 'NVDA', 'PYPL', 'ADBE', 'NFLX']
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

# --- Sidebar Filters ---
st.sidebar.title("Swing Trading Scanner Pro")
st.sidebar.subheader("Configuration")
with st.sidebar.expander("Scan Settings", expanded=True):
    scan_type = st.selectbox(
        "Scan Type",
        ["Momentum Opportunities", "Mean Reversion", "Breakouts", "All Opportunities"]
    )
    time_frame = st.selectbox("Time Frame", TIME_FRAMES)
    min_score = st.slider("Minimum Quality Score", 0, 100, 18)
    max_results = st.slider("Max Results", 5, 50, 15)

# Display current universe
st.sidebar.markdown("#### Current Universe")
for ticker in st.session_state.watchlist:
    st.sidebar.write(f"- {ticker}")

# --- Scanning Logic ---
def scan_universe(universe, period='6mo', scan_type="Momentum Opportunities", min_score=0, max_results=10):
    results = []
    progress_bar = st.progress(0)
    for i, ticker in enumerate(universe):
        ticker_clean = ticker.strip()
        data = get_stock_data(ticker_clean, period)
        if not data.empty:
            # Only a basic scoring; expand per scan_type as needed
            if scan_type == "Momentum Opportunities":
                score = score_momentum(data)
            else:
                score = score_momentum(data)  # Placeholder: you can customize for each scan type
            if score >= min_score:
                results.append({'Ticker': ticker_clean, 'Score': score})
        progress_bar.progress((i + 1) / len(universe))
    if results:
        return pd.DataFrame(results).sort_values('Score', ascending=False).head(max_results)
    else:
        return pd.DataFrame()

# --- Main Page ---
if st.sidebar.button("Run Scan", type="primary"):
    st.session_state.scanned_results = scan_universe(
        st.session_state.watchlist,
        period='6mo',
        scan_type=scan_type,
        min_score=min_score,
        max_results=max_results
    )

if not st.session_state.get('scanned_results', pd.DataFrame()).empty:
    st.subheader("Scan Results")
    st.dataframe(st.session_state.scanned_results)
else:
    st.info("Click 'Run Scan' to find swing trading opportunities")

