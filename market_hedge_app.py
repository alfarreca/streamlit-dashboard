import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

# Try importing scipy for Black-Scholes
try:
    from scipy.stats import norm
    has_scipy = True
except ImportError:
    has_scipy = False

st.set_page_config(page_title="Enhanced Market Hedge Simulator", layout="wide")

def black_scholes_put(S, K, T, r, sigma):
    from math import log, sqrt, exp
    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0 or np.isnan(S) or np.isnan(K) or np.isnan(T) or np.isnan(r) or np.isnan(sigma):
        return 0
    d1 = (log(S / K) + (r + sigma ** 2 / 2.) * T) / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)
    put_price = K * exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    return max(put_price, 0)

st.title("📉 Enhanced Market Crash Hedge Simulator")
st.markdown("""
Explore realistic hedging strategies and analyze their historical performance against market downturns with advanced metrics and interactive visualizations.
""")

st.sidebar.header("Strategy Parameters")

strategy = st.sidebar.selectbox(
    "Select Hedging Strategy",
    [
        "Put Options", "Inverse ETFs", "Gold Allocation",
        "Dynamic Allocation", "Volatility Index (VIX)"
    ]
)

ticker = st.sidebar.text_input("Primary Asset (e.g., SPY)", "SPY")
end_date = datetime.today()
start_date = st.sidebar.date_input(
    "Start Date", value=end_date - timedelta(days=365*5),
    max_value=end_date - timedelta(days=1)
)

# --- UPLOAD SECTION ---
st.sidebar.markdown("### Or upload your own data")
uploaded_file = st.sidebar.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])

def load_uploaded_data(uploaded_file):
    if uploaded_file is None:
        return None
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    df.columns = [str(c).strip() for c in df.columns]
    # Handle possible date column
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date")
    else:
        df.index = pd.to_datetime(df.index)
    return df

@st.cache_data
def load_data(ticker, start_date, end_date):
    return yf.download(ticker, start=start_date, end=end_date, auto_adjust=True)

# --- DATA INGESTION ---
if uploaded_file:
    main_data = load_uploaded_data(uploaded_file)
    st.success("✅ Using uploaded data!")
else:
    main_data = load_data(ticker, start_date, end_date)
    st.info("ℹ️ Using Yahoo Finance data.")

if main_data is None or main_data.empty:
    st.error("No data available for the selected input or date range.")
    st.stop()

# --- FLATTEN MULTIINDEX COLUMNS ---
if isinstance(main_data.columns, pd.MultiIndex):
    main_data.columns = ['_'.join([str(c) for c in col if c]) for col in main_data.columns.values]

# --- FLEXIBLE PRICE COLUMN DETECTION ---
close_candidates = [c for c in main_data.columns if "close" in str(c).lower()]
if not close_candidates:
    st.error(
        "The data does not contain a usable price column (e.g., 'Close', 'Adj Close', 'Close_SPY'). "
        "Please check the data source or upload a file with a price column."
    )
    st.write("Raw data columns:", [str(c) for c in main_data.columns])
    st.write(main_data.head())
    st.stop()
elif len(close_candidates) == 1:
    close_col = close_candidates[0]
    st.success(f"Using '{close_col}' as the price column.")
else:
    close_col = st.sidebar.selectbox("Select price column", [str(c) for c in close_candidates])
    st.success(f"Using '{close_col}' as the price column.")

main_data['Close'] = main_data[close_col]
main_data['Returns'] = main_data['Close'].pct_change()
main_data['Cumulative'] = (1 + main_data['Returns']).cumprod()

# --- PUT OPTIONS STRATEGY ---
if strategy == "Put Options":
    if not has_scipy:
        st.error("scipy is required for Black-Scholes option pricing. Please add 'scipy' to your requirements.txt.")
        st.stop()
    strike_offset = st.sidebar.slider("Strike Price (% below current)", 5, 30, 10)
    expiration_days = st.sidebar.slider("Days to Expiration", 30, 180, 30)
    annual_volatility = main_data['Returns'].std() * np.sqrt(252)
    risk_free_rate = 0.03

    def safe_black_scholes(
        row,
        strike_offset,
        expiration_days,
        risk_free_rate,
        annual_volatility
    ):
        S = row['Close']
        try:
            S = float(S)
        except Exception:
            S = np.nan
        if pd.isnull(S) or S <= 0:
            return np.nan
        K = S * (1 - strike_offset / 100)
        T = expiration_days / 365
        r = risk_free_rate
        sigma = annual_volatility
        if K <= 0 or T <= 0 or sigma <= 0 or np.isnan(K) or np.isnan(T) or np.isnan(sigma):
            return np.nan
        return black_scholes_put(S, K, T, r, sigma)

    main_data['Put_Price'] = main_data.apply(
        safe_black_scholes,
        axis=1,
        strike_offset=strike_offset,
        expiration_days=expiration_days,
        risk_free_rate=risk_free_rate,
        annual_volatility=annual_volatility
    )

    main_data['Put_Cost'] = np.where(
        (main_data['Close'] > 0) & (~main_data['Put_Price'].isna()),
        main_data['Put_Price'] / main_data['Close'],
        np.nan
    )
    main_data['Put_Cost'].fillna(method='ffill', inplace=True)
    main_data['Put_Cost'].fillna(0, inplace=True)

    main_data['Hedge_Payoff'] = np.where(
        main_data['Close'].shift(-expiration_days) < main_data['Close'] * (1 - strike_offset/100),
        (main_data['Close'] * (1 - strike_offset/100) - main_data['Close'].shift(-expiration_days)) / main_data['Close'],
        0
    )

    main_data['Strategy_Returns'] = main_data['Returns'] - main_data['Put_Cost']/expiration_days*30 + main_data['Hedge_Payoff']

# --- GOLD ALLOCATION STRATEGY ---
if strategy == "Gold Allocation":
    gold_weight = st.sidebar.slider("Gold allocation (%)", 0, 50, 20, step=5)
    gold_weight = gold_weight / 100
    asset_weight = 1 - gold_weight

    # Download gold data (GLD ETF, same date range)
    gold_data = yf.download("GLD", start=start_date, end=end_date, auto_adjust=True)
    if gold_data.empty:
        st.error("Could not download gold (GLD) data for the selected range.")
    else:
        if isinstance(gold_data.columns, pd.MultiIndex):
            gold_data.columns = ['_'.join([str(c) for c in col if c]) for col in gold_data.columns.values]
        gold_close_candidates = [c for c in gold_data.columns if "close" in str(c).lower()]
        if not gold_close_candidates:
            st.error("Could not find usable close column in gold data.")
        else:
            gold_col = gold_close_candidates[0]
            combined = pd.DataFrame({
                "Asset": main_data['Close'],
                "Gold": gold_data[gold_col]
            }).dropna()
            combined["Asset_Ret"] = combined["Asset"].pct_change()
            combined["Gold_Ret"] = combined["Gold"].pct_change()
            combined["Strategy_Returns"] = asset_weight * combined["Asset_Ret"] + gold_weight * combined["Gold_Ret"]
            combined["Cumulative"] = (1 + combined["Asset_Ret"]).cumprod()
            combined["Strategy_Cumulative"] = (1 + combined["Strategy_Returns"]).cumprod()
            main_data = combined

# --- INVERSE ETF STRATEGY ---
if strategy == "Inverse ETFs":
    st.sidebar.markdown("Examples: `SH` (SPY), `SQQQ` (QQQ), `DOG` (DIA), `PSQ` (QQQ, non-levered)")
    inverse_ticker = st.sidebar.text_input("Inverse ETF Ticker", value="SH")
    inverse_weight = st.sidebar.slider("Inverse ETF allocation (%)", 0, 50, 20, step=5)
    inverse_weight = inverse_weight / 100
    asset_weight = 1 - inverse_weight

    # Download inverse ETF data (same date range)
    inv_data = yf.download(inverse_ticker, start=start_date, end=end_date, auto_adjust=True)
    if inv_data.empty:
        st.error(f"Could not download {inverse_ticker} data for the selected range.")
    else:
        if isinstance(inv_data.columns, pd.MultiIndex):
            inv_data.columns = ['_'.join([str(c) for c in col if c]) for col in inv_data.columns.values]
        inv_close_candidates = [c for c in inv_data.columns if "close" in str(c).lower()]
        if not inv_close_candidates:
            st.error(f"Could not find usable close column in {inverse_ticker} data.")
        else:
            inv_col = inv_close_candidates[0]
            combined = pd.DataFrame({
                "Asset": main_data['Close'],
                "Inverse": inv_data[inv_col]
            }).dropna()
            combined["Asset_Ret"] = combined["Asset"].pct_change()
            combined["Inverse_Ret"] = combined["Inverse"].pct_change()
            combined["Strategy_Returns"] = asset_weight * combined["Asset_Ret"] + inverse_weight * combined["Inverse_Ret"]
            combined["Cumulative"] = (1 + combined["Asset_Ret"]).cumprod()
            combined["Strategy_Cumulative"] = (1 + combined["Strategy_Returns"]).cumprod()
            main_data = combined

# --- DYNAMIC ALLOCATION STRATEGY ---
if strategy == "Dynamic Allocation":
    st.sidebar.markdown("Hedge shifts when price is below moving average (SMA).")
    safe_asset = st.sidebar.selectbox("Hedge Asset", ["GLD (Gold)", "SH (Inverse SPY)", "Cash"], index=0)
    sma_length = st.sidebar.slider("SMA Window (days)", 10, 120, 50)
    hedge_weight = st.sidebar.slider("Hedge allocation (%)", 10, 100, 50, step=5) / 100

    main_data['SMA'] = main_data['Close'].rolling(window=sma_length).mean()
    main_data['Below_SMA'] = main_data['Close'] < main_data['SMA']

    # Load hedge asset or use 0 returns for cash
    if safe_asset.startswith("GLD"):
        hedge_ticker = "GLD"
    elif safe_asset.startswith("SH"):
        hedge_ticker = "SH"
    else:
        hedge_ticker = None

    if hedge_ticker:
        hedge_data = yf.download(hedge_ticker, start=start_date, end=end_date, auto_adjust=True)
        if hedge_data.empty:
            st.error(f"Could not download {hedge_ticker} data for the selected range.")
            hedge_returns = pd.Series(0, index=main_data.index)
        else:
            if isinstance(hedge_data.columns, pd.MultiIndex):
                hedge_data.columns = ['_'.join([str(c) for c in col if c]) for col in hedge_data.columns.values]
            hedge_close_candidates = [c for c in hedge_data.columns if "close" in str(c).lower()]
            hedge_col = hedge_close_candidates[0]
            hedge_returns = hedge_data[hedge_col].pct_change().reindex(main_data.index).fillna(0)
    else:
        hedge_returns = pd.Series(0, index=main_data.index)

    # Construct strategy returns
    main_returns = main_data['Returns'].fillna(0)
    weights = np.where(main_data['Below_SMA'], 1 - hedge_weight, 1)
    hedge_alloc = np.where(main_data['Below_SMA'], hedge_weight, 0)
    main_data['Strategy_Returns'] = weights * main_returns + hedge_alloc * hedge_returns

# --- VOLATILITY INDEX (VIX) STRATEGY ---
if strategy == "Volatility Index (VIX)":
    st.sidebar.markdown("Shift portfolio when VIX (volatility index) spikes.")
    hedge_asset = st.sidebar.selectbox("Hedge Asset", ["Cash", "GLD (Gold)", "SH (Inverse SPY)"], index=0)
    vix_trigger = st.sidebar.slider("VIX Trigger Level", 10, 40, 25)
    hedge_weight = st.sidebar.slider("Hedge allocation (%)", 10, 100, 50, step=5) / 100

    # Download VIX data for same date range
    vix_data = yf.download("^VIX", start=start_date, end=end_date, auto_adjust=True)
    vix_data = vix_data.reindex(main_data.index).fillna(method="ffill")
    main_data["VIX"] = vix_data["Close"]

    # Download hedge asset or use cash
    if hedge_asset.startswith("GLD"):
        hedge_ticker = "GLD"
    elif hedge_asset.startswith("SH"):
        hedge_ticker = "SH"
    else:
        hedge_ticker = None

    if hedge_ticker:
        hedge_data = yf.download(hedge_ticker, start=start_date, end=end_date, auto_adjust=True)
        if hedge_data.empty:
            st.error(f"Could not download {hedge_ticker} data for the selected range.")
            hedge_returns = pd.Series(0, index=main_data.index)
        else:
            if isinstance(hedge_data.columns, pd.MultiIndex):
                hedge_data.columns = ['_'.join([str(c) for c in col if c]) for col in hedge_data.columns.values]
            hedge_close_candidates = [c for c in hedge_data.columns if "close" in str(c).lower()]
            hedge_col = hedge_close_candidates[0]
            hedge_returns = hedge_data[hedge_col].pct_change().reindex(main_data.index).fillna(0)
    else:
        hedge_returns = pd.Series(0, index=main_data.index)

    # Allocate to hedge if VIX above trigger
    main_returns = main_data['Returns'].fillna(0)
    hedge_signal = main_data['VIX'] > vix_trigger
    weights = np.where(hedge_signal, 1 - hedge_weight, 1)
    hedge_alloc = np.where(hedge_signal, hedge_weight, 0)
    main_data['Strategy_Returns'] = weights * main_returns + hedge_alloc * hedge_returns

# --- METRICS, CHARTS, AND DOWNLOAD: Only run if Strategy_Returns exists! ---
if 'Strategy_Returns' in main_data.columns:
    main_data['Strategy_Cumulative'] = (1 + main_data['Strategy_Returns'].fillna(0)).cumprod()

    if main_data['Strategy_Returns'].std() > 0:
        sharpe_ratio = np.sqrt(252) * main_data['Strategy_Returns'].mean() / main_data['Strategy_Returns'].std()
    else:
        sharpe_ratio = np.nan

    sortino_denom = main_data[main_data['Strategy_Returns'] < 0]['Strategy_Returns'].std()
    if pd.notnull(sortino_denom) and sortino_denom > 0:
        sortino_ratio = np.sqrt(252) * main_data['Strategy_Returns'].mean() / sortino_denom
    else:
        sortino_ratio = np.nan

    fig = px.line(
        main_data,
        y=['Cumulative', 'Strategy_Cumulative'],
        title=f"{ticker} vs. Strategy Performance",
        labels={'value': 'Growth of $1', 'variable': 'Strategy'}
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📊 Performance Metrics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Buy & Hold Return", f"{main_data['Cumulative'].iloc[-1]-1:.1%}")
    col2.metric("Strategy Return", f"{main_data['Strategy_Cumulative'].iloc[-1]-1:.1%}")
    col3.metric("Sharpe Ratio", f"{sharpe_ratio:.2f}" if not np.isnan(sharpe_ratio) else "N/A")
    col4.metric("Sortino Ratio", f"{sortino_ratio:.2f}" if not np.isnan(sortino_ratio) else "N/A")

    main_data['Drawdown'] = main_data['Cumulative'] / main_data['Cumulative'].cummax() - 1
    main_data['Strategy_Drawdown'] = main_data['Strategy_Cumulative'] / main_data['Strategy_Cumulative'].cummax() - 1

    fig_dd = px.line(main_data, y=['Drawdown', 'Strategy_Drawdown'], title="Drawdown Comparison")
    st.plotly_chart(fig_dd, use_container_width=True)

    csv = main_data.to_csv().encode('utf-8')
    st.download_button("📥 Download Results CSV", csv, "results.csv")
else:
    st.info("This demo version implements Put Options, Gold Allocation, Inverse ETF, Dynamic Allocation, and Volatility Index strategies in detail. Contact support for full multi-strategy version.")
    st.write(main_data.head())

# --- STRATEGY FOOTER ---
st.info("""
**🔍 Strategy Insights:**

- **Put Options:** Protect your portfolio from sharp declines by using options as insurance.
- **Gold Allocation:** Add gold to reduce drawdowns and diversify risk. Adjust allocation to balance risk and return.
- **Inverse ETF:** Allocate to inverse ETFs to profit from market downturns and hedge long exposure.
- **Dynamic Allocation:** Automatically shifts to hedges when
