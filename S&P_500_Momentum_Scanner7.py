import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objs as go

# --- 1. Data Loader: hybrid default CSV and upload ---
uploaded_file = st.file_uploader(
    "Upload your S&P 500 momentum scan results (CSV)", type="csv"
)

if uploaded_file is not None:
    try:
        st.session_state.filtered_results = pd.read_csv(uploaded_file)
        st.success("Custom scan loaded!")
    except Exception as e:
        st.error(f"Error reading uploaded file: {e}")
        st.session_state.filtered_results = pd.DataFrame()
elif "filtered_results" not in st.session_state:
    try:
        st.session_state.filtered_results = pd.read_csv("sp500_momentum_scan.csv")
        st.info("Loaded most recent scan from sp500_momentum_scan.csv")
    except Exception as e:
        st.error(
            f"No scan file found. Please upload a scan or place sp500_momentum_scan.csv in your app directory. Error: {e}"
        )
        st.session_state.filtered_results = pd.DataFrame()

df = st.session_state.filtered_results

if df.empty:
    st.warning("No stock data available. Please run your scan or load data.")
    st.stop()

# --- 2. Symbol selectbox with sticky placeholder ---
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

# --- 3. Utility functions ---
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

# --- 4. Detail panel, original structure but robust ---
def display_symbol_details(selected_symbol):
    if not selected_symbol:
        return
    with st.spinner(f'Loading {selected_symbol} analysis...'):
        try:
            filtered_df = st.session_state.filtered_results[
                st.session_state.filtered_results["Symbol"] == selected_symbol
            ]
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
                try:
                    ticker = yf.Ticker(symbol_data["YF_Symbol"])
                    info = ticker.info
                    col1, col2 = st.columns(2)

                    with col1:
                        st.metric("Market Cap", f"${info.get('marketCap', 'N/A')/1e9:,.2f}B" if info.get('marketCap') else "N/A")
                        st.metric("P/E Ratio", info.get('trailingPE', 'N/A'))
                        st.metric("EPS", info.get('trailingEps', 'N/A'))
                        st.metric("Dividend Yield", f"{info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else "0%")

                    with col2:
                        st.metric("52 Week High", f"${info.get('fiftyTwoWeekHigh', 'N/A'):,.2f}")
                        st.metric("52 Week Low", f"${info.get('fiftyTwoWeekLow', 'N/A'):,.2f}")
                        st.metric("Beta", info.get('beta', 'N/A'))
                        st.metric("Average Volume", f"{info.get('averageVolume', 'N/A'):,.0f}")
                except Exception as e:
                    st.warning(f"Could not load fundamental data for this stock: {e}")

        except Exception as e:
            st.error(f"Error loading {selected_symbol}: {str(e)}")

# --- 5. Show selected symbol details ---
display_symbol_details(selected_symbol)
