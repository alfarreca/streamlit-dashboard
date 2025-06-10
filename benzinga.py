import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- App Title & Description ---
st.set_page_config(layout="wide")
st.title("🚀 Market Clubhouse Pro: Trading Levels with Options Flow")
st.markdown("""
Calculate dynamic **Support/Resistance** levels using Price, Volume, and **real options data** from Yahoo Finance.
""")

# --- Sidebar Inputs ---
st.sidebar.header("Settings")
ticker = st.sidebar.text_input("Stock/ETF Ticker", "SPY").upper()
lookback_days = st.sidebar.slider("Lookback Period (Days)", 5, 30, 10)
k1 = st.sidebar.slider("Volume Weight (k1)", 0.1, 1.0, 0.3)
k2 = st.sidebar.slider("Options Flow Weight (k2)", 0.1, 1.0, 0.5)  # Increased weight for options
k3 = st.sidebar.slider("Volatility Weight (k3)", 0.1, 1.0, 0.5)

# --- Fetch Stock Data ---
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_stock_data(ticker, lookback):
    end_date = datetime.today()
    start_date = end_date - timedelta(days=lookback)
    data = yf.download(ticker, start=start_date, end=end_date)
    return data

# --- Fetch Options Data ---
@st.cache_data(ttl=3600)
def get_options_flow(ticker):
    try:
        stock = yf.Ticker(ticker)
        expirations = stock.options
        
        if not expirations:
            return 1.0, None, None  # Neutral ratio if no options
        
        # Get nearest expiry options chain
        nearest_expiry = expirations[0]
        options_chain = stock.option_chain(nearest_expiry)
        calls = options_chain.calls
        puts = options_chain.puts
        
        # Calculate Call/Put Ratios
        total_calls_vol = calls["volume"].sum()
        total_puts_vol = puts["volume"].sum()
        total_calls_oi = calls["openInterest"].sum()
        total_puts_oi = puts["openInterest"].sum()
        
        # Avoid division by zero
        vol_ratio = (total_calls_vol / total_puts_vol) if total_puts_vol > 0 else 1.0
        oi_ratio = (total_calls_oi / total_puts_oi) if total_puts_oi > 0 else 1.0
        
        # Weighted average of volume and open interest ratios
        call_put_ratio = (vol_ratio * 0.7) + (oi_ratio * 0.3)
        return call_put_ratio, calls, puts
    
    except Exception as e:
        st.sidebar.warning(f"Options data error: {str(e)}")
        return 1.0, None, None  # Fallback to neutral

# --- Main Calculation ---
try:
    df = get_stock_data(ticker, lookback_days)
    if df.empty:
        st.error("No stock data found. Check ticker or try again.")
        st.stop()
    
    # Get latest metrics
    latest_close = df["Close"].iloc[-1]
    avg_volume = df["Volume"].mean() / 1e6  # in millions
    atr = (df["High"] - df["Low"]).mean()  # simplified ATR
    
    # Get options data
    call_put_ratio, calls, puts = get_options_flow(ticker)
    
    # --- Proprietary Formula ---
    def calculate_levels(price, volume, options_ratio, atr, bullish=True):
        if bullish:
            return price + (k1 * volume) + (k2 * options_ratio) + (k3 * atr)
        else:
            return price - (k1 * volume) - (k2 * options_ratio) - (k3 * atr)
    
    # Bullish Targets
    r1 = calculate_levels(latest_close, avg_volume, call_put_ratio, atr, bullish=True)
    r2 = r1 + (0.5 * atr)
    r3 = r2 + (0.5 * atr)
    
    # Bearish Targets
    s1 = calculate_levels(latest_close, avg_volume, call_put_ratio, atr, bullish=False)
    s2 = s1 - (0.5 * atr)
    s3 = s2 - (0.5 * atr)
    
    # --- Display Results ---
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        st.metric("Current Price", f"${latest_close:.2f}")
        st.metric("Avg Volume (M)", f"{avg_volume:.2f}")
        st.metric("ATR (Volatility)", f"{atr:.2f}")
    
    with col2:
        st.markdown("### 🟢 Bullish Targets")
        st.metric("Resistance 1", f"${r1:.2f}")
        st.metric("Resistance 2", f"${r2:.2f}")
        st.metric("Max Target", f"${r3:.2f}")
    
    with col3:
        st.markdown("### 🔴 Bearish Targets")
        st.metric("Support 1", f"${s1:.2f}")
        st.metric("Support 2", f"${s2:.2f}")
        st.metric("Lowest Target", f"${s3:.2f}")
    
    # --- Options Data Display ---
    st.subheader("📊 Options Flow Analysis")
    if calls is not None and puts is not None:
        col4, col5 = st.columns(2)
        with col4:
            st.markdown("**Top Calls (Volume)**")
            st.dataframe(calls.nlargest(5, "volume")[["strike", "lastPrice", "volume", "openInterest"]])
        with col5:
            st.markdown("**Top Puts (Volume)**")
            st.dataframe(puts.nlargest(5, "volume")[["strike", "lastPrice", "volume", "openInterest"]])
        
        st.metric("Call/Put Ratio (Weighted)", f"{call_put_ratio:.2f}")
    else:
        st.warning("Limited options data available. Using neutral ratio (1.0).")
    
    # --- Price Chart ---
    st.subheader(f"📈 {ticker} Price (Last {lookback_days} Days)")
    st.line_chart(df["Close"])
    
    # --- Formula Explanation ---
    st.subheader("🔍 Formula Logic")
    st.markdown(f"""
    ```
    Bullish Target = Price + (k1 × Volume) + (k2 × Call/Put Ratio) + (k3 × ATR)
    Bearish Target = Price - (k1 × Volume) - (k2 × Call/Put Ratio) - (k3 × ATR)
    ```
    - **k1 (Volume Weight)**: {k1}  
    - **k2 (Options Flow Weight)**: {k2}  
    - **k3 (Volatility Weight)**: {k3}  
    """)
    
    st.info("💡 Note: Call/Put Ratio combines volume and open interest (70/30 weight).")

except Exception as e:
    st.error(f"Error: {str(e)}")