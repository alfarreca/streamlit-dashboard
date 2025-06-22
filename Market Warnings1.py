import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import yfinance as yf
# from fredapi import Fred  # Remove if not installed

# -- Optional: Real-time Data Functions
def fetch_yahoo_price(ticker, fallback=None):
    try:
        return yf.Ticker(ticker).info["regularMarketPrice"]
    except Exception:
        return fallback

# -- Real-time Yahoo Finance
gold_price = fetch_yahoo_price("GC=F", fallback=2350)
btc_price = fetch_yahoo_price("BTC-USD", fallback=67000)
dxy_index = fetch_yahoo_price("DX-Y.NYB", fallback=104.2)

# App Config
st.set_page_config(page_title="Gundlach Macro Dashboard", layout="wide")

st.title("💰 Jeffrey Gundlach's Market Outlook")
st.subheader("Key insights from DoubleLine Capital CEO")

with st.sidebar:
    st.header("User Settings")
    risk_profile = st.selectbox(
        "Your Risk Profile",
        ["Conservative", "Moderate", "Aggressive"]
    )
    update_frequency = st.radio(
        "Data Refresh",
        ["Daily", "Weekly", "Monthly"]
    )
    st.markdown("---")
    st.caption("Last updated: " + datetime.now().strftime("%Y-%m-%d %H:%M"))

# ----- Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📉 U.S. Fiscal Crisis", 
    "🛡️ Safe Havens", 
    "⚠️ Credit Risks", 
    "🌍 Global Opportunities",
    "🏦 Central Bank Gold"
])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🚨 Unsustainable Debt Trajectory")
        st.write("""
        - **$37T+ national debt** with rising interest costs
        - Average Treasury coupon jumped from ~2% to ~4%
        - Long-term Treasuries no longer behave as safe havens
        """)
        debt_data = pd.DataFrame({
            "Year": [2010, 2015, 2020, 2024],
            "Debt ($T)": [13.5, 18.1, 26.9, 36.9],
            "Avg Yield": [1.8, 1.5, 1.9, 4.1]
        })
        fig = px.line(
            debt_data, 
            x="Year", 
            y=["Debt ($T)", "Avg Yield"],
            title="U.S. Debt & Treasury Yields",
            markers=True
        )
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("### 📈 Market Signals")
        st.write(f"""
        - When S&P drops >10%, dollar usually rises (but fell in 2022)
        - Yield curve steepening despite Fed cuts
        - Inflation likely to reaccelerate
        """)
        signal_data = pd.DataFrame({
            "Event": ["S&P Drop >10%", "First Fed Cut", "CPI Spike"],
            "Normal Reaction": ["Dollar ↑", "Yields ↓", "Gold ↑"],
            "2023-24 Reaction": ["Dollar ↓", "Yields ↑", "Gold ↑↑"]
        })
        st.dataframe(
            signal_data,
            hide_index=True,
            use_container_width=True
        )
        st.slider(
            "When will 10Y yield hit 6%?",
            min_value=2024,
            max_value=2026,
            value=2025
        )

with tab2:
    st.markdown("### 🥇 The New Safe Havens")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Gold Price", f"${gold_price:,.0f}")
        st.caption("Central bank gold purchases (see '🏦 Central Bank Gold' tab)")
    with col2:
        st.metric("DXY Index", f"{dxy_index:.2f}")
        st.write("""
        **Dollar weakness expected due to:**
        - Fiscal concerns
        - Foreign capital outflows
        - EM alternatives
        """)
    with col3:
        st.metric("Bitcoin Price", f"${btc_price:,.0f}")
        st.caption("Gundlach prefers 2x leveraged gold over BTC")

with tab3:
    st.markdown("### 🔍 Credit Market Red Flags")
    st.write("""
    **Corporate Debt:**  
    - High-yield allocations at historic lows  
    - Spreads too tight for risk  
    
    **Private Credit Bubble:**  
    - Echoes 2006-07 CDO market  
    - Harvard endowment liquidity issues  
    - Retail overexposure  
    """)
    risk_chart = pd.DataFrame({
        "Year": [2019, 2020, 2021, 2022, 2023, 2024],
        "HY Spreads (bps)": [350, 480, 310, 470, 390, 310],
        "Private Credit AUM ($B)": [800, 950, 1200, 1400, 1700, 2100]
    })
    fig = px.area(
        risk_chart,
        x="Year",
        y=["HY Spreads (bps)", "Private Credit AUM ($B)"],
        title="Credit Market Indicators"
    )
    st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.markdown("### 🌏 International Opportunities")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Top Picks:**")
        st.checkbox("🇮🇳 India (demographic dividend)", True)
        st.checkbox("🇪🇺 European value stocks", True)
        st.checkbox("EM ex-China equities", True)
        st.checkbox("Non-USD currencies", True)
    with col2:
        country_data = pd.DataFrame({
            "Country": ["India", "Japan", "Germany", "Brazil"],
            "GDP Growth (2024E)": [6.5, 1.2, 0.8, 2.1],
            "PE Ratio": [22, 15, 12, 8]
        })
        st.dataframe(
            country_data,
            hide_index=True
        )

# -------------- NEW TAB: CENTRAL BANK GOLD XLSX UPLOAD -------------
with tab5:
    st.header("📤 Central Bank Gold Holdings & Purchases Upload")

    uploaded_file = st.file_uploader(
        "Upload XLSX file from World Gold Council or other source",
        type=["xlsx"]
    )

    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            st.success("File uploaded successfully!")
            st.dataframe(df, use_container_width=True)

            # Example: Extract top 10 countries by latest gold holdings if columns match
            if "Latest Holdings (tonnes)" in df.columns:
                st.subheader("Top 10 Countries by Latest Holdings")
                st.dataframe(df[["Country", "Latest Holdings (tonnes)"]].sort_values(
                    "Latest Holdings (tonnes)", ascending=False).head(10),
                    use_container_width=True
                )

            # Purchases/Changes if available
            purchase_columns = [c for c in df.columns if "change" in c.lower() or "purchase" in c.lower()]
            if purchase_columns:
                st.subheader("Gold Purchases/Changes")
                st.dataframe(df[["Country"] + purchase_columns], use_container_width=True)

            # Example: Bar chart for latest holdings
            if "Latest Holdings (tonnes)" in df.columns:
                st.bar_chart(df.set_index("Country")["Latest Holdings (tonnes)"].sort_values(ascending=False).head(10))
        except Exception as e:
            st.error(f"Error reading file: {e}")
    else:
        st.info("Please upload a gold statistics XLSX file to see central bank holdings and purchases.")

# ---- Footer ----
st.markdown("---")
st.caption("""
**Data Sources:** DoubleLine Capital, Bloomberg, Yahoo Finance, World Gold Council  
**Disclaimer:** Not investment advice. For informational purposes only.
""")
