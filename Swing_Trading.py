import streamlit as st
import pandas as pd
import yfinance as yf
from ta import add_all_ta_features

# Always clean tickers (removes quotes, whitespace, ensures uppercase)
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

st.set_page_config(
    page_title="Swing Trading Scanner Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

SCAN_UNIVERSE = ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'TSLA', 'NVDA', 'PYPL', 'ADBE', 'NFLX']
TIME_FRAMES = ['1d', '1wk']

uploaded_file = st.file_uploader(
    "Upload an Excel file (.xlsx) with a column named 'Ticker' or 'Symbol'", 
    type=["xlsx"]
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

st.sidebar.markdown("#### Current Universe")
st.sidebar.write(st.session_state.watchlist)

def get_stock_data(ticker, period='6mo', interval='1d'):
    data = yf.download(ticker, period=period, interval=interval)
    if data.empty or len(data) < 2:
        return pd.DataFrame()
    try:
        data = add_all_ta_features(
            data,
            open="Open",
            high="High",
            low="Low",
            close="Close",
            volume="Volume"
        )
    except Exception as e:
        print(f"Technical analysis error for {ticker}: {e}")
        return pd.DataFrame()
    return data

def scan_universe(universe, period='6mo'):
    results = []
    progress_bar = st.progress(0)
    for i, ticker in enumerate(universe):
        ticker_clean = ticker.strip()
        data = get_stock_data(ticker_clean, period)
        if not data.empty:
            score = data['momentum_rsi'].iloc[-1]
            results.append({'Ticker': ticker_clean, 'Score': score})
        progress_bar.progress((i + 1) / len(universe))

    return pd.DataFrame(results).sort_values('Score', ascending=False) if results else pd.DataFrame()

if st.sidebar.button("Run Scan", type="primary"):
    st.session_state.scanned_results = scan_universe(st.session_state.watchlist)

if not st.session_state.get('scanned_results', pd.DataFrame()).empty:
    st.subheader("Scan Results")
    st.dataframe(st.session_state.scanned_results)
else:
    st.info("Click 'Run Scan' to find swing trading opportunities")
