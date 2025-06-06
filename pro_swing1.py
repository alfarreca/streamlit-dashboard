import streamlit as st
import pandas as pd
import yfinance as yf
from ta import add_all_ta_features
import plotly.graph_objs as go

st.set_page_config("Swing Trading Scanner Pro", layout="wide")

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
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        if df.empty or len(df) < 2:
            return pd.DataFrame()
        df = add_all_ta_features(
            df, open="Open", high="High", low="Low", close="Close", volume="Volume"
        )
        return df
    except Exception as e:
        return pd.DataFrame()  # Return empty on error

def score_momentum(data):
    if data.empty or 'momentum_rsi' not in data.columns:
        return 0
    return data['momentum_rsi'].iloc[-1]

# --- Layout ---
st.title("📈 Swing Trading Scanner Pro")
st.caption("Your professional dashboard for swing trading opportunities — with technicals, charts, and Excel export.")

# --- Excel Upload / Universe ---
st.sidebar.header("Configuration")
uploaded_file = st.sidebar.file_uploader("Upload an Excel file (.xlsx) with a column named 'Ticker' or 'Symbol'", type=["xlsx"])
excel_ticker_list = None
if uploaded_file:
    df_excel = pd.read_excel(uploaded_file)
    ticker_col = next((col for col in df_excel.columns if col.lower() in ['ticker', 'symbol']), None)
    if ticker_col:
        excel_ticker_list = clean_tickers(df_excel[ticker_col].tolist())
        st.sidebar.success(f"Loaded {len(excel_ticker_list)} tickers from Excel: {ticker_col}")
    else:
        st.sidebar.error("Could not find 'Ticker' or 'Symbol' column in Excel.")

default_universe = ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'TSLA', 'NVDA', 'PYPL', 'ADBE', 'NFLX']
watchlist = excel_ticker_list or clean_tickers(default_universe)
st.sidebar.markdown("#### Current Universe")
for t in watchlist:
    st.sidebar.write(f"- {t}")

# --- Filters ---
time_frame = st.sidebar.selectbox("Time Frame", ['1d', '1wk'], index=0)
min_score = st.sidebar.slider("Minimum Quality Score", 0, 100, 18)
max_results = st.sidebar.slider("Max Results", 5, 50, 15)

# --- Scan Logic ---
def scan_universe(universe, period='6mo', interval='1d', min_score=0, max_results=10):
    results = []
    failed = []
    progress = st.progress(0, text="Scanning tickers...")
    for i, ticker in enumerate(universe):
        data = get_stock_data(ticker, period=period, interval=interval)
        if not data.empty:
            score = score_momentum(data)
            if score >= min_score:
                results.append({
                    'Ticker': ticker,
                    'Score': round(score, 2),
                    'Price': round(data['Close'].iloc[-1], 2),
                    'Change %': round(100 * (data['Close'].iloc[-1] / data['Close'].iloc[-2] - 1), 3) if len(data['Close']) > 1 else 0,
                    'Volume': int(data['Volume'].iloc[-1]),
                    'RSI': round(data['momentum_rsi'].iloc[-1], 2) if 'momentum_rsi' in data.columns else None,
                    'MACD': round(data['trend_macd'].iloc[-1], 3) if 'trend_macd' in data.columns else None
                })
        else:
            failed.append(ticker)
        progress.progress((i+1)/len(universe))
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values("Score", ascending=False).head(max_results)
    return df, failed

# --- Scan Button ---
if st.button("Run Scan"):
    scan_df, failed = scan_universe(watchlist, period='6mo', interval=time_frame, min_score=min_score, max_results=max_results)
    st.session_state['scan_results'] = scan_df
    st.session_state['failed'] = failed

scan_df = st.session_state.get('scan_results', pd.DataFrame())
failed = st.session_state.get('failed', [])

if not scan_df.empty:
    st.subheader("Scan Results")
    st.dataframe(scan_df, use_container_width=True)
    st.download_button("Download Results as CSV", scan_df.to_csv(index=False), "scan_results.csv")
    st.download_button("Download Results as Excel", scan_df.to_excel(index=False), "scan_results.xlsx")
else:
    st.info("Run a scan to see results.")
    if failed:
        st.warning(f"No results found. All tickers may have failed data download, or none meet the score threshold.")

# --- Single Ticker Diagnostic ---
with st.expander("Single Ticker Data Test (Diagnostics)"):
    col1, col2, col3 = st.columns(3)
    with col1:
        single_ticker = st.text_input("Test a ticker (e.g. MC.PA, AAPL, ORA.PA, SAN.PA):", value=watchlist[0])
    with col2:
        single_period = st.selectbox("Test period", ["6mo", "1y", "1mo"], index=0)
    with col3:
        single_interval = st.selectbox("Test interval", ["1d", "1wk"], index=0)
    if st.button("Fetch Ticker Data"):
        df_single = get_stock_data(single_ticker, period=single_period, interval=single_interval)
        st.markdown(f"**Ticker:** {single_ticker}\n\n**Period:** {single_period}\n\n**Interval:** {single_interval}")
        if not df_single.empty:
            st.dataframe(df_single.tail(10))
            # --- Plotly Chart ---
            chart = go.Figure()
            chart.add_trace(go.Candlestick(
                x=df_single.index,
                open=df_single['Open'],
                high=df_single['High'],
                low=df_single['Low'],
                close=df_single['Close'],
                name="Candlestick"
            ))
            if 'momentum_rsi' in df_single.columns:
                chart.add_trace(go.Scatter(
                    x=df_single.index, y=df_single['momentum_rsi'],
                    yaxis="y2", name="RSI", line=dict(color='orange')
                ))
            chart.update_layout(
                xaxis_rangeslider_visible=False,
                yaxis=dict(title='Price'),
                yaxis2=dict(title='RSI', overlaying='y', side='right', showgrid=False),
                height=450
            )
            st.plotly_chart(chart, use_container_width=True)
        else:
            st.error("No data returned! This ticker/interval/period combo is not supported by Yahoo, or market is closed.")

