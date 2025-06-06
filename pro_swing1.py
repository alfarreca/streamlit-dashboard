import streamlit as st
import pandas as pd
import yfinance as yf
from ta import add_all_ta_features
import plotly.graph_objs as go
from io import BytesIO

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
    data = yf.download(ticker, period=period, interval=interval)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(-1)
    if data.empty or len(data) < 2:
        return pd.DataFrame()
    min_rows = 15
    if len(data) < min_rows:
        return pd.DataFrame()
    try:
        data = add_all_ta_features(
            data, open="Open", high="High", low="Low", close="Close", volume="Volume"
        )
        # Custom: add SMA20, SMA50, ATR, ADX
        data['sma20'] = data['Close'].rolling(20).mean()
        data['sma50'] = data['Close'].rolling(50).mean()
        # Support/Resistance: min/max of last N closes
        data['support'] = data['Close'].rolling(10).min()
        data['resistance'] = data['Close'].rolling(10).max()
    except Exception as e:
        print(f"TA error for {ticker}: {e}")
        return pd.DataFrame()
    return data

def calculate_opportunity_score(data):
    if data.empty:
        return 0
    rsi = data['momentum_rsi'].iloc[-1] if 'momentum_rsi' in data else float('nan')
    macd = data['trend_macd_diff'].iloc[-1] if 'trend_macd_diff' in data else float('nan')
    bbp = data['volatility_bbp'].iloc[-1] if 'volatility_bbp' in data else float('nan')
    score = 0
    if not pd.isna(rsi):
        score += (100 - abs(rsi - 50)) * 0.5
    if not pd.isna(macd):
        score += (macd * 100) * 0.25
    if not pd.isna(bbp):
        score += (100 - abs(bbp - 0.5) * 200) * 0.25
    return round(score, 1)

def scan_universe(universe, period='6mo', interval='1d'):
    results = []
    failed = []
    for ticker in universe:
        data = get_stock_data(ticker, period, interval)
        if not data.empty:
            score = calculate_opportunity_score(data)
            results.append({
                'Ticker': ticker,
                'Score': score,
                'Price': data['Close'].iloc[-1],
                'Change %': (data['Close'].iloc[-1] / data['Close'].iloc[-2] - 1) * 100,
                'Volume': data['Volume'].iloc[-1],
                'RSI': data['momentum_rsi'].iloc[-1],
                'MACD': data['trend_macd_diff'].iloc[-1],
                'ATR': data['volatility_atr'].iloc[-1],
                'ADX': data['trend_adx'].iloc[-1],
                'SMA20': data['sma20'].iloc[-1],
                'SMA50': data['sma50'].iloc[-1],
                'Support': data['support'].iloc[-1],
                'Resistance': data['resistance'].iloc[-1],
            })
        else:
            failed.append(ticker)
    if not results:
        return pd.DataFrame(), failed
    return pd.DataFrame(results), failed

def style_dataframe(df):
    # Highlight top/bottom
    def color_score(val):
        if val >= df['Score'].max(): return "background-color: #c7f4d7"
        if val <= df['Score'].min(): return "background-color: #ffc9c9"
        return ""
    return df.style.applymap(color_score, subset=['Score'])

def download_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

def plot_ticker_chart(data, ticker):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=data.index, open=data['Open'], high=data['High'],
        low=data['Low'], close=data['Close'], name='Price'))
    fig.add_trace(go.Scatter(
        x=data.index, y=data['sma20'], line=dict(color='orange', width=1), name="SMA20"))
    fig.add_trace(go.Scatter(
        x=data.index, y=data['sma50'], line=dict(color='blue', width=1), name="SMA50"))
    fig.add_trace(go.Scatter(
        x=data.index, y=data['support'], line=dict(color='green', width=1, dash='dot'), name="Support"))
    fig.add_trace(go.Scatter(
        x=data.index, y=data['resistance'], line=dict(color='red', width=1, dash='dot'), name="Resistance"))
    fig.update_layout(title=f"{ticker} Price Chart", xaxis_title="Date", yaxis_title="Price", height=420)
    return fig

# --- LAYOUT ---
st.set_page_config(
    page_title="Swing Trading Scanner Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(
    "<h1 style='color:#255fa8;'>📈 Swing Trading Scanner Pro</h1>"
    "<p style='color:#5c5c5c;'>Your professional dashboard for swing trading opportunities — with technicals, charts, and Excel export.</p>",
    unsafe_allow_html=True,
)
st.markdown("---")

# --- UNIVERSE & UPLOAD ---
SCAN_UNIVERSE = [
    'AAPL', 'MSFT', 'GOOG', 'AMZN', 'META', 'TSLA', 'NVDA', 'PYPL', 'ADBE', 'NFLX'
]
TIME_FRAMES = ['1d', '1wk']

with st.sidebar:
    st.title("Swing Trading Scanner Pro")
    st.subheader("Configuration")
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

    watchlist = excel_ticker_list or clean_tickers(SCAN_UNIVERSE)
    time_frame = st.selectbox("Time Frame", TIME_FRAMES)
    min_score = st.slider("Minimum Quality Score", 0, 100, 18)
    max_results = st.slider("Max Results", 5, 50, 15)

    st.markdown("#### Current Universe")
    for ticker in watchlist:
        st.write(f"- {ticker}")

# --- SCAN BUTTON ---
if st.button("Run Scan"):
    scan_df, failed = scan_universe(watchlist, period='6mo', interval=time_frame)
    scan_df = scan_df[scan_df['Score'] >= min_score].sort_values("Score", ascending=False).head(max_results)
    st.session_state['scan_results'] = scan_df
    st.session_state['failed'] = failed

# --- SUMMARY CARDS ---
if 'scan_results' in st.session_state and not st.session_state['scan_results'].empty:
    df = st.session_state['scan_results']
    col1, col2, col3 = st.columns(3)
    col1.metric("Top Winner", df.iloc[0]['Ticker'], round(df.iloc[0]['Score'],1))
    col2.metric("Top Loser", df.iloc[-1]['Ticker'], round(df.iloc[-1]['Score'],1))
    col3.metric("Most Volatile", df.iloc[df['ATR'].idxmax()]['Ticker'], round(df['ATR'].max(),2))
    st.markdown("### Scan Results")
    st.data_editor(
        df,
        column_order=df.columns,
        hide_index=True,
        use_container_width=True,
        key="main_table",
        num_rows="dynamic",
        column_config={
            "Score": st.column_config.NumberColumn(help="Opportunity score (higher=better)"),
            "RSI": st.column_config.NumberColumn(help="Relative Strength Index"),
            "MACD": st.column_config.NumberColumn(help="MACD value"),
            "ATR": st.column_config.NumberColumn(help="Average True Range (volatility)"),
            "ADX": st.column_config.NumberColumn(help="Trend strength (above 25=strong trend)"),
            "SMA20": st.column_config.NumberColumn(help="20-day Simple Moving Average"),
            "SMA50": st.column_config.NumberColumn(help="50-day Simple Moving Average"),
            "Support": st.column_config.NumberColumn(help="Support level (last 10 closes)"),
            "Resistance": st.column_config.NumberColumn(help="Resistance level (last 10 closes)"),
        }
    )
    st.download_button(
        label="Download Results as Excel",
        data=download_excel(df),
        file_name="scan_results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    # --- INTERACTIVE LIVE CHART ---
    tickers_for_chart = df['Ticker'].tolist()
    chart_ticker = st.selectbox("Show Chart For", tickers_for_chart, index=0)
    chart_data = get_stock_data(chart_ticker, period='6mo', interval=time_frame)
    if not chart_data.empty:
        st.plotly_chart(plot_ticker_chart(chart_data, chart_ticker), use_container_width=True)
        st.info(f"Showing price, SMA20, SMA50, support and resistance for {chart_ticker}.")

    if 'failed' in st.session_state and st.session_state['failed']:
        st.warning(f"Failed to fetch data for: {', '.join(st.session_state['failed'])}")

else:
    st.info("Run a scan to see results.")

# --- DIAGNOSTICS ---
with st.expander("Single Ticker Data Test (Diagnostics)", expanded=False):
    ticker = st.text_input("Test a ticker", value="", placeholder="e.g. MC.PA, AAPL, ORA.PA, SAN.PA")
    period = st.selectbox("Test period", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=2, key='test_period')
    interval = st.selectbox("Test interval", ["1d", "1wk"], index=0, key='test_interval')
    if st.button("Fetch Ticker Data", key='diagnostics_fetch'):
        if not ticker:
            st.warning("Please enter a ticker symbol.")
        else:
            st.write(f"**Ticker:** {ticker}  \n**Period:** {period}  \n**Interval:** {interval}")
            data = get_stock_data(ticker, period, interval)
            st.write("Raw Yahoo data:")
            st.write(data.tail(10))
            if data.empty:
                st.error("No data returned! This ticker/interval/period combo is not supported by Yahoo, or market is closed.")
            elif len(data) < 15:
                st.warning("Not enough data to compute indicators (need at least 15 rows).")
            else:
                st.write("With TA features (last 5 rows):")
                st.write(data.tail())
                st.plotly_chart(plot_ticker_chart(data, ticker), use_container_width=True)
