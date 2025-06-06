import streamlit as st
import pandas as pd
import yfinance as yf
from ta import add_all_ta_features
import plotly.graph_objects as go
import numpy as np
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
    try:
        data = yf.download(ticker, period=period, interval=interval, progress=False)
        if data.empty or len(data) < 2:
            return pd.DataFrame(), "Empty dataframe"
        try:
            data_ta = add_all_ta_features(
                data.copy(), open="Open", high="High", low="Low", close="Close", volume="Volume"
            )
        except Exception as e:
            return data, f"TA error: {e}"
        return data_ta, "OK"
    except Exception as e:
        return pd.DataFrame(), str(e)

def scan_universe(universe, period, interval, min_score, max_results):
    results = []
    failed = []
    progress_bar = st.progress(0)
    for i, ticker in enumerate(universe):
        df, msg = get_stock_data(ticker, period, interval)
        if not df.empty and 'momentum_rsi' in df.columns:
            last = df.iloc[-1]
            score = last['momentum_rsi']
            result = {
                "Ticker": ticker,
                "Score": score,
                "Price": last["Close"],
                "Change %": (last["Close"] - df["Close"].iloc[-2]) / df["Close"].iloc[-2] * 100 if len(df) > 1 else 0,
                "Volume": last["Volume"],
                "RSI": last["momentum_rsi"],
                "MACD": last.get("trend_macd", np.nan),
                "BB %": last.get("volatility_bbm", np.nan) / last.get("volatility_bbh", 1) * 100 if last.get("volatility_bbh", 1) else np.nan,
                "ATR": last.get("volatility_atr", np.nan),
                "ADX": last.get("trend_adx", np.nan),
                "SMA_20": last.get("trend_sma_fast", np.nan),
                "EMA_20": last.get("trend_ema_fast", np.nan),
                "Sup": df["Low"].rolling(14).min().iloc[-1] if len(df) >= 14 else np.nan,
                "Res": df["High"].rolling(14).max().iloc[-1] if len(df) >= 14 else np.nan,
            }
            results.append(result)
        else:
            failed.append(f"{ticker} [{msg}]")
        progress_bar.progress((i + 1) / len(universe))
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values("Score", ascending=False)
        df = df[df["Score"] >= min_score].head(max_results)
    return df, failed

def download_as_excel(df):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False)
    buffer.seek(0)
    return buffer

# --- Streamlit Page Setup ---
st.set_page_config(
    page_title="Swing Trading Scanner Pro",
    page_icon="📈",
    layout="wide"
)

# --- Branding ---
st.markdown("""
    <h1 style='color:#145DA0;font-size:2.7rem; font-family:Montserrat;'>📈 Swing Trading Scanner Pro</h1>
    <div style="font-size:1.2rem; color:#333;">Your professional dashboard for swing trading opportunities — with technicals, charts, and Excel export.</div>
    <hr>
""", unsafe_allow_html=True)

# --- Sidebar Config ---
st.sidebar.title("Swing Trading Scanner Pro")
st.sidebar.header("Configuration")
uploaded_file = st.sidebar.file_uploader(
    "Upload an Excel file (.xlsx) with a column named 'Ticker' or 'Symbol'", type=["xlsx"]
)
TIME_FRAMES = ['1d', '1wk']
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
time_frame = st.sidebar.selectbox("Time Frame", TIME_FRAMES)
min_score = st.sidebar.slider("Minimum Quality Score", 0, 100, 18)
max_results = st.sidebar.slider("Max Results", 5, 50, 15)

st.sidebar.markdown("#### Current Universe")
for ticker in watchlist:
    st.sidebar.write(f"- {ticker}")

# --- SCAN BUTTON ---
st.markdown("### Scan Results")
if st.button("Run Scan"):
    scan_df, failed = scan_universe(watchlist, period='6mo', interval=time_frame, min_score=min_score, max_results=max_results)
    st.session_state["scan_results"] = scan_df
    st.session_state["failed"] = failed

scan_df = st.session_state.get("scan_results", pd.DataFrame())
failed = st.session_state.get("failed", [])

# --- Results Table ---
if not scan_df.empty:
    st.success("Scan completed!")
    st.dataframe(scan_df, use_container_width=True)
    st.download_button(
        label="Download Results as Excel",
        data=download_as_excel(scan_df),
        file_name="swing_scanner_results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("Run a scan to see results.")
    if failed:
        st.warning("Some tickers failed data download. See diagnostics below.")

# --- Diagnostics Panel: Single Ticker Test ---
with st.expander("Single Ticker Data Test (Diagnostics)"):
    st.write("Quickly test a single ticker and see raw Yahoo/yfinance output (for debugging failed downloads).")
    ticker_input = st.text_input("Test a ticker (e.g. MC.PA, AAPL, ORA.PA, SAN.PA):", value=(watchlist[0] if watchlist else "AAPL"))
    test_period = st.selectbox("Test period", ["1mo", "3mo", "6mo", "1y"], index=2)
    test_interval = st.selectbox("Test interval", ["1d", "1wk"], index=0)
    if st.button("Fetch Ticker Data"):
        raw_df, debug_msg = get_stock_data(ticker_input, test_period, test_interval)
        st.markdown(f"**Ticker:** {ticker_input.upper()}  \n**Period:** {test_period}  \n**Interval:** {test_interval}")
        if not raw_df.empty:
            st.write("Raw Yahoo data (tail):")
            st.dataframe(raw_df.tail(8))
            # Show chart
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=raw_df.index,
                open=raw_df['Open'],
                high=raw_df['High'],
                low=raw_df['Low'],
                close=raw_df['Close'],
                name="Price"
            ))
            if "momentum_rsi" in raw_df.columns:
                fig.add_trace(go.Scatter(
                    x=raw_df.index, y=raw_df["momentum_rsi"],
                    yaxis="y2", mode="lines", name="RSI"
                ))
            fig.update_layout(
                title=f"{ticker_input.upper()} Price & RSI",
                yaxis_title="Price",
                yaxis2=dict(title="RSI", overlaying='y', side='right'),
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
            st.write("With TA features (last 5 rows):")
            st.dataframe(raw_df.tail(5))
        else:
            st.error("No data returned! " + debug_msg)
        # --- DEBUG INFO PANEL: not nested! ---
        st.markdown("**Debug Info / Raw Log**")
        st.code(f"Debug message: {debug_msg}\n\nReturned DataFrame shape: {raw_df.shape}\nColumns: {list(raw_df.columns)}")
        st.write("Returned head (first 3 rows):")
        st.dataframe(raw_df.head(3))
        st.write("Returned tail (last 3 rows):")
        st.dataframe(raw_df.tail(3))

# --- Footer ---
st.markdown("""
    <hr>
    <div style="text-align:center; font-size:0.93rem; color:#888;">
        &copy; 2025 Swing Trading Scanner Pro &bull; Built with ❤️ using Python, Streamlit, yfinance, TA-Lib, Plotly.
    </div>
""", unsafe_allow_html=True)
