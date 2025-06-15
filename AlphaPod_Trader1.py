import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import numpy as np
import time
import io

# --- Configuration ---
st.set_page_config(layout="wide", page_title="AlphaPod Trader", page_icon="📈")

# --- Session State ---
if "trades" not in st.session_state:
    st.session_state.trades = pd.DataFrame(columns=["timestamp", "ticker", "strategy", "status"])
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []
if "watchlist_ex" not in st.session_state:
    st.session_state.watchlist_ex = {}  # to store exchange info (optional)
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = None

# --- Add a demo trade for visual feedback if table is empty ---
if st.session_state.trades.empty:
    st.session_state.trades = pd.DataFrame([{
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ticker": "NVDA",
        "strategy": "Earnings Beat",
        "status": "Open"
    }])

def remove_from_watchlist(ticker):
    if ticker in st.session_state.watchlist:
        idx = st.session_state.watchlist.index(ticker)
        st.session_state.watchlist.pop(idx)
        if ticker in st.session_state.watchlist_ex:
            st.session_state.watchlist_ex.pop(ticker)
        st.toast(f"{ticker} removed from watchlist")

# --- Sidebar UI ---
with st.sidebar:
    st.header("Controls")
    if st.button("🔄 Refresh Data"):
        st.session_state.last_refresh = datetime.now()

    st.metric("Last Refresh",
              st.session_state.last_refresh.strftime("%Y-%m-%d %H:%M:%S")
              if st.session_state.last_refresh else "Never")

    # --- XLSX Watchlist Upload ---
    st.header("Watchlist Management")
    uploaded_file = st.file_uploader("Upload Watchlist (.xlsx)", type=["xlsx"])
    if uploaded_file is not None:
        try:
            df_watchlist = pd.read_excel(uploaded_file)
            if "Symbol" in df_watchlist.columns and "Exchange" in df_watchlist.columns:
                symbols = df_watchlist["Symbol"].astype(str).str.upper().tolist()
                exchanges = df_watchlist["Exchange"].astype(str).tolist()
                # Only add new tickers
                new_tickers = [s for s in symbols if s not in st.session_state.watchlist]
                st.session_state.watchlist.extend(new_tickers)
                for s, ex in zip(symbols, exchanges):
                    st.session_state.watchlist_ex[s] = ex
                st.success(f"Added {len(new_tickers)} tickers to watchlist!")
            else:
                st.error("Excel file must contain columns: 'Symbol' and 'Exchange'.")
        except Exception as e:
            st.error(f"Failed to read file: {e}")

    if st.session_state.watchlist:
        for ticker in st.session_state.watchlist:
            ex = st.session_state.watchlist_ex.get(ticker, "")
            col1, col2 = st.columns([4, 1])
            if ex:
                col1.write(f"{ticker} ({ex})")
            else:
                col1.write(ticker)
            if col2.button("❌", key=f"remove_{ticker}"):
                remove_from_watchlist(ticker)
    else:
        st.write("Watchlist is empty.")

# --- Main Dashboard ---
st.title("📈 AlphaPod Trader")

dashboard_tab, portfolio_tab = st.tabs(["📊 Watchlist Dashboard", "💼 Portfolio"])

with dashboard_tab:
    st.header("Watchlist Overview")
    if not st.session_state.watchlist:
        st.info("Upload a watchlist file (.xlsx) with columns 'Symbol' and 'Exchange' to get started!")
    else:
        for ticker in st.session_state.watchlist:
            st.subheader(f"{ticker}" + (f" ({st.session_state.watchlist_ex.get(ticker, '')})" if st.session_state.watchlist_ex.get(ticker) else ""))
            # Download up to 1 month of daily data for chart
            try:
                data = yf.Ticker(ticker)
                hist = data.history(period="1mo")
                info = data.info

                # Price, change, etc.
                last_quote = hist['Close'][-1] if isinstance(hist, pd.DataFrame) and not hist.empty else None
                prev_quote = hist['Close'][-2] if isinstance(hist, pd.DataFrame) and len(hist) > 1 else last_quote
                pct_change = ((last_quote - prev_quote) / prev_quote * 100) if last_quote and prev_quote else 0
                st.metric("Last Price", f"${last_quote:.2f}" if last_quote else "N/A", 
                          f"{pct_change:+.2f}%" if last_quote and prev_quote else "N/A")

                # Chart
                if isinstance(hist, pd.DataFrame) and not hist.empty:
                    st.line_chart(hist['Close'], use_container_width=True)
                else:
                    st.write("_No recent price data available for this symbol._")

                # Earnings date (robust)
                cal = data.calendar
                if isinstance(cal, pd.DataFrame) and not cal.empty and 'Earnings Date' in cal.index:
                    earnings = cal.loc['Earnings Date'][0]
                    st.write(f"**Next Earnings Date:** {earnings.strftime('%Y-%m-%d') if isinstance(earnings, pd.Timestamp) else earnings}")
                else:
                    st.write("_Earnings date unavailable._")
            except Exception as e:
                st.warning(f"Could not retrieve data for {ticker}: {e}")

with portfolio_tab:
    st.header("Trade History")
    st.dataframe(st.session_state.trades, use_container_width=True)

