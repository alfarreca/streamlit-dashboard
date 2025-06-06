import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from ta import add_all_ta_features
import plotly.graph_objects as go

# ----- Helper Functions -----

@st.cache_data(show_spinner=False)
def fetch_and_flatten_ticker(ticker, period="6mo", interval="1d"):
    dbg = {}
    try:
        data = yf.download(ticker, period=period, interval=interval)
        dbg['raw_shape'] = data.shape
        dbg['raw_columns'] = list(data.columns)
        if data.empty:
            dbg['error'] = "No data returned."
            return pd.DataFrame(), dbg

        data = data.rename_axis('Date').reset_index()
        
        try:
            data = add_all_ta_features(
                data, open="Open", high="High", low="Low", close="Close", volume="Volume", fillna=True
            )
        except Exception as e:
            dbg['ta_error'] = str(e)

        data['Ticker'] = ticker
        dbg['df_shape_post_ta'] = data.shape
        dbg['columns_post_ta'] = list(data.columns)

        return data, dbg
    except Exception as ex:
        dbg['exception'] = str(ex)
        return pd.DataFrame(), dbg

def scan_universe(watchlist, period="6mo", interval="1d"):
    scan_results = []
    debug_info = {}
    for ticker in watchlist:
        df, dbg = fetch_and_flatten_ticker(ticker, period, interval)
        debug_info[ticker] = dbg
        if not df.empty:
            last_row = df.iloc[-1]
            score = float(last_row.get("momentum_rsi", 0))
            scan_results.append({
                "Ticker": ticker,
                "Score": score,
                "RSI": float(last_row.get("momentum_rsi", np.nan)),
                "MACD": float(last_row.get("trend_macd", np.nan)),
                "Volume": float(last_row.get("Volume", np.nan)),
            })
    results_df = pd.DataFrame(scan_results)
    return results_df, debug_info

# ----- Streamlit App -----

st.set_page_config("Swing Trading Scanner Pro", layout="wide")
st.title("📈 Swing Trading Scanner Pro")
st.markdown("""
Your professional dashboard for swing trading opportunities — with technicals, charts, Excel export, and diagnostics.
""")

# --- Sidebar: Upload & Controls ---
st.sidebar.header("Configuration")

uploaded = st.sidebar.file_uploader("Upload an Excel file (.xlsx) with a column named 'Ticker' or 'Symbol'", type=['xlsx'])
if uploaded:
    df_excel = pd.read_excel(uploaded)
    col = "Ticker" if "Ticker" in df_excel.columns else ("Symbol" if "Symbol" in df_excel.columns else None)
    if col:
        watchlist = df_excel[col].dropna().astype(str).unique().tolist()
        st.sidebar.success(f"Loaded {len(watchlist)} tickers from Excel: {col}")
    else:
        st.sidebar.error("Excel must have a 'Ticker' or 'Symbol' column.")
        watchlist = []
else:
    watchlist = ["AAPL", "MSFT", "GOOG"]

# --- Scan Settings ---
period = st.sidebar.selectbox("Time Frame", ["1d", "1wk"], index=0)
min_score = st.sidebar.slider("Minimum Quality Score", 0, 100, 18)
max_results = st.sidebar.slider("Max Results", 5, 50, 15)

# --- Universe Display ---
st.sidebar.markdown("#### Current Universe")
for ticker in watchlist:
    st.sidebar.write("-", ticker)

# --- Scan Button & Results ---
if st.button("Run Scan"):
    with st.spinner("Scanning..."):
        scan_df, debug_info = scan_universe(watchlist, period="6mo", interval=period)
    if scan_df.empty:
        st.warning("No results found: all tickers failed, or none passed the score filter.")
    else:
        scan_df = scan_df[scan_df["Score"] >= min_score].sort_values("Score", ascending=False).head(max_results)
        st.subheader("Scan Results")
        st.dataframe(scan_df)
        st.download_button("Download Results as CSV", scan_df.to_csv(index=False), "scan_results.csv")
        st.download_button("Download Results as Excel", scan_df.to_excel(index=False, engine="openpyxl"), "scan_results.xlsx")

# --- Diagnostics: Single Ticker ---
with st.expander("Single Ticker Data Test (Diagnostics)", expanded=False):
    col1, col2, col3 = st.columns([3,1,1])
    with col1:
        single_ticker = st.text_input("Test a ticker (e.g. MC.PA, AAPL, ORA.PA, SAN.PA):", value=watchlist[0] if watchlist else "AAPL")
    with col2:
        single_period = st.selectbox("Test period", ['6mo', '1y', '3mo'], index=0)
    with col3:
        single_interval = st.selectbox("Test interval", ['1d', '1wk'], index=0)

    if st.button("Fetch Ticker Data"):
        df, dbg = fetch_and_flatten_ticker(single_ticker, period=single_period, interval=single_interval)
        if not df.empty:
            st.write(f"Returned DataFrame shape: {df.shape}")
            st.dataframe(df.head(3))

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df["Date"], y=df["Close"], mode='lines', name="Close"))
            if "momentum_rsi" in df.columns:
                fig.add_trace(go.Scatter(x=df["Date"], y=df["momentum_rsi"], mode='lines', name="RSI", yaxis="y2"))
                fig.update_layout(yaxis2=dict(overlaying='y', side='right', title="RSI"))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("No data returned! See Debug Info below.")

        st.markdown("#### Debug Info")
        st.write(dbg)
