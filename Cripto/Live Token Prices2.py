# =============================================================================
# Cripto/Live Token Prices2.py
#
# Token Inclusion Criteria:
# - All tokens must be either:
#   - A top 50 DeFi protocol by Total Value Locked (TVL)
#   - OR a leading RWA project with on-chain activity and a public price feed
# - Preference to tokens/projects with active institutional involvement
# - Rationale and type for each token is listed below
# =============================================================================

import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
import plotly.express as px
import numpy as np
import requests
from pytz import timezone
from streamlit_autorefresh import st_autorefresh

# ---- Institutional Adoption Data ----
institutional_adoption = [
    {
        "Institution": "Franklin Templeton",
        "Project/Token": "BENJI",
        "Initiative": "Tokenized US Govt. Money Fund (Stellar/Polygon)",
        "Summary": "First major asset manager to issue a regulated US fund as blockchain tokens."
    },
    {
        "Institution": "BlackRock",
        "Project/Token": "ONDO (partner)",
        "Initiative": "Tokenized Treasuries & Partnerships",
        "Summary": "Partners with Ondo to bring tokenized treasuries to institutions and DeFi."
    },
    {
        "Institution": "Ondo Finance",
        "Project/Token": "ONDO",
        "Initiative": "Tokenized Treasuries",
        "Summary": "Institutional partnerships with BlackRock, Morgan Stanley, and others."
    },
    {
        "Institution": "Backed Finance",
        "Project/Token": "bCSPX",
        "Initiative": "Tokenized ETFs/Stocks",
        "Summary": "Swiss-regulated tokenization of ETFs like iShares S&P 500."
    },
    {
        "Institution": "Maple Finance",
        "Project/Token": "MPL",
        "Initiative": "On-chain Institutional Lending",
        "Summary": "Lends to hedge funds, market makers, and now RWA borrowers."
    },
    {
        "Institution": "Centrifuge",
        "Project/Token": "CFG",
        "Initiative": "RWA Lending Pools",
        "Summary": "Works with fintechs and institutions to onboard real-world assets."
    },
    {
        "Institution": "Aave/Maker/Compound/Synthetix/Curve",
        "Project/Token": "AAVE, MKR, COMP, SNX, CRV",
        "Initiative": "DeFi Blue Chip RWA Integration",
        "Summary": "Protocols integrating RWA as collateral or lending assets."
    },
    {
        "Institution": "Polymesh",
        "Project/Token": "POLYX",
        "Initiative": "Regulated Digital Securities",
        "Summary": "Adopted by broker-dealers and banks for compliant digital assets."
    },
]
institutional_df = pd.DataFrame(institutional_adoption)

st.set_page_config(page_title="Multi-Source Crypto Dashboard", page_icon="₿", layout="wide")
TIMEZONE = timezone('UTC')
REFRESH_INTERVAL = 300  # seconds
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

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
    except Exception:
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
    except Exception:
        return None, None, None, None

def get_crypto_data(ticker, symbol):
    tokens_without_price = ['Various', 'bCSPX', 'REALTOKEN', 'BENJI', 'TBILL', 'SBTB', 'TBY']
    coingecko_mapping = {
        "UNI": "uniswap",
        "MPL": "maple",
        "CFG": "centrifuge",
        "ONDO": "ondo-finance",
        "COMP": "compound-governance-token",
        "MKR": "maker",
        "SNX": "synthetix-network-token"
        # Add more if CoinGecko supports them
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
        return f"{x:+.2f}%"
    return x

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

def get_df_filtered(df, category, source, symbol, token_type, min_volume=None):
    df_filtered = df.copy()
    if category != "All":
        df_filtered = df_filtered[df_filtered["Category"] == category]
    if source != "All":
        df_filtered = df_filtered[df_filtered["Source"] == source]
    if symbol != "All":
        df_filtered = df_filtered[df_filtered["Symbol"] == symbol]
    if token_type != "All":
        df_filtered = df_filtered[df_filtered["Type"] == token_type]
    if min_volume is not None:
        df_filtered = df_filtered[df_filtered["Volume"].apply(lambda x: (isinstance(x, (int, float, np.floating, np.integer)) and x >= min_volume))]
    return df_filtered

def main():
    st.title("🌐 Multi-Source Crypto Dashboard")
    now = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S UTC")
    st.session_state.last_updated = now
    st.markdown(f"**Last Updated:** {now}")

    with st.sidebar:
        st.info("This dashboard highlights tokens and protocols with real institutional adoption in crypto, RWA, and blockchain finance.")
        st.header("Filters & Controls")
        auto_refresh = st.checkbox("Enable auto-refresh", value=True)
        if auto_refresh:
            st_autorefresh(interval=REFRESH_INTERVAL * 1000, key="datarefresh")
        st.markdown("---")
        st.header("Filter Tokens")

    # --- TOKEN LIST ---
    crypto_data = [
        # --- DeFi Blue Chips ---
        {"Category": "DeFi", "Type": "Governance", "Project": "Uniswap", "Purpose": "DEX protocol, governance via UNI.", "Token ID": "UNI-USD", "Symbol": "UNI"},
        {"Category": "DeFi", "Type": "Governance", "Project": "Aave", "Purpose": "Lending/borrowing, governance via AAVE.", "Token ID": "AAVE-USD", "Symbol": "AAVE"},
        {"Category": "DeFi", "Type": "Governance", "Project": "dYdX", "Purpose": "Perpetuals DEX, governance via DYDX.", "Token ID": "DYDX", "Symbol": "DYDX"},
        {"Category": "DeFi", "Type": "Governance", "Project": "Curve Finance", "Purpose": "Stablecoin DEX, governance via CRV.", "Token ID": "CRV", "Symbol": "CRV"},
        {"Category": "DeFi", "Type": "Governance", "Project": "Compound", "Purpose": "Lending protocol, governance via COMP.", "Token ID": "COMP", "Symbol": "COMP"},
        {"Category": "DeFi", "Type": "Governance", "Project": "Maker", "Purpose": "DAI stablecoin governance.", "Token ID": "MKR", "Symbol": "MKR"},
        {"Category": "DeFi", "Type": "Governance", "Project": "Synthetix", "Purpose": "Synthetic assets protocol, governance via SNX.", "Token ID": "SNX", "Symbol": "SNX"},
        # --- Leading RWA ---
        {"Category": "Tokenized RWA", "Type": "Governance", "Project": "Ondo Finance", "Purpose": "Tokenized treasuries/RWA, ONDO governance.", "Token ID": "ONDO", "Symbol": "ONDO"},
        {"Category": "Tokenized RWA", "Type": "Asset-backed", "Project": "RealT", "Purpose": "Tokenized real estate (fractional property tokens).", "Token ID": "REALTOKEN", "Symbol": "Various"},
        {"Category": "Tokenized RWA", "Type": "Governance", "Project": "Maple Finance", "Purpose": "Institutional lending, governance via MPL.", "Token ID": "MPL", "Symbol": "MPL"},
        {"Category": "Tokenized RWA", "Type": "Asset-backed", "Project": "Backed Finance", "Purpose": "Tokenized ETFs/stocks (e.g. bCSPX).", "Token ID": "bCSPX", "Symbol": "bCSPX"},
        {"Category": "Tokenized RWA", "Type": "Governance", "Project": "Centrifuge", "Purpose": "RWA lending, governance via CFG.", "Token ID": "CFG", "Symbol": "CFG"},
        {"Category": "Tokenized RWA", "Type": "Governance", "Project": "Polymesh", "Purpose": "Regulated asset chain, POLYX governance.", "Token ID": "POLYX", "Symbol": "POLYX"},
        # --- Notable RWA additions (price feed N/A unless noted) ---
        {"Category": "Tokenized RWA", "Type": "Asset-backed", "Project": "Franklin Templeton", "Purpose": "Money market fund (BENJI); not yet publicly priced on-chain.", "Token ID": "BENJI", "Symbol": "BENJI"},
        {"Category": "Tokenized RWA", "Type": "Asset-backed", "Project": "OpenEden", "Purpose": "Tokenized US Treasuries (TBILL); not yet publicly priced on-chain.", "Token ID": "TBILL", "Symbol": "TBILL"},
        {"Category": "Tokenized RWA", "Type": "Asset-backed", "Project": "Matrixdock", "Purpose": "Tokenized short-term T-bills (SBTB); not yet publicly priced on-chain.", "Token ID": "SBTB", "Symbol": "SBTB"},
        {"Category": "Tokenized RWA", "Type": "Asset-backed", "Project": "Swarm", "Purpose": "Tokenized Treasury Bills (TBY); not yet publicly priced on-chain.", "Token ID": "TBY", "Symbol": "TBY"},
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
    types = ["All"] + sorted(df["Type"].unique())
    with st.sidebar:
        category_filter = st.selectbox("Category", categories)
        source_filter = st.selectbox("Data Source", data_sources)
        symbol_filter = st.selectbox("Symbol", symbols)
        type_filter = st.selectbox("Token Type", types)
        st.markdown("---")
        min_vol_filter_on = st.checkbox("Minimum Volume filter", value=False)
        min_volume = None
        if min_vol_filter_on:
            min_volume = st.number_input("Min. 24h Volume ($)", min_value=0, value=10000, step=1000)
        st.info("+5.37% = gain, -2.12% = loss, N/A = Not available.")

    # --- Table Formatting ---
    df_display = df.copy()
    df_display["Price"] = df_display["Price"].apply(format_currency)
    df_display["Volume"] = df_display["Volume"].apply(format_volume)
    for col in ["24h Change", "7d Trend"]:
        df_display[col] = df_display[col].apply(format_percent)

    # --- Filtering ---
    filtered_df = get_df_filtered(df, category_filter, source_filter, symbol_filter, type_filter, min_volume)
    filtered_df_display = df_display.loc[filtered_df.index]

    # --- Main Token Table ---
    st.markdown("### Token Market Data")
    st.dataframe(
        filtered_df_display[["Category", "Type", "Project", "Symbol", "Price", "24h Change", "7d Trend", "Volume", "Source"]],
        use_container_width=True,
        height=500,
        hide_index=True,
        column_config={
            "Source": st.column_config.TextColumn("Data Source")
        }
    )

    # --- Cross-linked Institutional Adoption Panel ---
    st.markdown("## 🏦 Institutional Adoption Cross-Link")
    sel_symbols = filtered_df["Symbol"].unique().tolist()
    if sel_symbols:
        selected_token = st.selectbox(
            "Select a token to view institutional adoption details:",
            options=sel_symbols,
            index=0
        )
        related_institutions = institutional_df[
            institutional_df['Project/Token'].str.contains(selected_token, case=False, na=False)
        ]
        st.markdown(f"### Institutional Adoption for **{selected_token}**")
        if not related_institutions.empty:
            st.dataframe(
                related_institutions[["Institution", "Initiative", "Summary"]],
                use_container_width=True,
                hide_index=True
            )
            for _, row in related_institutions.iterrows():
                with st.expander(f"{row['Institution']} — {row['Initiative']}"):
                    st.markdown(f"**Summary:** {row['Summary']}")
        else:
            st.info("No direct institutional adoption data found for this token/project.")
    else:
        st.info("No tokens in filtered list to cross-link.")

    # --- Expandable Detail Section ---
    st.markdown("---")
    st.markdown("### Token Explanations & Charts")
    for i, row in filtered_df.iterrows():
        with st.expander(f"{row['Symbol']} ({row['Project']})"):
            st.markdown(f"**Purpose:** {row['Purpose']}")
            st.markdown(f"**Category:** {row['Category']}")
            st.markdown(f"**Type:** {row['Type']}")
            st.markdown(f"**Source:** {row['Source']}")
            if isinstance(row["Price"], str) and row["Price"] == "N/A":
                st.info("No public price feed available for this token.")
            elif isinstance(row["Hist"], pd.DataFrame):
                hist = row["Hist"]
                fig = px.line(hist, y="Close", title=f"{row['Symbol']} 7-day Price Trend (USD)")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No historical chart data available.")

    # --- Visualization ---
    st.markdown("---")
    st.subheader("Multi-Source Performance")
    tab1, tab2 = st.tabs(["Price Comparison", "Source Distribution"])
    with tab1:
        display_df = filtered_df[filtered_df["24h Change"].apply(lambda x: isinstance(x, (int, float, np.floating, np.integer)))]
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
        source_counts = filtered_df['Source'].value_counts().reset_index()
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
