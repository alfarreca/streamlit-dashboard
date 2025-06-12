import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

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
        st.write("""
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
        st.metric("Gold Price", "$2,350", "+18% YTD")
        st.image("https://i.imgur.com/Jc0lRxX.png", caption="Central bank gold purchases")
    
    with col2:
        st.metric("DXY Index", "104.2", "-3% from peak")
        st.write("""
        **Dollar weakness expected due to:**
        - Fiscal concerns
        - Foreign capital outflows
        - EM alternatives
        """)
    
    with col3:
        st.metric("Bitcoin vs Gold", "BTC +45%", "GLD +40%")
        st.progress(60)
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
**Data Sources:** DoubleLine Capital, Bloomberg, FRED  
**Disclaimer:** Not investment advice. For informational purposes only.
""")