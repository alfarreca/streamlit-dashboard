import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import yfinance as yf
from fredapi import Fred

# -- Auto-Refresh (every 5 min)
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=5 * 60 * 1000, key="data_refresh")
except ImportError:
    pass  # Safe fallback if package not installed

# -- FRED API Key
FRED_API_KEY = "a79018b53e3085363528cf148b358708"
fred = Fred(api_key=FRED_API_KEY)

# -- Real-time Yahoo Finance Tickers
def fetch_yahoo_price(ticker, fallback=None):
    try:
        return yf.Ticker(ticker).info["regularMarketPrice"]
    except Exception:
        return fallback

# -- Real-time FRED series (returns latest value)
def fetch_fred_series(series_id, fallback=None):
    try:
        data = fred.get_series_latest_release(series_id)
        return float(data[-1])
    except Exception:
        return fallback

# App Config
st.set_page_config(page_title="Gundlach Macro Dashboard", layout="wide")

# Title
st.title("💰 Jeffrey Gundlach's Market Outlook")
st.subheader("Key insights from DoubleLine Capital CEO")

# Sidebar Filters
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

# ----- Real-time Market Data (All Tabs Can Use These)
gold_price = fetch_yahoo_price("GC=F", fallback=2350)
btc_price = fetch_yahoo_price("BTC-USD", fallback=67000)
dxy_index = fetch_yahoo_price("DX-Y.NYB", fallback=104.2)
treasury_10y = fetch_fred_series("GS10", fallback=4.1)  # 10Y Treasury yield

# Main Content - Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📉 U.S. Fiscal Crisis", 
    "🛡️ Safe Havens", 
    "⚠️ Credit Risks", 
    "🌍 Global Opportunities"
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
        
        # -- Real-time chart for 10Y Yield (last 10 years)
        try:
            df_yield = fred.get_series('GS10', observation_start='2015-01-01')
            df_yield = df_yield.reset_index()
            df_yield.columns = ['Year', '10Y Yield']
            fig = px.line(df_yield, x="Year", y="10Y Yield",
                          title="10-Year Treasury Yield (FRED Real-Time)", markers=True)
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            # fallback: static sample
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
        - **10Y Treasury Yield (Real-Time): {treasury_10y:.2f}%**
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
        st.image("https://i.imgur.com/Jc0lRxX.png", caption="Central bank gold purchases")
    
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
        # Optionally add performance bars if you wish
        # st.progress(60)
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
    # Keeping static for now—can add FRED credit spreads if desired
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
            column_config={
                "GDP Growth (2024E)": st.column_config.ProgressColumn(
                    format="%.1f%%",
                    min_value=0,
                    max_value=10
                )
            },
            hide_index=True
        )

# Footer
st.markdown("---")
st.caption("""
**Data Sources:** DoubleLine Capital, Bloomberg, FRED, Yahoo Finance  
**Disclaimer:** Not investment advice. For informational purposes only.
""")
