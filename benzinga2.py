import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from io import BytesIO

# --- App Config ---
st.set_page_config(layout="wide")
st.title("🚀 Market Clubhouse Pro: Trading Levels with Options Flow")

st.markdown("""
Calculate dynamic **Support/Resistance** levels using Price, Volume, and **real options data** from Yahoo Finance.
""")

# --- Sidebar Inputs ---
st.sidebar.header("Settings")
uploaded_file = st.sidebar.file_uploader("Upload XLSX file with tickers (optional)", type=["xlsx"])
uploaded_df = None
full_metrics_df = None

ticker = st.sidebar.text_input("Stock/ETF Ticker", "SPY").upper()
lookback_days = st.sidebar.slider("Lookback Period (Trading Days)", 5, 30, 10)
k1 = st.sidebar.slider("Volume Weight (k1)", 0.1, 1.0, 0.3)
k2 = st.sidebar.slider("Options Flow Weight (k2)", 0.1, 1.0, 0.5)
k3 = st.sidebar.slider("Volatility Weight (k3)", 0.1, 1.0, 0.5)

# --- Helper Functions ---

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

@st.cache_data(ttl=3600)
def get_stock_data(ticker, lookback):
    end_date = datetime.today()
    start_date = end_date - timedelta(days=lookback * 3)
    df = yf.download(ticker, start=start_date, end=end_date, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[df['Close'].notna()]
    df = df.tail(lookback)
    return df

def calculate_atr(df, period=14):
    required_cols = {'High', 'Low', 'Close'}
    if df.empty or not required_cols.issubset(df.columns):
        return np.nan
    try:
        from ta.volatility import AverageTrueRange
        atr = AverageTrueRange(df['High'], df['Low'], df['Close'], window=min(period, len(df))).average_true_range()
        return float(atr.iloc[-1])
    except ImportError:
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=min(period, len(df)), min_periods=1).mean()
        return float(atr.iloc[-1])
    except Exception:
        return np.nan

@st.cache_data(ttl=3600)
def get_options_flow(ticker):
    try:
        stock = yf.Ticker(ticker)
        expirations = stock.options
        if not expirations:
            return 1.0, 0  # Neutral ratio, no options activity
        nearest_expiry = expirations[0]
        options_chain = stock.option_chain(nearest_expiry)
        calls = options_chain.calls
        puts = options_chain.puts
        total_calls_vol = calls["volume"].sum()
        total_puts_vol = puts["volume"].sum()
        total_calls_oi = calls["openInterest"].sum()
        total_puts_oi = puts["openInterest"].sum()
        vol_ratio = (total_calls_vol / total_puts_vol) if total_puts_vol > 0 else 1.0
        oi_ratio = (total_calls_oi / total_puts_oi) if total_puts_oi > 0 else 1.0
        call_put_ratio = (vol_ratio * 0.7) + (oi_ratio * 0.3)
        total_opt_activity = total_calls_vol + total_puts_vol
        return float(call_put_ratio), int(total_opt_activity)
    except Exception:
        return 1.0, 0

def calculate_levels(price, normalized_vol, call_put_ratio, atr, volume_pct, atr_pct, k1, k2, k3):
    if price is None or np.isnan(price):
        return [np.nan]*6
    r1 = price * (1 + (k1 * volume_pct) + (k2 * call_put_ratio / 10) + (k3 * atr_pct))
    r2 = r1 + (0.5 * atr)
    r3 = r2 + (0.5 * atr)
    s1 = price * (1 - (k1 * volume_pct) - (k2 * call_put_ratio / 10) - (k3 * atr_pct))
    s2 = s1 - (0.5 * atr)
    s3 = s2 - (0.5 * atr)
    return [r1, r2, r3, s1, s2, s3]

# --- Uploaded XLSX Table Processing ---
if uploaded_file is not None:
    try:
        uploaded_df = pd.read_excel(uploaded_file)
        st.success("✅ XLSX file uploaded!")
        if "Symbol" not in uploaded_df.columns:
            st.error('Uploaded file must contain a "Symbol" column.')
            st.stop()
        uploaded_df["Symbol"] = uploaded_df["Symbol"].astype(str).str.upper().str.strip()
        tickers = uploaded_df["Symbol"].dropna().unique().tolist()[:30]
        st.info(f"Processing {len(tickers)} tickers. (Limit: 30)")
        metrics = []
        progress_bar = st.progress(0)
        for i, symbol in enumerate(tickers):
            try:
                df = get_stock_data(symbol, lookback_days)
                if df.empty or not {'High', 'Low', 'Close', 'Volume'}.issubset(df.columns):
                    raise ValueError("No data or missing columns.")
                latest_close = float(df['Close'].iloc[-1])
                avg_volume = float(df['Volume'].mean())
                normalized_vol = avg_volume / 1e6
                volume_pct = avg_volume / max(df['Volume'].max(), 1)
                atr = calculate_atr(df, lookback_days)
                atr_pct = atr / latest_close if latest_close else 0
                call_put_ratio, total_opt_activity = get_options_flow(symbol)
                r1, r2, r3, s1, s2, s3 = calculate_levels(
                    latest_close, normalized_vol, call_put_ratio, atr, volume_pct, atr_pct, k1, k2, k3
                )
                metrics.append({
                    "Symbol": symbol,
                    "Last Price": latest_close,
                    "Avg Volume (M)": normalized_vol,
                    "ATR": atr,
                    "ATR %": atr_pct*100,
                    "Vol% of Max": volume_pct*100,
                    "R1": r1, "R2": r2, "R3": r3,
                    "S1": s1, "S2": s2, "S3": s3,
                    "Call/Put Ratio": call_put_ratio,
                    "Total Options Volume": total_opt_activity
                })
            except Exception as e:
                metrics.append({
                    "Symbol": symbol,
                    "Last Price": np.nan,
                    "Avg Volume (M)": np.nan,
                    "ATR": np.nan,
                    "ATR %": np.nan,
                    "Vol% of Max": np.nan,
                    "R1": np.nan, "R2": np.nan, "R3": np.nan,
                    "S1": np.nan, "S2": np.nan, "S3": np.nan,
                    "Call/Put Ratio": np.nan,
                    "Total Options Volume": np.nan
                })
            progress_bar.progress((i+1)/len(tickers))
        full_metrics_df = pd.DataFrame(metrics)
        # Merge extra columns if any
        extra_cols = [c for c in uploaded_df.columns if c != "Symbol"]
        if extra_cols:
            full_metrics_df = pd.merge(uploaded_df, full_metrics_df, on="Symbol", how="left")
        st.subheader("📋 Full Tickers List with All Metrics")
        st.dataframe(full_metrics_df)
        xlsx_data = to_excel(full_metrics_df)
        st.download_button(
            label="Download Full Metrics Table as XLSX",
            data=xlsx_data,
            file_name="full_tickers_metrics.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="full_metrics_xlsx"
        )
        st.stop()
    except Exception as e:
        st.error(f"Error processing XLSX: {e}")
        st.stop()

# --- If NO uploaded file: continue original app logic below ---

# --- Validate Ticker ---
def validate_ticker(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        if info is None or 'regularMarketPrice' not in info or info['regularMarketPrice'] is None:
            return False
        return True
    except Exception:
        return False

if not ticker:
    st.error("Please enter a ticker symbol.")
    st.stop()

with st.spinner("Validating ticker..."):
    if not validate_ticker(ticker):
        st.error("Invalid or unavailable ticker symbol. Please enter a valid, listed stock/ETF ticker.")
        st.stop()

with st.spinner("Fetching price history..."):
    df = get_stock_data(ticker, lookback_days)
    df.columns = [str(col).title() for col in df.columns]
    st.write("Downloaded DataFrame shape:", df.shape)
    st.write("Columns:", df.columns)
    st.write("Preview:", df.head())

def to_excel_index(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=True)
    return output.getvalue()

if st.sidebar.button("Download XLSX file"):
    xlsx_data = to_excel_index(df)
    st.download_button(
        label="Download Data as XLSX",
        data=xlsx_data,
        file_name=f"{ticker}_history.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_yahoo_xlsx"
    )

# --- CSV download (Yahoo data only, for backwards compatibility) ---
if st.sidebar.button("Export as CSV"):
    csv = df.to_csv(index=True).encode('utf-8')
    st.download_button("Download Price Data CSV", csv, f"{ticker}_history.csv", "text/csv", key='csv_dl')

# --- Check for empty DataFrame or missing columns
required_cols = {'High', 'Low', 'Close', 'Volume'}
if df.empty or not required_cols.issubset(df.columns):
    st.error("No or insufficient stock data found for this period, or required columns are missing. "
             "Try a different ticker or timeframe.")
    st.stop()

if len(df) < lookback_days // 2:
    st.error("Insufficient stock data for this period. Try a different ticker or longer lookback.")
    st.stop()

# --- Metrics calculations (as before) ---
atr = calculate_atr(df, lookback_days)
latest_close = float(df['Close'].iloc[-1])
avg_volume = float(df['Volume'].mean())
normalized_vol = avg_volume / 1e6
volume_pct = avg_volume / max(df['Volume'].max(), 1)
call_put_ratio, total_opt_activity = get_options_flow(ticker)
atr_pct = atr / latest_close if latest_close else 0
r1, r2, r3, s1, s2, s3 = calculate_levels(
    latest_close, normalized_vol, call_put_ratio, atr, volume_pct, atr_pct, k1, k2, k3
)

col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    st.metric("Current Price", f"${latest_close:.2f}")
    st.metric("Avg Volume (M)", f"{normalized_vol:.2f}")
    st.metric("ATR (Volatility)", f"{atr:.2f}")
    st.metric("ATR (% of Price)", f"{atr_pct*100:.2f}%")
    st.metric("Volume as % of Max", f"{volume_pct*100:.1f}%")

with col2:
    st.markdown("### 🟢 Bullish Targets")
    st.metric("Resistance 1", f"${r1:.2f}")
    st.metric("Resistance 2", f"{r2:.2f}")
    st.metric("Max Target", f"{r3:.2f}")

with col3:
    st.markdown("### 🔴 Bearish Targets")
    st.metric("Support 1", f"${s1:.2f}")
    st.metric("Support 2", f"{s2:.2f}")
    st.metric("Lowest Target", f"{s3:.2f}")

# --- Options Data Display ---
st.subheader("📊 Options Flow Analysis")
try:
    stock = yf.Ticker(ticker)
    expirations = stock.options
    if expirations:
        nearest_expiry = expirations[0]
        options_chain = stock.option_chain(nearest_expiry)
        calls = options_chain.calls
        puts = options_chain.puts
        col4, col5 = st.columns(2)
        with col4:
            st.markdown("**Top Calls (Volume)**")
            st.dataframe(calls.nlargest(5, "volume")[["strike", "lastPrice", "volume", "openInterest"]])
        with col5:
            st.markdown("**Top Puts (Volume)**")
            st.dataframe(puts.nlargest(5, "volume")[["strike", "lastPrice", "volume", "openInterest"]])
        st.metric("Call/Put Ratio (Weighted)", f"{call_put_ratio:.2f}")
        st.metric("Total Options Volume (Activity)", f"{int(total_opt_activity):,}")
        if total_opt_activity > avg_volume:
            st.info("⚡ High options activity vs. historical stock volume – **watch for volatility spikes!**")
    else:
        st.warning("Limited options data available. Using neutral ratio (1.0).")
except Exception:
    st.warning("Options data unavailable.")

st.subheader(f"📈 {ticker} Price (Last {lookback_days} Trading Days)")
st.line_chart(df["Close"])

st.subheader("🔍 Formula Logic")
st.markdown(
    f"""
This app calculates custom support and resistance levels by blending:

- **Current Price**
- **Normalized Volume** (vs. peak in lookback)
- **Options Flow Ratio** (weighted calls vs. puts, using both volume and open interest)
- **ATR (Average True Range)**

**Bullish Level:**  
&nbsp;&nbsp;&nbsp;&nbsp;`price * (1 + k1*volume_pct + k2*options_ratio/10 + k3*atr_pct)`

**Bearish Level:**  
&nbsp;&nbsp;&nbsp;&nbsp;`price * (1 - k1*volume_pct - k2*options_ratio/10 - k3*atr_pct)`

- _k1, k2, k3_ are weights set in the sidebar.
- ATR is normalized as a % of price.
- Options ratio is a weighted average of call/put volume and open interest.
- All data is fetched live from Yahoo Finance.
    """
)
st.caption(
    "For education only – do not use for trading without your own research. "
    "Contact @alfarreca for feedback or suggestions!"
)
