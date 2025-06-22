import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import yfinance as yf

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
        "Upload XLSX file from World Gold Council or IMF (IFS)",
        type=["xlsx"]
    )

    if uploaded_file:
        try:
            # Set correct header row (Excel row 6 → pandas header=5)
            df = pd.read_excel(uploaded_file, header=5)
            df = df.dropna(axis=0, how='all').dropna(axis=1, how='all')

            # Split into left and right halves, rename columns
            left_cols = df.columns[:5]
            right_cols = df.columns[5:]
            df_left = df[left_cols].copy()
            df_right = df[right_cols].copy()

            df_left.columns = ["Rank", "Country", "Tonnes", "% of reserves", "Holdings as of"]
            df_right.columns = ["Rank", "Country", "Tonnes", "% of reserves", "Holdings as of"]

            # Drop rows with missing country names
            df_left = df_left.dropna(subset=["Country"])
            df_right = df_right.dropna(subset=["Country"])

            # Combine both sides into one, convert Tonnes to numeric for sorting
            df_all = pd.concat([df_left, df_right], ignore_index=True)
            df_all["Tonnes"] = pd.to_numeric(df_all["Tonnes"], errors='coerce')
            df_all = df_all.dropna(subset=["Tonnes"]).sort_values("Tonnes", ascending=False)

            st.success("File uploaded and parsed successfully!")
            st.dataframe(df_all, use_container_width=True)

            st.subheader("Top 10 Countries by Gold Holdings")
            st.dataframe(df_all[["Country", "Tonnes"]].head(10), use_container_width=True)
            st.bar_chart(df_all.set_index("Country")["Tonnes"].head(10))

            st.subheader("Gold as % of Reserves")
            st.dataframe(df_all[["Country", "% of reserves"]].head(10), use_container_width=True)

        except Exception as e:
            st.error(f"Error reading or parsing file: {e}")
    else:
        st.info("Please upload a gold statistics XLSX file to see central bank holdings and purchases.")

# ---- Footer ----
st.markdown("---")
st.caption("""
**Data Sources:** DoubleLine Capital, Bloomberg, Yahoo Finance, World Gold Council, IMF  
**Disclaimer:** Not investment advice. For informational purposes only.
""")
