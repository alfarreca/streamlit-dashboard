import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta
from st_aggrid import AgGrid, GridOptionsBuilder
import requests
from PIL import Image
import io
import base64

# App configuration
st.set_page_config(
    page_title="App-Layer Investment Dashboard",
    layout="wide",
    page_icon="📈",
    initial_sidebar_state="expanded"
)

# Optionally keep background color CSS, but all dashboard text is HTML-free
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def load_company_data():
    return pd.DataFrame({
        "Company": ["Coinbase", "Robinhood", "Block (Square)", "Galaxy Digital", "SoFi"],
        "Ticker": ["COIN", "HOOD", "SQ", "BRPHF", "SOFI"],
        "Market": ["NASDAQ", "NASDAQ", "NYSE", "OTC", "NASDAQ"],
        "Sector": ["Exchange", "Brokerage", "Payments", "Asset Management", "Fintech"],
        "App Layer Focus": [
            "Wallet, on/off ramp, DeFi access",
            "User brokerage/super-app",
            "Crypto + fiat payment super-app",
            "Asset mgmt, DeFi, app integration",
            "Super-app for banking + crypto"
        ],
        "Market Cap (B)": [50.2, 12.8, 45.3, 1.8, 7.5]
    })

@st.cache_data(ttl=3600)
def load_token_data():
    return pd.DataFrame({
        "Token": ["UNI", "AAVE", "YFI", "1INCH", "LDO", "SAFE"],
        "Name": ["Uniswap", "Aave", "Yearn Finance", "1inch", "Lido DAO", "Safe"],
        "Focus": [
            "Decentralized exchange protocol",
            "Decentralized lending platform",
            "Yield aggregator",
            "DEX aggregator",
            "Liquid staking",
            "Smart contract accounts"
        ],
        "Market Cap (B)": [4.2, 1.8, 0.3, 0.5, 2.1, 1.2],
        "Network Effects": ["Strong", "Strong", "Moderate", "Strong", "Growing", "Emerging"],
        "User Fees": ["Yes", "Yes", "Yes", "Yes", "Yes", "No"],
        "Composability": ["High", "High", "High", "High", "Medium", "High"],
        "TVL (B)": [3.5, 6.2, 0.8, 0.3, 20.1, 0.5]
    })

@st.cache_data(ttl=3600)
def fetch_price_data(tickers, days=30):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    try:
        data = yf.download(
            " ".join(tickers),
            start=start_date.strftime('%Y-%m-%d'),
            end=end_date.strftime('%Y-%m-%d'),
            group_by='ticker'
        )
        return data
    except Exception as e:
        st.error(f"Error fetching price data: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_token_logo(token_symbol):
    try:
        url = f"https://cryptoicons.org/api/icon/{token_symbol.lower()}/200"
        response = requests.get(url)
        return Image.open(io.BytesIO(response.content))
    except:
        return None

def logo_to_base64(image):
    if image:
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()
    return ""

# Load data
companies_df = load_company_data()
tokens_df = load_token_data()

# Sidebar - Filters
st.sidebar.header("Filters & Controls")

analysis_period = st.sidebar.selectbox(
    "Analysis Period",
    options=["1M", "3M", "6M", "1Y", "YTD"],
    index=1
)

days_mapping = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365, "YTD": (datetime.now() - datetime(datetime.now().year, 1, 1)).days}
selected_days = days_mapping[analysis_period]

selected_sectors = st.sidebar.multiselect(
    "Filter by Sector",
    options=companies_df["Sector"].unique(),
    default=companies_df["Sector"].unique()
)

selected_companies = st.sidebar.multiselect(
    "Select Companies",
    options=companies_df["Company"],
    default=companies_df["Company"]
)

selected_tokens = st.sidebar.multiselect(
    "Select Tokens",
    options=tokens_df["Token"],
    default=tokens_df["Token"]
)

# Main content
st.title("🚀 App-Layer Investment Dashboard")
st.markdown("Track publicly traded companies and tokens with strong app-layer network effects")

# Metrics row (HTML-free)
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Companies Tracked", len(selected_companies))
with col2:
    st.metric("Tokens Tracked", len(selected_tokens))
with col3:
    total_mcap = companies_df[companies_df["Company"].isin(selected_companies)]["Market Cap (B)"].sum() + \
                tokens_df[tokens_df["Token"].isin(selected_tokens)]["Market Cap (B)"].sum()
    st.metric("Total Market Cap", f"${total_mcap:.1f}B")

# Companies Section
st.header("Public Companies Analysis")
filtered_companies = companies_df[
    (companies_df["Company"].isin(selected_companies)) & 
    (companies_df["Sector"].isin(selected_sectors))
]

if not filtered_companies.empty:
    gb = GridOptionsBuilder.from_dataframe(filtered_companies)
    gb.configure_pagination(paginationAutoPageSize=True)
    gb.configure_side_bar()
    gb.configure_default_column(groupable=True, value=True, enableRowGroup=True, aggFunc="sum", editable=False)
    grid_options = gb.build()
    AgGrid(
        filtered_companies,
        gridOptions=grid_options,
        enable_enterprise_modules=True,
        height=400,
        width="100%",
        theme="streamlit"
    )
    st.subheader("Price Performance")
    price_data = fetch_price_data(filtered_companies["Ticker"].tolist(), selected_days)
    if not price_data.empty:
        tab1, tab2 = st.tabs(["Individual Performance", "Comparative Analysis"])
        with tab1:
            cols = st.columns(2)
            for i, (_, row) in enumerate(filtered_companies.iterrows()):
                with cols[i % 2]:
                    if row["Ticker"] in price_data:
                        df = price_data[row["Ticker"]]
                        fig = px.line(
                            df, 
                            x=df.index, 
                            y="Close",
                            title=f"{row['Company']} ({row['Ticker']})",
                            labels={"Close": "Price (USD)"}
                        )
                        fig.update_layout(
                            hovermode="x unified",
                            showlegend=False,
                            margin=dict(l=20, r=20, t=40, b=20)
                        )
                        st.plotly_chart(fig, use_container_width=True)
        with tab2:
            closing_prices = pd.DataFrame()
            for ticker in filtered_companies["Ticker"]:
                if ticker in price_data:
                    closing_prices[ticker] = price_data[ticker]["Close"]
            norm_prices = closing_prices.apply(lambda x: x / x.iloc[0] * 100)
            fig = px.line(
                norm_prices,
                title="Normalized Price Comparison (Base 100)",
                labels={"value": "Price Change (%)", "variable": "Ticker"}
            )
            fig.update_layout(
                hovermode="x unified",
                legend_title="Ticker",
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)
            st.subheader("Performance Metrics")
            metrics = []
            for ticker in filtered_companies["Ticker"]:
                if ticker in price_data:
                    df = price_data[ticker]
                    first = df["Close"].iloc[0]
                    last = df["Close"].iloc[-1]
                    change = (last - first) / first * 100
                    high = df["Close"].max()
                    low = df["Close"].min()
                    vol = df["Volume"].mean()
                    metrics.append({
                        "Ticker": ticker,
                        "Start Price": f"${first:.2f}",
                        "End Price": f"${last:.2f}",
                        "Change": f"{change:.2f}%",
                        "High": f"${high:.2f}",
                        "Low": f"${low:.2f}",
                        "Avg Vol": f"{vol:,.0f}"
                    })
            st.dataframe(pd.DataFrame(metrics), hide_index=True)
else:
    st.warning("No companies match your selected filters.")

# Tokens Section (HTML-free token cards)
st.header("Token Analysis")
filtered_tokens = tokens_df[tokens_df["Token"].isin(selected_tokens)]

if not filtered_tokens.empty:
    cols = st.columns(3)
    for i, (_, row) in enumerate(filtered_tokens.iterrows()):
        with cols[i % 3]:
            logo = fetch_token_logo(row["Token"])
            if logo:
                st.image(logo, width=40)
            st.write(f"**{row['Name']} ({row['Token']})**")
            st.write(f"Market Cap: ${row['Market Cap (B)']:.2f}B")
            st.write(f"Focus: {row['Focus']}")
            st.write(f"TVL: ${row['TVL (B)']:.1f}B")
            st.write(f"Composability: {row['Composability']}")
            st.markdown("---")
    st.subheader("Token Metrics Comparison")
    st.dataframe(
        filtered_tokens.drop(columns=["Focus"]),
        use_container_width=True,
        hide_index=True
    )
else:
    st.warning("No tokens match your selected filters.")

# Research Section
st.header("Research & Insights")
with st.expander("Investment Thesis"):
    st.markdown("""
### App-Layer Investment Thesis

The app layer represents the user-facing gateways to blockchain and DeFi. Companies and tokens with strong network effects, user bases, and deep composability are positioned for long-term value accrual.

**Key Aspects:**

- **User Adoption:** Preference for platforms with real, sustainable user growth and retention.
- **Network Effects:** Emphasize protocols and companies that benefit from increasing returns as their user base grows.
- **Composability:** Select assets that can be combined with, or built upon by, other applications, multiplying their utility and stickiness.
- **Revenue & Fees:** Focus on those generating consistent user fees and demonstrating economic sustainability.
- **Ecosystem Role:** Invest in platforms that act as primary access points or aggregation layers for DeFi and crypto adoption.
- **Tokenomics:** Prefer clear, sustainable value accrual mechanisms for token holders and transparent governance.

_App-layer investments are often higher risk, but can offer outsized returns as crypto adoption grows and new use-cases emerge._

---
_Last updated: June 2025_
    """)
