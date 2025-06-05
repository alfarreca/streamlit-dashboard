import streamlit as st
import yfinance as yf
import plotly.graph_objs as go
import pandas as pd

# --- 1. Dummy data for demonstration (REPLACE with your loader) ---
# Remove/comment this and load your own DataFrame
if "filtered_results" not in st.session_state:
    # Demo DataFrame structure
    st.session_state.filtered_results = pd.DataFrame([
        {"Symbol": "AAPL", "YF_Symbol": "AAPL", "Price": 195.12, "5D_Change": 1.5, "20D_Change": 5.3, "Momentum_Score": 85, "Trend": "Strong", "ADX": 37, "RSI": 55, "MACD_Hist": 0.23, "Volume_Ratio": 1.8},
        {"Symbol": "MSFT", "YF_Symbol": "MSFT", "Price": 400.54, "5D_Change": -0.8, "20D_Change": 3.2, "Momentum_Score": 73, "Trend": "Moderate", "ADX": 29, "RSI": 48, "MACD_Hist": -0.12, "Volume_Ratio": 0.95},
    ])

df = st.session_state.filtered_results

if df.empty:
    st.warning("No stock data available. Please run your scan or load data.")
    st.stop()

# --- 2. Selectbox with sticky placeholder logic ---
placeholder_option = "— Select a symbol —"
symbol_list = list(df["Symbol"].unique())
options = [placeholder_option] + symbol_list

# Ensure session_state is in sync
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

# --- 3. Defensive Data Selection ---
selected_df = df[df["Symbol"] == selected_symbol]
if selected_df.empty:
    st.warning("No data found for this symbol.")
    st.stop()
symbol_data = selected_df.iloc[0]

# --- 4. Utilities ---
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

# --- 5. Main Display ---
def display_symbol_details(symbol_data):
    st.subheader(f"📊 {symbol_data['Symbol']} Detailed Analysis")
    tab1, tab2, tab3 = st.tabs(["Price Chart", "Technical Indicators", "Fundamentals"])

    with tab1:
        ticker = yf.Ticker(symbol_data["YF_Symbol"])
        hist = safe_yfinance_fetch(ticker, "6mo")
        if not hist.empty:
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
