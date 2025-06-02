import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import math
import numpy as np

# App configuration
st.set_page_config(page_title="Silver Momentum Scanner", layout="wide")
st.title("Silver Momentum Scanner Dashboard")

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
        font-weight: bold;
    }
    .negative {
        color: red;
        font-weight: bold;
    }
    .neutral {
        color: orange;
        font-weight: bold;
    }
    .dataframe {
        width: 100%;
    }
    .header {
        font-size: 1.5em;
        color: #2c3e50;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Asset data - mapping to Yahoo Finance tickers
assets = [
    {"Asset": "Silver Spot", "Type": "Commodity", "Ticker": "SI=F"},   # Silver Futures
    {"Asset": "Gold Spot", "Type": "Commodity", "Ticker": "GC=F"},     # Gold Futures
    {"Asset": "iShares Silver ETF", "Type": "ETF", "Ticker": "SLV"},
    {"Asset": "Sprott Physical Silver Trust", "Type": "Closed-End Fund", "Ticker": "PSLV"},
    {"Asset": "Global X Silver Miners ETF", "Type": "ETF", "Ticker": "SIL"},
    {"Asset": "Wheaton Precious Metals", "Type": "Silver Streaming Stock", "Ticker": "WPM"},
    {"Asset": "First Majestic Silver", "Type": "Silver Miner", "Ticker": "AG"},
    {"Asset": "Pan American Silver", "Type": "Silver Miner", "Ticker": "PAAS"},
    {"Asset": "Hecla Mining", "Type": "Silver Miner", "Ticker": "HL"},
    {"Asset": "Gold Miners ETF", "Type": "ETF", "Ticker": "GDX"}
]

def get_momentum_data(ticker):
    today = datetime.today()
    try:
        data = yf.Ticker(ticker)
        
        # Get historical data for different time periods
        hist_1y = data.history(period="1y")
        hist_6m = data.history(period="6mo")
        hist_3m = data.history(period="3mo")
        hist_1m = data.history(period="1mo")
        
        if hist_1y.empty:
            st.warning(f"No data found for ticker: {ticker}")
            return None
            
        live_price = hist_1y['Close'].iloc[-1]
        
        # Calculate returns for different periods
        returns = {
            "1D": (live_price / hist_1y['Close'].iloc[-2] - 1) * 100 if len(hist_1y) > 1 else None,
            "1W": (live_price / hist_1y['Close'].iloc[-5] - 1) * 100 if len(hist_1y) > 5 else None,
            "1M": (live_price / hist_1m['Close'].iloc[0] - 1) * 100 if not hist_1m.empty else None,
            "3M": (live_price / hist_3m['Close'].iloc[0] - 1) * 100 if not hist_3m.empty else None,
            "6M": (live_price / hist_6m['Close'].iloc[0] - 1) * 100 if not hist_6m.empty else None,
            "1Y": (live_price / hist_1y['Close'].iloc[0] - 1) * 100 if not hist_1y.empty else None
        }
        
        # Calculate moving averages
        ma_20 = hist_1y['Close'].rolling(20).mean().iloc[-1]
        ma_50 = hist_1y['Close'].rolling(50).mean().iloc[-1]
        ma_200 = hist_1y['Close'].rolling(200).mean().iloc[-1]
        
        # Calculate momentum score (weighted average of returns)
        momentum_score = (
            returns["1D"] * 0.1 + 
            returns["1W"] * 0.15 + 
            returns["1M"] * 0.25 + 
            returns["3M"] * 0.25 + 
            returns["6M"] * 0.15 + 
            returns["1Y"] * 0.1
        ) if all(v is not None for v in returns.values()) else None
        
        return {
            "Live Price": live_price,
            "20D MA": ma_20,
            "50D MA": ma_50,
            "200D MA": ma_200,
            "Momentum Score": momentum_score,
            **returns
        }
    except Exception as e:
        st.warning(f"Error fetching data for {ticker}: {e}")
        return None

def calculate_gold_silver_ratio(gold_price, silver_price):
    if (
        gold_price is None or silver_price is None or
        silver_price == 0 or (isinstance(silver_price, float) and math.isnan(silver_price))
    ):
        return None
    return gold_price / silver_price

def process_data():
    df = pd.DataFrame(assets)
    momentum_data = []
    for asset in assets:
        data = get_momentum_data(asset["Ticker"])
        if data:
            momentum_data.append(data)
        else:
            momentum_data.append({
                "Live Price": None,
                "20D MA": None,
                "50D MA": None,
                "200D MA": None,
                "Momentum Score": None,
                "1D": None,
                "1W": None,
                "1M": None,
                "3M": None,
                "6M": None,
                "1Y": None
            })
    momentum_df = pd.DataFrame(momentum_data)
    result_df = pd.concat([df, momentum_df], axis=1)
    
    # Calculate Gold/Silver ratio
    gold_price = result_df[result_df["Asset"] == "Gold Spot"]["Live Price"].values[0]
    silver_price = result_df[result_df["Asset"] == "Silver Spot"]["Live Price"].values[0]
    if gold_price is None or silver_price is None:
        st.warning(f"Gold price: {gold_price}, Silver price: {silver_price} – one or both are missing, so ratio is N/A.")
        result_df["Gold/Silver Ratio"] = None
    else:
        gs_ratio = calculate_gold_silver_ratio(gold_price, silver_price)
        result_df["Gold/Silver Ratio"] = None
        result_df.loc[result_df["Asset"] == "Silver Spot", "Gold/Silver Ratio"] = gs_ratio
    
    # Add moving average cross indicators
    result_df["20D > 50D"] = result_df["20D MA"] > result_df["50D MA"]
    result_df["50D > 200D"] = result_df["50D MA"] > result_df["200D MA"]
    
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
                color = "orange"
            st.markdown(f'<div class="metric-card">Ratio Status: <span style="color:{color}">{ratio_status}</span></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="metric-card">Ratio Status: N/A</div>', unsafe_allow_html=True)
except Exception as e:
    st.error(f"Error displaying metrics: {e}")

# Display momentum leaders
st.subheader("Silver Momentum Leaders")
st.markdown("""
The table below shows silver-related assets ranked by their momentum score, which combines short, medium, and long-term performance.
""")

# Sort by momentum score and format for display
momentum_df = data.copy().sort_values("Momentum Score", ascending=False)

# Format the dataframe for display
def color_momentum(val):
    if val is None:
        return "color: black"
    if val > 0:
        return "color: green"
    elif val < 0:
        return "color: red"
    return "color: black"

display_df = momentum_df.copy()
display_df["Live Price"] = display_df["Live Price"].apply(lambda x: f"${x:.2f}" if pd.notnull(x) else "N/A")
display_df["20D MA"] = display_df["20D MA"].apply(lambda x: f"${x:.2f}" if pd.notnull(x) else "N/A")
display_df["50D MA"] = display_df["50D MA"].apply(lambda x: f"${x:.2f}" if pd.notnull(x) else "N/A")
display_df["200D MA"] = display_df["200D MA"].apply(lambda x: f"${x:.2f}" if pd.notnull(x) else "N/A")
display_df["Momentum Score"] = display_df["Momentum Score"].apply(lambda x: f"{x:.1f}" if pd.notnull(x) else "N/A")

for period in ["1D", "1W", "1M", "3M", "6M", "1Y"]:
    display_df[period] = display_df[period].apply(lambda x: f"{x:.1f}%" if pd.notnull(x) else "N/A")

display_df["Gold/Silver Ratio"] = display_df["Gold/Silver Ratio"].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "N/A")

# Reorder columns
display_df = display_df[[
    "Asset", "Type", "Ticker", "Live Price", "Momentum Score", 
    "20D MA", "50D MA", "200D MA", "20D > 50D", "50D > 200D",
    "1D", "1W", "1M", "3M", "6M", "1Y", "Gold/Silver Ratio"
]]

# Display the dataframe with styling
st.dataframe(
    display_df.style.applymap(
        color_momentum,
        subset=["1D", "1W", "1M", "3M", "6M", "1Y"]
    ).applymap(
        lambda x: 'background-color: lightgreen' if x == True else ('background-color: lightcoral' if x == False else ''),
        subset=["20D > 50D", "50D > 200D"]
    ),
    height=(len(data) + 1) * 35 + 3,
    use_container_width=True
)

# Technical Analysis Section
st.subheader("Technical Analysis Signals")
st.markdown("""
**Golden Cross (Bullish Signal):**  
When the 50-day moving average crosses above the 200-day moving average (highlighted in green).

**Death Cross (Bearish Signal):**  
When the 50-day moving average crosses below the 200-day moving average (highlighted in red).

**Short-Term Momentum:**  
When the 20-day moving average is above the 50-day moving average.
""")

# Add a refresh button
if st.button("Refresh Data"):
    st.rerun()

# Add some explanation
st.markdown("""
*Note: Data is fetched from Yahoo Finance. The Momentum Score is a weighted average of returns across different time periods, 
with more weight given to intermediate-term (1-3 month) performance. The app updates when you click the Refresh Data button.*
""")
