import streamlit as st
import yfinance as yf

# --- 1. Assume filtered_results is already in session_state ---
# For demo purposes:
# st.session_state.filtered_results = your_dataframe_with_symbol_column

# --- 2. Setup Selectbox Options and Session State ---
placeholder_option = "— Select a symbol —"

if "filtered_results" not in st.session_state or st.session_state.filtered_results.empty:
    st.warning("No stock data available. Please run your scan or load data.")
    st.stop()

symbol_list = list(st.session_state.filtered_results["Symbol"].unique())
options = [placeholder_option] + symbol_list

# Ensure selection persists
if "selected_symbol" not in st.session_state or st.session_state.selected_symbol not in options:
    st.session_state.selected_symbol = placeholder_option

selected_symbol = st.selectbox(
    "Select a symbol for details",
    options,
    index=options.index(st.session_state.selected_symbol),
    key="selected_symbol"
)

if selected_symbol == placeholder_option:
    st.info("Please select a symbol to view details.")
    st.stop()

# --- 3. Defensive Check for DataFrame ---
df = st.session_state.filtered_results[
    st.session_state.filtered_results["Symbol"] == selected_symbol
]
if df.empty:
    st.warning("No data found for this symbol.")
    st.stop()
symbol_data = df.iloc[0]

# --- 4. Display Symbol Details (Modular) ---
def safe_yfinance_fetch(ticker, period):
    try:
        return ticker.history(period=period)
    except Exception as e:
        st.error(f"Error fetching price data: {e}")
        return None

def create_price_chart(hist, symbol):
    import plotly.graph_objs as go
    fig = go.Figure(data=[go.Candlestick(
        x=hist.index,
        open=hist['Open'],
        high=hist['High'],
        low=hist['Low'],
        close=hist['Close']
    )])
    fig.update_layout(title=f"{symbol} Price Chart")
    return fig

def display_symbol_details(symbol_data):
    st.subheader(f"📊 {symbol_data['Symbol']} Detailed Analysis")
    tab1, tab2, tab3 = st.tabs(["Price Chart", "Technical Indicators", "Fundamentals"])

    with tab1:
        ticker = yf.Ticker(symbol_data["YF_Symbol"])
        hist = safe_yfinance_fetch(ticker, "6mo")
        if hist is not None and not hist.empty:
            st.plotly_chart(create_price_chart(hist, symbol_data['Symbol']), use_container_width=True)
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

display_symbol_details(symbol_data)
