import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# App configuration
st.set_page_config(
    page_title="App-Layer Investment Tracker",
    layout="wide",
    page_icon="📊"
)

# Data
companies_data = {
    "Company": ["Coinbase", "Robinhood", "Block (Square)", "Galaxy Digital", "SoFi"],
    "Ticker": ["COIN", "HOOD", "SQ", "BRPHF", "SOFI"],
    "Market": ["NASDAQ", "NASDAQ", "NYSE", "OTC", "NASDAQ"],
    "App Layer Focus": [
        "Wallet, on/off ramp, DeFi access",
        "User brokerage/super-app",
        "Crypto + fiat payment super-app",
        "Asset mgmt, DeFi, app integration",
        "Super-app for banking + crypto"
    ]
}

tokens_data = {
    "Token": ["UNI", "AAVE", "YFI", "1INCH", "LDO", "SAFE"],
    "Focus": [
        "Decentralized exchange protocol",
        "Decentralized lending platform",
        "Yearn.finance yield aggregator",
        "DEX aggregator with best price routing",
        "Liquid staking for Ethereum",
        "Smart contract account standard"
    ],
    "Network Effects": ["Strong", "Strong", "Moderate", "Strong", "Growing", "Emerging"],
    "User Fees": ["Yes", "Yes", "Yes", "Yes", "Yes", "No"],
    "Composability": ["High", "High", "High", "High", "Medium", "High"]
}

# Create DataFrames
companies_df = pd.DataFrame(companies_data)
tokens_df = pd.DataFrame(tokens_data)

# Sidebar
st.sidebar.title("Filters")
selected_companies = st.sidebar.multiselect(
    "Select Companies to Display",
    companies_df["Company"],
    default=companies_df["Company"]
)

selected_tokens = st.sidebar.multiselect(
    "Select Tokens to Display",
    tokens_df["Token"],
    default=tokens_df["Token"]
)

show_price_data = st.sidebar.checkbox("Show Price Data", value=True)
price_days = st.sidebar.slider("Price History Days", 1, 365, 30)

# Main content
st.title("📊 App-Layer Investment Tracker")
st.subheader("Publicly Traded Companies with App-Layer Focus")

# Display companies table
filtered_companies = companies_df[companies_df["Company"].isin(selected_companies)]
st.dataframe(
    filtered_companies,
    use_container_width=True,
    hide_index=True
)

# Price data for companies
if show_price_data and not filtered_companies.empty:
    st.subheader("Company Price Data")
    
    # Get price data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=price_days)
    
    tickers = " ".join(filtered_companies["Ticker"].tolist())
    
    try:
        price_data = yf.download(
            tickers,
            start=start_date.strftime('%Y-%m-%d'),
            end=end_date.strftime('%Y-%m-%d'),
            group_by='ticker'
        )
        
        if not price_data.empty:
            # Display closing prices
            closing_prices = pd.DataFrame()
            for ticker in filtered_companies["Ticker"]:
                if ticker in price_data:
                    closing_prices[ticker] = price_data[ticker]["Close"]
            
            st.line_chart(closing_prices)
            
            # Display recent price changes
            st.write("Recent Price Changes:")
            price_changes = []
            for ticker in filtered_companies["Ticker"]:
                if ticker in price_data:
                    first_close = price_data[ticker]["Close"].iloc[0]
                    last_close = price_data[ticker]["Close"].iloc[-1]
                    change = ((last_close - first_close) / first_close) * 100
                    price_changes.append({
                        "Ticker": ticker,
                        "First Close": f"${first_close:.2f}",
                        "Last Close": f"${last_close:.2f}",
                        "Change (%)": f"{change:.2f}%",
                        "Direction": "Up" if change >= 0 else "Down"
                    })
            
            st.table(pd.DataFrame(price_changes))
        else:
            st.warning("No price data available for the selected companies.")
    except Exception as e:
        st.error(f"Error fetching price data: {e}")

# Token information
st.subheader("Tokens with Strong App-Layer Network Effects")
filtered_tokens = tokens_df[tokens_df["Token"].isin(selected_tokens)]
st.dataframe(
    filtered_tokens,
    use_container_width=True,
    hide_index=True
)

# Additional information
st.subheader("Investment Considerations")
st.markdown("""
**For Token Investors:**
- Focus on tokens with strong app-layer network effects
- Look for protocols generating real user fees
- Consider composability (ability to integrate with other protocols)
- Evaluate adoption metrics beyond just token price

**Key Metrics to Watch:**
- Daily Active Users (DAU)
- Transaction volume
- Protocol revenue
- TVL (Total Value Locked) for DeFi protocols
- Integration with major wallets and apps
""")

# Footer
st.markdown("---")
st.markdown("""
**Data Sources:**
- Company data from public filings
- Token data from on-chain analytics
- Price data from Yahoo Finance
""")
