import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# App configuration
st.set_page_config(page_title="Silver Watchlist", layout="wide")
st.title("Silver Watchlist Dashboard")

# Custom CSS for better styling
st.markdown("""
<style>
    .metric-card {
        padding: 10px;
        border-radius: 5px;
        background-color: #f0f2f6;
        margin-bottom: 10px;
    }
    .positive {
        color: green;
    }
    .negative {
        color: red;
    }
    .dataframe {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# Asset data - mapping to Yahoo Finance tickers
assets = [
    {"Asset": "Silver Spot", "Type": "Commodity", "Ticker": "SI=F"},  # Changed from XAGUSD=X to SI=F
    {"Asset": "Gold Spot", "Type": "Commodity", "Ticker": "XAUUSD=X"},
    {"Asset": "iShares Silver ETF", "Type": "ETF", "Ticker": "SLV"},
    {"Asset": "Sprott Physical Silver Trust", "Type": "Closed-End Fund", "Ticker": "PSLV"},
    {"Asset": "Global X Silver Miners ETF", "Type": "ETF", "Ticker": "SIL"},
    {"Asset": "Wheaton Precious Metals", "Type": "Silver Streaming Stock", "Ticker": "WPM"},
    {"Asset": "First Majestic Silver", "Type": "Silver Miner", "Ticker": "AG"},
    {"Asset": "Pan American Silver", "Type": "Silver Miner", "Ticker": "PAAS"},
    {"Asset": "Hecla Mining", "Type": "Silver Miner", "Ticker": "HL"},
    {"Asset": "Gold Miners ETF", "Type": "ETF", "Ticker": "GDX"}
]

def get_financial_data(ticker):
    today = datetime.today()
    one_year_ago = today - timedelta(days=365)
    try:
        data = yf.Ticker(ticker)
        hist = data.history(period="1y")
        if hist.empty:
            st.warning(f"No data found for ticker: {ticker}")
            return None
        live_price = hist['Close'].iloc[-1]
        high_52w = hist['Close'].max()
        low_52w = hist['Close'].min()
        # Get price from 1 year ago (approximately)
        if len(hist) > 250:  # Roughly 1 year of trading days
            price_1y_ago = hist['Close'].iloc[0]
        else:
            # If we don't have full year data, try to get more
            older_data = data.history(start=one_year_ago, end=today)
            price_1y_ago = older_data['Close'].iloc[0] if not older_data.empty else None
        if price_1y_ago:
            yoy_change = (live_price - price_1y_ago) / price_1y_ago
        else:
            yoy_change = None
        return {
            "Live Price": live_price,
            "52W High": high_52w,
            "52W Low": low_52w,
            "1Y Change (%)": yoy_change * 100 if yoy_change else None
        }
    except Exception as e:
        st.warning(f"Error fetching data for {ticker}: {e}")
        return None

def calculate_gold_silver_ratio(gold_price, silver_price):
    if not silver_price or silver_price == 0:
        return None
    return gold_price / silver_price

def process_data():
    df = pd.DataFrame(assets)
    financial_data = []
    # Get data for all assets
    for asset in assets:
        data = get_financial_data(asset["Ticker"])
        if data:
            financial_data.append(data)
        else:
            # Add empty data if fetch fails
            financial_data.append({
                "Live Price": None,
                "52W High": None,
                "52W Low": None,
                "1Y Change (%)": None
            })
    financial_df = pd.DataFrame(financial_data)
    result_df = pd.concat([df, financial_df], axis=1)
    # Calculate gold/silver ratio if both are available
    gold_price = result_df[result_df["Asset"] == "Gold Spot"]["Live Price"].values[0]
    silver_price = result_df[result_df["Asset"] == "Silver Spot"]["Live Price"].values[0]
    if gold_price and silver_price:
        gs_ratio = calculate_gold_silver_ratio(gold_price, silver_price)
        result_df["Gold/Silver Ratio"] = None
        result_df.loc[result_df["Asset"] == "Silver Spot", "Gold/Silver Ratio"] = gs_ratio
    else:
        result_df["Gold/Silver Ratio"] = None
    return result_df

# Display the data
data = process_data()

# Display key metrics at the top
col1, col2, col3, col4 = st.columns(4)

try:
    silver_price = data[data["Asset"] == "Silver Spot"]["Live Price"].values[0]
    gold_price = data[data["Asset"] == "Gold Spot"]["Live Price"].values[0]
    gs_ratio = calculate_gold_silver_ratio(gold_price, silver_price) if gold_price and silver_price else None

    with col1:
        st.metric("Silver Price", f"${silver_price:.2f}" if silver_price else "N/A")
    with col2:
        st.metric("Gold Price", f"${gold_price:.2f}" if gold_price else "N/A")
    with col3:
        st.metric("Gold/Silver Ratio", f"{gs_ratio:.2f}" if gs_ratio else "N/A")
    with col4:
        if gs_ratio:
            if gs_ratio > 80:
                ratio_status = "High (Silver Undervalued)"
                color = "green"
            elif gs_ratio < 60:
                ratio_status = "Low (Gold Undervalued)"
                color = "red"
            else:
                ratio_status = "Normal Range"
                color = "black"
            st.markdown(f'<div class="metric-card">Ratio Status: <span style="color:{color}">{ratio_status}</span></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="metric-card">Ratio Status: N/A</div>', unsafe_allow_html=True)
except Exception as e:
    st.error(f"Error displaying metrics: {e}")

# Display the main dataframe
st.subheader("Silver Investment Watchlist")

# Format the dataframe for display
display_df = data.copy()
display_df["1Y Change (%)"] = display_df["1Y Change (%)"].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) else "N/A")
display_df["Live Price"] = display_df["Live Price"].apply(lambda x: f"${x:.2f}" if pd.notnull(x) else "N/A")
display_df["52W High"] = display_df["52W High"].apply(lambda x: f"${x:.2f}" if pd.notnull(x) else "N/A")
display_df["52W Low"] = display_df["52W Low"].apply(lambda x: f"${x:.2f}" if pd.notnull(x) else "N/A")
display_df["Gold/Silver Ratio"] = display_df["Gold/Silver Ratio"].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "N/A")

# Reorder columns to match Excel
display_df = display_df[["Asset", "Type", "Ticker", "Live Price", "52W High", "52W Low", "1Y Change (%)", "Gold/Silver Ratio"]]

# Display the dataframe with styling
st.dataframe(
    display_df.style.applymap(
        lambda x: 'color: green' if isinstance(x, str) and x.endswith('%') and float(x[:-1]) > 0 
        else ('color: red' if isinstance(x, str) and x.endswith('%') and float(x[:-1]) < 0 else ''),
        subset=["1Y Change (%)"]
    ),
    height=(len(data) + 1) * 35 + 3,
    use_container_width=True
)

# Insights section
st.subheader("Investment Insights")
st.markdown("""
**Insight 1 (Sound):**  
The gold/silver ratio near 100 is well above its long-term average (~70–80), signaling silver is relatively undervalued versus gold. 
A tilt toward physical silver or low-fee silver ETFs (e.g. SLV, PSLV) when the ratio exceeds 100 can capture mean-reversion.

**Insight 2 (Contra-intuitive):**  
Rather than boosting pure silver exposure, overweighting high-quality silver miners (e.g. WPM, SIL) could actually deliver better leveraged returns—miners often outperform the metal during rallies.
""")

# Add a refresh button
if st.button("Refresh Data"):
    st.rerun()  # Updated for modern Streamlit

# Add some explanation
st.markdown("""
*Note: Data is fetched from Yahoo Finance. The app updates when you click the Refresh Data button or when the page is reloaded.*
""")
