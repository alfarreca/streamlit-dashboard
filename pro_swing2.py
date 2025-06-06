import streamlit as st
import pandas as pd
import yfinance as yf
from ta import add_all_ta_features
import plotly.graph_objs as go
import io

# ---------- UTILITIES ----------
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

def get_stock_data(ticker, period='6mo', interval='1d', debug=False):
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        debug_info = {'raw': df.copy()}
        if df.empty or len(df) < 2:
            debug_info['error'] = "No data returned! This ticker/interval/period combo is not supported by Yahoo, or market is closed."
            return pd.DataFrame(), debug_info
        try:
            ta_df = add_all_ta_features(
                df, open="Open", high="High", low="Low", close="Close", volume="Volume", fillna=True
            )
            debug_info['ta'] = ta_df.copy()
            return ta_df, debug_info
        except Exception as e:
            debug_info['error'] = f"TA error: {str(e)}"
            return df, debug_info  # Return raw if TA fails
    except Exception as e:
        return pd.DataFrame(), {'error': f"Yahoo download error: {str(e)}"}

def score_momentum(data):
    # Use RSI as a "quality" score
    if data.empty or 'momentum_rsi' not in data.columns:
        return 0
    return round(data['momentum_rsi'].iloc[-1], 2)

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

# ---------- STREAMLIT APP CONFIG ----------
st.set_page_config(
    page_title="Swing Trading Scanner Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<h1 style="color:#185ADB; font-size:2.2rem">📈 Swing Trading Scanner Pro</h1>
Your professional dashboard for swing trading opportunities — with technicals, charts, and Excel export.
""", unsafe_allow_html=True)

# ---------- UNIVERSE & UPLOAD ----------
SCAN_UNIVERSE = ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'TSLA', 'NVDA', 'PYPL', 'ADBE', 'NFLX']
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

# Initialize session state
if 'watchlist' not in st.session_state:
    st.session_state['watchlist'] = excel_ticker_list or clean_tickers(SCAN_UNIVERSE)
else:
    if excel_ticker_list:
        st.session_state['watchlist'] = excel_ticker_list

watchlist = st.session_state['watchlist']

# ---------- SIDEBAR FILTERS ----------
st.sidebar.title("Swing Trading Scanner Pro")
st.sidebar.subheader("Configuration")

with st.sidebar.expander("Scan Settings", expanded=True):
    time_frame = st.selectbox("Time Frame", TIME_FRAMES)
    min_score = st.slider("Minimum Quality Score", 0, 100, 18)
    max_results = st.slider("Max Results", 5, 50, 15)

st.sidebar.markdown("#### Current Universe")
for ticker in watchlist:
    st.sidebar.write(f"- {ticker}")

# ---------- SCAN BUTTON ----------
if st.button("Run Scan"):
    results = []
    failed = []
    progress = st.progress(0)
    for i, ticker in enumerate(watchlist):
        data, debug_info = get_stock_data(ticker, period='6mo', interval=time_frame)
        score = score_momentum(data)
        if not data.empty and score >= min_score:
            results.append({
                "Ticker": ticker,
                "Score": score,
                "RSI": data['momentum_rsi'].iloc[-1] if 'momentum_rsi' in data.columns else None
            })
        elif data.empty:
            failed.append(ticker)
        progress.progress((i + 1) / len(watchlist))
    scan_df = pd.DataFrame(results)
    scan_df = scan_df.sort_values("Score", ascending=False).head(max_results) if not scan_df.empty else scan_df
    st.session_state['scan_results'] = scan_df
    st.session_state['failed'] = failed

scan_df = st.session_state.get('scan_results', pd.DataFrame())
failed = st.session_state.get('failed', [])

if not scan_df.empty:
    st.subheader("Scan Results")
    st.dataframe(scan_df, use_container_width=True)
    st.download_button("Download Results as Excel", to_excel(scan_df), "scan_results.xlsx")
    if failed:
        st.warning(f"Failed to fetch data for {len(failed)} tickers.")
else:
    st.info("Run a scan to see results.")
    if failed:
        st.warning(f"Failed to fetch data for {len(failed)} tickers.")

# ---------- SINGLE TICKER DIAGNOSTIC ----------
with st.expander("Single Ticker Data Test (Diagnostics)"):
    col1, col2, col3 = st.columns(3)
    with col1:
        test_ticker = st.text_input("Test a ticker (e.g. MC.PA, AAPL, ORA.PA, SAN.PA):", value=watchlist[0] if watchlist else "")
    with col2:
        test_period = st.selectbox("Test period", ['6mo', '3mo', '1mo'], index=0)
    with col3:
        test_interval = st.selectbox("Test interval", TIME_FRAMES, index=0)

    if st.button("Fetch Ticker Data"):
        data, debug_info = get_stock_data(test_ticker, period=test_period, interval=test_interval, debug=True)
        st.markdown(f"**Ticker:** {test_ticker}  \n**Period:** {test_period}  \n**Interval:** {test_interval}")

        # ---------- DEBUG INFO / RAW LOG ----------
        st.markdown("#### Debug Info / Raw Log")
        if debug_info.get('error'):
            st.code(f"Debug message: {debug_info['error']}")
        if 'raw' in debug_info:
            raw = debug_info['raw']
            st.code(f"Returned DataFrame shape: {raw.shape}\nColumns: {list(raw.columns)}")
            if not raw.empty:
                st.markdown("Returned head (first 3 rows):")
                st.dataframe(raw.head(3))
                st.markdown("Returned tail (last 3 rows):")
                st.dataframe(raw.tail(3))

        # ---------- PRICE CHART ----------
        st.markdown("#### Price Chart")
        debug_df = debug_info.get('ta', debug_info.get('raw', pd.DataFrame()))
        price_col = None
        for candidate in ["Close", "close", debug_df.columns[0] if not debug_df.empty else None]:
            if candidate in debug_df.columns:
                price_col = candidate
                break
        df_plot = debug_df.copy()
        if not df_plot.empty:
            # Ensure index is datetime
            if not pd.api.types.is_datetime64_any_dtype(df_plot.index):
                try:
                    df_plot.index = pd.to_datetime(df_plot.index)
                except Exception:
                    st.info("Cannot plot: Data index is not a valid datetime.")
                    price_col = None

            if price_col and len(df_plot[price_col].dropna()) > 1:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_plot.index,
                    y=df_plot[price_col],
                    mode='lines+markers',
                    name='Price'
                ))
                # Add RSI if available
                if 'momentum_rsi' in df_plot.columns:
                    fig.add_trace(go.Scatter(
                        x=df_plot.index,
                        y=df_plot['momentum_rsi'],
                        mode='lines',
                        name='RSI',
                        yaxis='y2'
                    ))
                    fig.update_layout(
                        yaxis2=dict(
                            title="RSI",
                            overlaying="y",
                            side="right",
                            showgrid=False
                        )
                    )
                fig.update_layout(
                    title=f"{test_ticker.upper()} Price & RSI",
                    xaxis_title="Date",
                    yaxis_title="Price"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Not enough valid price data to plot.")
        else:
            st.info("No data to plot.")

        # ---------- TA TABLE ----------
        if not debug_df.empty:
            st.markdown("With TA features (last 5 rows):")
            st.dataframe(debug_df.tail(5))

