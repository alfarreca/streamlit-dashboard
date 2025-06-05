import streamlit as st
import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import MACD, ADXIndicator
import plotly.graph_objs as go

st.title("S&P 500 Momentum Scanner (Cloud Edition)")

# --- 1. File upload OR default tickers ---
uploaded_file = st.file_uploader("Upload S&P 500 ticker list (CSV, must have 'Symbol')", type="csv")
if uploaded_file is not None:
    tickers_df = pd.read_csv(uploaded_file)
    st.success("Custom ticker list loaded.")
else:
    # fallback: small demo set, or load from a static file if you want
    tickers_df = pd.DataFrame({
        "Symbol": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"],
    })
    st.info("Using default demo tickers. Upload your own CSV for a full scan.")

# --- 2. Button to scan and calculate technicals ---
if st.button("Run Momentum Scan for All Tickers"):
    scan_output = []
    tickers = tickers_df["Symbol"].dropna().unique().tolist()
    progress_bar = st.progress(0, text="Scanning...")

    for i, symbol in enumerate(tickers):
        try:
            data = yf.download(symbol, period="6mo", auto_adjust=True, progress=False)
            if data.empty:
                continue
            close = data["Close"]
            price = close.iloc[-1]
            chg_5d = ((close.iloc[-1] / close.iloc[-6]) - 1) * 100 if len(close) >= 6 else 0
            chg_20d = ((close.iloc[-1] / close.iloc[-21]) - 1) * 100 if len(close) >= 21 else 0
            rsi = RSIIndicator(close, window=14).rsi().iloc[-1]
            macd_obj = MACD(close, window_slow=26, window_fast=12, window_sign=9)
            macd_hist = macd_obj.macd_diff().iloc[-1]
            adx = ADXIndicator(data["High"], data["Low"], close, window=14).adx().iloc[-1]
            momentum_score = (rsi + max(0, macd_hist * 10) + min(adx, 50)) / 3
            vol_ratio = data["Volume"].iloc[-1] / data["Volume"].rolling(20).mean().iloc[-1] if len(data) >= 20 else 1
            trend = "Strong" if adx >= 30 else "Moderate" if adx >= 20 else "Weak"
            scan_output.append({
                "Symbol": symbol,
                "YF_Symbol": symbol,
                "Price": round(price, 2),
                "5D_Change": round(chg_5d, 2),
                "20D_Change": round(chg_20d, 2),
                "Momentum_Score": round(momentum_score, 1),
                "Trend": trend,
                "ADX": round(adx, 2),
                "RSI": round(rsi, 2),
                "MACD_Hist": round(macd_hist, 3),
                "Volume_Ratio": round(vol_ratio, 2)
            })
        except Exception as e:
            st.warning(f"Error for {symbol}: {e}")
        progress_bar.progress((i + 1) / len(tickers), text=f"Scanning {symbol} ({i+1}/{len(tickers)})")

    st.session_state.filtered_results = pd.DataFrame(scan_output)
    st.success("Scan complete! Data is now available in the app.")

elif "filtered_results" in st.session_state and not st.session_state.filtered_results.empty:
    st.info("Using last scan or uploaded data.")

else:
    st.warning("Please upload a ticker list and/or run the scan to continue.")

# --- 3. Main dashboard (runs if data available) ---
if "filtered_results" in st.session_state and not st.session_state.filtered_results.empty:
    df = st.session_state.filtered_results

    # --- Symbol selectbox with sticky placeholder ---
    placeholder = "— Select a symbol —"
    symbols = list(df["Symbol"].unique())
    options = [placeholder] + symbols

    if "selected_symbol" not in st.session_state or st.session_state.selected_symbol not in options:
        st.session_state.selected_symbol = placeholder

    selected_symbol = st.selectbox(
        "Select a symbol for details",
        options,
        index=options.index(st.session_state.selected_symbol),
        key="selected_symbol"
    )

    if selected_symbol == placeholder:
        st.info("Please select a symbol to view details.")
        st.stop()

    # --- Utility functions ---
    def safe_yfinance_fetch(ticker, period):
        try:
            return ticker.history(period=period)
        except Exception as e:
            st.error(f"Error fetching price data: {e}")
            return pd.DataFrame()

    def create_price_chart(hist, symbol):
        fig = go.Figure(data=[go.Candlestick(
            x=hist.index,
            open=hist['Open'],
            high=hist['High'],
            low=hist['Low'],
            close=hist['Close']
        )])
        fig.update_layout(title=f"{symbol} Price Chart")
        return fig

    # --- Detail panel ---
    def display_symbol_details(selected_symbol):
        if not selected_symbol:
            return
        with st.spinner(f'Loading {selected_symbol} analysis...'):
            try:
                filtered_df = df[df["Symbol"] == selected_symbol]
                if filtered_df.empty:
                    st.warning(f"No data found for {selected_symbol}.")
                    return
                symbol_data = filtered_df.iloc[0]

                st.subheader(f"📊 {selected_symbol} Detailed Analysis")
                tab1, tab2, tab3 = st.tabs(["Price Chart", "Technical Indicators", "Fundamentals"])

                with tab1:
                    ticker = yf.Ticker(symbol_data["YF_Symbol"])
                    hist = safe_yfinance_fetch(ticker, "6mo")
                    if hist is not None and not hist.empty:
                        st.plotly_chart(create_price_chart(hist, selected_symbol), use_container_width=True)
                    else:
                        st.warning("Could not load price history for chart")

                with tab2:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Current Price", f"${symbol_data['Price']:,.2f}")
                        st.metric("5-Day Change", f"{symbol_data['5D_Change']:.1f}%")
                        st.metric("20-Day Change", f"{symbol_data['20D_Change']:.1f}%")
                    with col2:
                        st.metric("Momentum Score", symbol_data["Momentum_Score"])
                        st.metric("Trend Strength", symbol_data["Trend"])
                        st.metric("ADX", symbol_data["ADX"])
                    with col3:
                        st.metric("RSI", symbol_data["RSI"])
                        st.metric("MACD Histogram", f"{symbol_data['MACD_Hist']:.3f}")
                        st.metric("Volume Ratio", f"{symbol_data['Volume_Ratio']:.2f}x")
                    st.progress(max(0, min(symbol_data["Momentum_Score"]/100, 1.0)), text="Momentum Strength")
                    st.progress(max(0, min(symbol_data["RSI"]/100, 1.0)), text="RSI")
                    st.progress(max(0, min(symbol_data["ADX"]/50, 1.0)), text="ADX Trend Strength")

                with tab3:
                    st.info("Fundamental metrics unavailable on Streamlit Cloud (yfinance.info disabled).")

            except Exception as e:
                st.error(f"Error loading {selected_symbol}: {str(e)}")

    display_symbol_details(selected_symbol)
