import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
import numpy as np
import requests

# --- Configuration ---
st.set_page_config(layout="wide", page_title="AlphaPod Trader", page_icon="📈")

# --- API (Polygon for Earnings Demo) ---
POLYGON_KEY = st.secrets.get("POLYGON_KEY", "demo_key")
TIMEOUT = 10
MAX_RETRIES = 3

def fetch_polygon_earnings():
    url = "https://api.polygon.io/v2/reference/earnings"
    params = {
        "apiKey": POLYGON_KEY,
        "date.gte": (datetime.now() - pd.Timedelta(days=7)).strftime("%Y-%m-%d"),
        "date.lte": (datetime.now() + pd.Timedelta(days=7)).strftime("%Y-%m-%d"),
        "limit": 20
    }
    try:
        for _ in range(MAX_RETRIES):
            r = requests.get(url, params=params, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass
    # fallback demo data
    return {
        "results": [
            {
                "ticker": "NVDA",
                "reportDate": (datetime.now() + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                "epsEstimate": 3.34,
                "eps": 3.71,
                "surprisePercent": 11.08
            },
            {
                "ticker": "TSLA",
                "reportDate": (datetime.now() + pd.Timedelta(days=2)).strftime("%Y-%m-%d"),
                "epsEstimate": 0.73,
                "eps": 0.85,
                "surprisePercent": 16.44
            }
        ]
    }

def calculate_iv_rank(ticker):
    return int(np.clip(np.random.normal(60, 20), 0, 100))

def get_stock_price(ticker):
    demo_prices = {
        "NVDA": 450.50,
        "TSLA": 210.75,
        "AAPL": 175.25,
        "MSFT": 310.40
    }
    return demo_prices.get(ticker, 100.00)

# --- Session State ---
if "trades" not in st.session_state:
    st.session_state.trades = pd.DataFrame(columns=["timestamp", "ticker", "strategy", "status"])
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []
if "watchlist_ex" not in st.session_state:
    st.session_state.watchlist_ex = {}  # Exchange info for each ticker
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = None

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

    st.header("Watchlist Management")
    uploaded_file = st.file_uploader("Upload Watchlist (.xlsx)", type=["xlsx"])
    if uploaded_file is not None:
        try:
            df_watchlist = pd.read_excel(uploaded_file)
            if "Symbol" in df_watchlist.columns and "Exchange" in df_watchlist.columns:
                symbols = df_watchlist["Symbol"].astype(str).str.upper().tolist()
                exchanges = df_watchlist["Exchange"].astype(str).tolist()
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

# --- Main Tabs ---
tab1, tab2, tab3 = st.tabs(["Earnings Plays", "Watchlist Dashboard", "Portfolio"])

with tab1:
    st.title("📈 AlphaPod Trader")
    st.header("Upcoming Earnings Opportunities")
    market_data = fetch_polygon_earnings()
    for play in market_data.get("results", [])[:15]:
        with st.expander(f"{play['ticker']}", expanded=False):
            cols = st.columns([1,1,2])
            with cols[0]:
                st.metric("EPS Surprise", f"{play.get('surprisePercent', 0):.2f}%")
                st.metric("IV Rank", f"{calculate_iv_rank(play['ticker']):.0f}%")
            with cols[1]:
                st.metric("Price", f"${get_stock_price(play['ticker']):.2f}")
                st.metric("Volume", f"{np.random.uniform(1.5,2.1):.1f}x")  # Demo value
            with cols[2]:
                if st.button("📊 Analyze", key=f"analyze_{play['ticker']}"):
                    st.session_state.current_ticker = play['ticker']
                if st.button("➕ Add to Watchlist", key=f"watch_{play['ticker']}"):
                    if play['ticker'] not in st.session_state.watchlist:
                        st.session_state.watchlist.append(play['ticker'])
                        st.toast(f"Added {play['ticker']} to watchlist")

with tab2:
    st.title("📈 AlphaPod Trader")
    st.header("Watchlist Overview")
    if not st.session_state.watchlist:
        st.info("Upload a watchlist file (.xlsx) with columns 'Symbol' and 'Exchange' to get started!")
    else:
        for ticker in st.session_state.watchlist:
            st.subheader(f"{ticker}" + (f" ({st.session_state.watchlist_ex.get(ticker, '')})" if st.session_state.watchlist_ex.get(ticker) else ""))
            try:
                data = yf.Ticker(ticker)
                hist = data.history(period="1mo")
                info = data.info

                last_quote = hist['Close'][-1] if isinstance(hist, pd.DataFrame) and not hist.empty else None
                prev_quote = hist['Close'][-2] if isinstance(hist, pd.DataFrame) and len(hist) > 1 else last_quote
                pct_change = ((last_quote - prev_quote) / prev_quote * 100) if last_quote and prev_quote else 0
                st.metric("Last Price", f"${last_quote:.2f}" if last_quote else "N/A", 
                          f"{pct_change:+.2f}%" if last_quote and prev_quote else "N/A")

                if isinstance(hist, pd.DataFrame) and not hist.empty:
                    st.line_chart(hist['Close'], use_container_width=True)
                else:
                    st.write("_No recent price data available for this symbol._")

                # Robust earnings date logic
                earnings_shown = False
                cal = data.calendar
                if isinstance(cal, pd.DataFrame) and not cal.empty and 'Earnings Date' in cal.index:
                    earnings = cal.loc['Earnings Date'][0]
                    st.write(f"**Next Earnings Date:** {earnings.strftime('%Y-%m-%d') if isinstance(earnings, pd.Timestamp) else earnings}")
                    earnings_shown = True
                else:
                    try:
                        edf = data.earnings_dates
                        if isinstance(edf, pd.DataFrame) and not edf.empty:
                            next_earning = edf.index[0] if hasattr(edf, "index") and len(edf.index) > 0 else None
                            if next_earning:
                                st.write(f"**Next Earnings Date:** {pd.to_datetime(next_earning).strftime('%Y-%m-%d')}")
                                earnings_shown = True
                    except Exception:
                        pass

                if not earnings_shown:
                    st.write("_Earnings date unavailable._")
            except Exception as e:
                st.warning(f"Could not retrieve data for {ticker}: {e}")

with tab3:
    st.header("Trade History")
    st.dataframe(st.session_state.trades, use_container_width=True)
