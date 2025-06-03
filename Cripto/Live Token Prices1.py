import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
import plotly.express as px
import numpy as np
import requests
from pytz import timezone
from streamlit_autorefresh import st_autorefresh

# --- CONFIG ---
st.set_page_config(page_title="Multi-Source Crypto Dashboard", page_icon="₿", layout="wide")
TIMEZONE = timezone('UTC')
REFRESH_INTERVAL = 300  # seconds
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

# --- SESSION STATE ---
if 'data_sources' not in st.session_state:
    st.session_state.data_sources = {}
if 'last_updated' not in st.session_state:
    st.session_state.last_updated = None

# --- DATA FETCHING HELPERS ---
@st.cache_data(ttl=REFRESH_INTERVAL, show_spinner=False)
def get_coingecko_data(ticker_id):
    try:
        price_url = f"{COINGECKO_API_URL}/simple/price?ids={ticker_id}&vs_currencies=usd&include_24hr_change=true"
        price_response = requests.get(price_url, timeout=10)
        price_data = price_response.json().get(ticker_id, {})
        if not price_data:
            return None, None, None, None
        current_price = price_data.get('usd')
        daily_change = price_data.get('usd_24h_change', 0)
        hist_url = f"{COINGECKO_API_URL}/coins/{ticker_id}/market_chart?vs_currency=usd&days=7"
        hist_response = requests.get(hist_url, timeout=10)
        hist_data = hist_response.json()
        if not hist_data.get('prices'):
            return current_price, daily_change, 0, None
        prices = [p[1] for p in hist_data['prices']]
        weekly_change = ((prices[-1] - prices[0]) / prices[0]) * 100 if prices[0] else 0
        hist_df = pd.DataFrame({
            'Date': [datetime.fromtimestamp(p[0]/1000) for p in hist_data['prices']],
            'Close': [p[1] for p in hist_data['prices']],
            'Volume': [v[1] for v in hist_data['total_volumes']]
        }).set_index('Date')
        return current_price, daily_change, weekly_change, hist_df
    except Exception as e:
        return None, None, None, None

@st.cache_data(ttl=REFRESH_INTERVAL, show_spinner=False)
def get_yahoo_crypto_data(ticker):
    try:
        base_ticker = ticker.split('.')[0].split('-')[0].upper()
        yahoo_ticker = f"{base_ticker}-USD"
        data = yf.Ticker(yahoo_ticker)
        hist = data.history(period="7d", interval="1d")
        if hist.empty:
            return None, None, None, None
        current_price = hist['Close'].iloc[-1]
        prev_price = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        week_ago_price = hist['Close'].iloc[0] if len(hist) > 1 else current_price
        daily_change = ((current_price - prev_price) / prev_price) * 100 if prev_price else 0
        weekly_change = ((current_price - week_ago_price) / week_ago_price) * 100 if week_ago_price else 0
        return current_price, daily_change, weekly_change, hist
    except Exception as e:
        return None, None, None, None

def get_crypto_data(ticker, symbol):
    tokens_without_price = ['Various', 'bCSPX', 'REALTOKEN']
    coingecko_mapping = {
        "UNI": "uniswap",
        "MPL": "maple",
        "CFG": "centrifuge",
        "ONDO": "ondo-finance"
    }
    if symbol in tokens_without_price or ticker in tokens_without_price:
        st.session_state.data_sources[symbol] = "N/A"
        return None, None, None, None
    if symbol in coingecko_mapping:
        st.session_state.data_sources[symbol] = "CoinGecko"
        return get_coingecko_data(coingecko_mapping[symbol])
    else:
        st.session_state.data_sources[symbol] = "Yahoo Finance"
        return get_yahoo_crypto_data(ticker)

def format_percent(x):
    if isinstance(x, (float, int, np.floating, np.integer)):
        color = "green" if x > 0 else ("red" if x < 0 else "gray")
        emoji = "🟢" if x > 0 else ("🔴" if x < 0 else "⚪")
        return f"{emoji} <span style='color:{color}'>{x:+.2f}%</span>"
    return x  # leaves "N/A" or other strings untouched

def format_currency(val):
    if isinstance(val, (float, int, np.floating, np.integer)):
        return f"${val:,.2f}"
    return val

def format_volume(val):
    if isinstance(val, (float, int, np.floating, np.integer)):
        if val >= 1e9:
            return f"${val/1e9:.2f}B"
        elif val >= 1e6:
            return f"${val/1e6:.2f}M"
        elif val >= 1e3:
            return f"${val/1e3:.2f}K"
        else:
            return f"${val:.0f}"
    return val

def get_df_filtered(df, category, source, symbol):
    df_filtered = df.copy()
    if category != "All":
        df_filtered = df_filtered[df_filtered["Category"] == category]
    if source != "All":
        df_filtered = df_filtered[df_filtered["Source"] == source]
    if symbol != "All":
        df_filtered = df_filtered[df_filtered["Symbol"] == symbol]
    return df_filtered

# --- MAIN APP ---
def main():
    st.title("🌐 Multi-Source Crypto Dashboard")
    # Show last updated time
    now = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S UTC")
    st.session_state.last_updated = now
    st.markdown(f"**Last Updated:** {now}")

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("Filters & Controls")
        auto_refresh = st.checkbox("Enable auto-refresh", value=True)
        if auto_refresh:
            st_autorefresh(interval=REFRESH_INTERVAL * 1000, key="datarefresh")
        st.markdown("---")
        st.header("Filter Tokens")
    
    crypto_data = [
        {
            "Category": "DeFi",
            "Project": "Uniswap",
            "Purpose": "Uniswap is a decentralized exchange (DEX) protocol. The UNI token is used for governance of the Uniswap protocol.",
            "Token ID": "UNI-USD",
            "Symbol": "UNI"
        },
        {
            "Category": "DeFi",
            "Project": "Aave",
            "Purpose": "Aave is a decentralized lending/borrowing protocol. The AAVE token is used for governance and staking.",
            "Token ID": "AAVE-USD",
            "Symbol": "AAVE"
        },
        {
            "Category": "DeFi",
            "Project": "dYdX",
            "Purpose": "dYdX is a decentralized derivatives exchange. The DYDX token is used for governance and as a reward.",
            "Token ID": "DYDX",
            "Symbol": "DYDX"
        },
        {
            "Category": "DeFi",
            "Project": "Curve Finance",
            "Purpose": "Curve Finance is a DEX optimized for stablecoin trading. The CRV token is used for governance and incentivizing liquidity providers.",
            "Token ID": "CRV",
            "Symbol": "CRV"
        },
        {
            "Category": "Tokenized RWA",
            "Project": "Ondo Finance",
            "Purpose": "Ondo Finance offers tokenized US Treasuries and other real-world assets. The ONDO token governs the protocol.",
            "Token ID": "ONDO",
            "Symbol": "ONDO"
        },
        {
            "Category": "Tokenized RWA",
            "Project": "RealT",
            "Purpose": "RealT provides tokenized real estate (mainly US properties), enabling users to earn passive income from rent. Tokens represent fractional ownership. Price data is not available for 'Various'; check RealT for specific property tokens.",
            "Token ID": "REALTOKEN",
            "Symbol": "Various"
        },
        {
            "Category": "Tokenized RWA",
            "Project": "Maple Finance",
            "Purpose": "Maple Finance is a decentralized credit marketplace for institutional loans. The MPL token is used for governance and staking.",
            "Token ID": "MPL",
            "Symbol": "MPL"
        },
        {
            "Category": "Tokenized RWA",
            "Project": "Backed Finance",
            "Purpose": "Backed Finance brings tokenized ETFs and stocks on-chain. Example token: bCSPX (mirrors S&P 500 ETF). No public price feed is available.",
            "Token ID": "bCSPX",
            "Symbol": "bCSPX"
        },
        {
            "Category": "Tokenized RWA",
            "Project": "Centrifuge",
            "Purpose": "Centrifuge enables asset-backed lending, bringing real-world assets like invoices and real estate on-chain. The CFG token is used for staking and governance.",
            "Token ID": "CFG",
            "Symbol": "CFG"
        },
        {
            "Category": "Tokenized RWA",
            "Project": "Polymesh",
            "Purpose": "Polymesh is a blockchain for regulated assets. The POLYX token is used for transaction fees and governance.",
            "Token ID": "POLYX",
            "Symbol": "POLYX"
        },
    ]

    df = pd.DataFrame(crypto_data)
    for col in ["Price", "24h Change", "7d Trend", "Volume", "Source", "Hist"]:
        if col not in df.columns:
            df[col] = np.nan

    with st.spinner("Loading multi-source market data..."):
        progress_bar = st.progress(0)
        for i, row in df.iterrows():
            ticker = row['Token ID']
            symbol = row['Symbol']
            price, daily_change, weekly_change, hist = get_crypto_data(ticker, symbol)
            if price is not None:
                df.at[i, 'Price'] = price
                df.at[i, '24h Change'] = daily_change
                df.at[i, '7d Trend'] = weekly_change
                df.at[i, 'Volume'] = hist['Volume'].iloc[-1] if hist is not None and 'Volume' in hist.columns else 0
                df.at[i, 'Source'] = st.session_state.data_sources.get(symbol, "Unknown")
                df.at[i, 'Hist'] = hist
            else:
                df.at[i, 'Price'] = "N/A"
                df.at[i, '24h Change'] = "N/A"
                df.at[i, '7d Trend'] = "N/A"
                df.at[i, 'Volume'] = "N/A"
                df.at[i, 'Source'] = st.session_state.data_sources.get(symbol, "N/A")
                df.at[i, 'Hist'] = None
            progress_bar.progress((i + 1) / len(df))

    # --- Sidebar Filtering ---
    categories = ["All"] + sorted(df["Category"].unique())
    data_sources = ["All"] + sorted(df["Source"].unique())
    symbols = ["All"] + sorted(df["Symbol"].unique())
    with st.sidebar:
        category_filter = st.selectbox("Category", categories)
        source_filter = st.selectbox("Data Source", data_sources)
        symbol_filter = st.selectbox("Symbol", symbols)
        st.markdown("---")
        st.write("**Table Legend:**")
        st.help("🟢 Green: Positive change\n🔴 Red: Negative change\n⚪ Gray: No change\nN/A: Not available")

    # --- Table Formatting ---
    df_display = df.copy()
    df_display["Price"] = df_display["Price"].apply(format_currency)
    df_display["Volume"] = df_display["Volume"].apply(format_volume)
    for col in ["24h Change", "7d Trend"]:
        df_display[col] = df_display[col].apply(format_percent)

    # --- Filtering ---
    filtered_df = get_df_filtered(df_display, category_filter, source_filter, symbol_filter)

    # --- Table Display ---
    st.markdown("### Token Market Data")
    st.markdown("_Click a row for more details and a 7-day chart (where available)._")
    st.dataframe(
        filtered_df[["Category", "Project", "Symbol", "Price", "24h Change", "7d Trend", "Volume", "Source"]],
        use_container_width=True,
        height=500,
        hide_index=True,
        column_config={
            "Source": st.column_config.TextColumn("Data Source")
        }
    )

    # --- Expandable Detail Section ---
    st.markdown("---")
    st.markdown("### Token Explanations & Charts")
    for i, row in filtered_df.iterrows():
        with st.expander(f"{row['Symbol']} ({row['Project']})"):
            st.markdown(f"**Purpose:** {row['Purpose']}")
            st.markdown(f"**Category:** {row['Category']}")
            st.markdown(f"**Source:** {row['Source']}")
            if isinstance(row["Price"], str) and row["Price"] == "N/A":
                st.info("No public price feed available for this token.")
            elif isinstance(df.loc[df_display.index[i], "Hist"], pd.DataFrame):
                hist = df.loc[df_display.index[i], "Hist"]
                fig = px.line(hist, y="Close", title=f"{row['Symbol']} 7-day Price Trend (USD)")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No historical chart data available.")

    # --- Visualization ---
    st.markdown("---")
    st.subheader("Multi-Source Performance")
    tab1, tab2 = st.tabs(["Price Comparison", "Source Distribution"])
    with tab1:
        display_df = df[df["24h Change"].apply(lambda x: isinstance(x, (int, float, np.floating, np.integer)))]
        if not display_df.empty:
            fig = px.bar(
                display_df.sort_values('24h Change', ascending=False),
                x='Symbol',
                y='24h Change',
                color='Source',
                color_discrete_map={
                    "CoinGecko": "#8CC63F",
                    "Yahoo Finance": "#720E9E"
                },
                title="24h Price Change by Data Source"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No price data available for chart.")
    with tab2:
        source_counts = df['Source'].value_counts().reset_index()
        source_counts.columns = ['Source', 'count']
        fig = px.pie(
            source_counts,
            names='Source',
            values='count',
            color='Source',
            color_discrete_map={
                "CoinGecko": "#8CC63F",
                "Yahoo Finance": "#720E9E",
                "N/A": "gray"
            },
            title="Data Source Distribution"
        )
        st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()
