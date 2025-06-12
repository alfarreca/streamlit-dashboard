import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# Configure page
st.set_page_config(
    page_title="Market Warnings Dashboard",
    page_icon="📊",
    layout="wide"
)

# Add title and description
st.title("📈 ETF Recommendations Based on Jeffrey Gundlach's Themes")
st.markdown("""
This dashboard provides investment recommendations aligned with Jeffrey Gundlach's market outlook,
including gold, emerging markets, and sector-specific ETFs.
""")

# Add divider
st.divider()

# ETF data based on Gundlach's themes
etf_data = {
    "Theme": [
        "Gold (Core Hedge)",
        "Gold (Core Hedge)",
        "Gold Miners (Leveraged Real Asset Exposure)",
        "Gold Miners (Leveraged Real Asset Exposure)",
        "Gold Miners (Leveraged Real Asset Exposure)",
        "India Equity Exposure",
        "India Equity Exposure",
        "India Equity Exposure",
        "India Equity Exposure",
        "Emerging Markets (Currency-Hedged)",
        "Broader EM Equity (Unhedged)"
    ],
    "Ticker": [
        "GLD", "IAU", "GDX", "RING", "GDXJ", 
        "INDA", "EPI", "SMIN", "INDY", "HEEM", "VWO"
    ],
    "Name": [
        "SPDR Gold Shares",
        "iShares Gold Trust",
        "VanEck Gold Miners ETF",
        "iShares MSCI Global Gold Miners ETF",
        "VanEck Junior Gold Miners ETF",
        "iShares MSCI India ETF",
        "WisdomTree India Earnings Fund",
        "iShares MSCI India Small-Cap ETF",
        "iShares India 50 ETF",
        "iShares Currency Hedged MSCI Emerging Markets ETF",
        "Vanguard FTSE Emerging Markets ETF"
    ],
    "Expense Ratio": [
        0.40, 0.25, 0.51, 0.39, 0.52,
        0.62, 0.85, 0.74, 0.94, 0.61, 0.08
    ]
}

# Create DataFrame
etf_df = pd.DataFrame(etf_data)

# Add performance data
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_performance_data(tickers):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    performance = {}
    
    for ticker in tickers:
        try:
            data = yf.download(ticker, start=start_date, end=end_date)
            if not data.empty:
                perf = (data['Close'][-1] / data['Close'][0] - 1) * 100
                performance[ticker] = round(perf, 2)
        except:
            performance[ticker] = "N/A"
    
    return performance

performance_data = get_performance_data(etf_df['Ticker'].tolist())
etf_df['1Y Performance (%)'] = etf_df['Ticker'].map(performance_data)

# Display ETF table
st.header("Recommended ETFs")
st.dataframe(
    etf_df,
    column_config={
        "Ticker": st.column_config.TextColumn("Ticker", width="small"),
        "Name": st.column_config.TextColumn("ETF Name"),
        "Expense Ratio": st.column_config.NumberColumn(
            "Expense Ratio (%)",
            format="%.2f",
            help="Annual management fee"
        ),
        "1Y Performance (%)": st.column_config.NumberColumn(
            "1Y Performance",
            format="%.2f%%",
            help="1-year price return"
        )
    },
    hide_index=True,
    use_container_width=True
)

# Portfolio allocation section
st.header("Suggested Portfolio Allocation")
portfolio_allocation = {
    "Core Allocation (50-60%)": ["GLD/IAU (20-25%)", "INDA/VWO (20-25%)", "HEEM (10%)"],
    "Satellite Allocation (30-40%)": ["GDX/RING (10-15%)", "SMIN (10%)", "GDXJ (5-10%)"],
    "Opportunistic (10%)": ["EPI/INDY (5%)", "Other tactical positions (5%)"]
}

for category, allocations in portfolio_allocation.items():
    with st.expander(category):
        for alloc in allocations:
            st.write(f"- {alloc}")

# Investment rationale
st.header("Investment Rationale")
st.markdown("""
1. **Gold & miners** align with Gundlach's view of gold as the new flight-to-quality asset
2. **India/EM equities** tap into secular growth and dollar weakness tailwinds
3. **Currency-hedged EM (HEEM)** cushions against FX volatility
4. **Satellite positions** provide higher growth potential while core maintains stability
""")

# Performance charts
st.header("ETF Performance")
selected_tickers = st.multiselect(
    "Select ETFs to compare performance",
    options=etf_df['Ticker'].unique(),
    default=["GLD", "GDX", "INDA", "VWO"]
)

if selected_tickers:
    @st.cache_data
    def get_historical_data(tickers):
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        data = yf.download(tickers, start=start_date, end=end_date)['Close']
        return data.pct_change().cumsum() * 100
    
    performance_chart = get_historical_data(selected_tickers)
    st.line_chart(performance_chart)

# Notes and disclaimer
st.divider()
st.caption("""
**Note:** Review each ETF's expense ratio, liquidity, and how it fits your risk profile. 
Consider periodic rebalancing to maintain target allocations. Past performance is not indicative of future results.
""")
