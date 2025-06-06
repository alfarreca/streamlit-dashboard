import streamlit as st
import yfinance as yf
import pandas as pd
from ta import add_all_ta_features

st.set_page_config(page_title="Ticker Data Test", layout="centered")

st.title("Yahoo Finance Single-Ticker Test")

ticker = st.text_input("Enter ticker (e.g. MC.PA, ORA.PA, SAN.PA):", value="MC.PA")
period = st.selectbox("Period", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=2)
interval = st.selectbox("Interval", ["1d", "1wk"], index=0)

if st.button("Fetch Data"):
    st.write(f"**Ticker:** {ticker}  \n**Period:** {period}  \n**Interval:** {interval}")
    data = yf.download(ticker, period=period, interval=interval)
    # --- Fix: Flatten MultiIndex columns if present ---
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(-1)
    st.write("Raw Yahoo data:")
    st.write(data.tail(10))

    if not data.empty:
        try:
            ta_data = add_all_ta_features(
                data, open="Open", high="High", low="Low", close="Close", volume="Volume"
            )
            st.write("With TA features (last 5 rows):")
            st.write(ta_data.tail())
        except Exception as e:
            st.warning(f"TA error: {e}")
    else:
        st.error("No data returned! This ticker/interval/period combo is not supported by Yahoo, or market is closed.")
