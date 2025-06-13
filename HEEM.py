import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import yfinance as yf
from datetime import datetime, timedelta

# App config
st.set_page_config(page_title="HEEM FX Hedge App", layout="wide")

# Cache data to improve performance
@st.cache_data
def load_currency_data():
    """Load EM currency data with robust error handling"""
    tickers = {
        'BRLUSD=X': 'Brazilian Real',
        'MXNUSD=X': 'Mexican Peso',
        'ZARUSD=X': 'South African Rand',
        'INRUSD=X': 'Indian Rupee',
        'CNYUSD=X': 'Chinese Yuan',
        'KRWUSD=X': 'South Korean Won',
        'TRYUSD=X': 'Turkish Lira'
    }
    end_date = datetime.today()
    start_date = end_date - timedelta(days=365*3)
    
    # Download data with progress indication
    with st.spinner("Loading currency data..."):
        try:
            data = yf.download(
                list(tickers.keys()), 
                start=start_date, 
                end=end_date,
                progress=False,
                group_by='ticker'
            )
            
            # Handle multi-level DataFrame
            prices = pd.DataFrame()
            for ticker in tickers:
                if ticker in data:
                    prices[tickers[ticker]] = data[ticker]['Adj Close']
                else:
                    st.warning(f"Could not load data for {tickers[ticker]}")
            
            if prices.empty:
                st.error("No currency data could be loaded. Please check your internet connection.")
                return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
            
            returns = prices.pct_change().dropna()
            volatility = returns.rolling(21).std() * np.sqrt(252)  # Annualized volatility
            
            return prices, returns, volatility
            
        except Exception as e:
            st.error(f"Error loading data: {str(e)}")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# Load data
currency_prices, currency_returns, currency_volatility = load_currency_data()

# Only proceed if we have data
if not currency_prices.empty:
    # Sidebar controls
    st.sidebar.header("HEEM Configuration")
    selected_currencies = st.sidebar.multiselect(
        "Select EM Currencies",
        options=currency_prices.columns,
        default=currency_prices.columns.tolist()[:3]  # Default to first 3
    )

    hedge_ratio = st.sidebar.slider(
        "Hedge Ratio (%)",
        min_value=0,
        max_value=100,
        value=50,
        step=5
    )

    lookback_period = st.sidebar.selectbox(
        "Volatility Lookback Period",
        options=[30, 90, 180, 365],
        index=2
    )

    # Main app
    st.title("Currency-Hedged EM (HEEM) FX Risk Management")

    # Dashboard section
    st.header("FX Risk Dashboard")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Currency Performance")
        fig = px.line(currency_prices[selected_currencies], 
                     title="EM Currency Trends (USD per unit)")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Currency Volatility")
        recent_vol = currency_volatility.iloc[-lookback_period:].mean().sort_values(ascending=False)
        fig = px.bar(recent_vol[selected_currencies], 
                    title=f"Annualized Volatility (Last {lookback_period} days)")
        st.plotly_chart(fig, use_container_width=True)

    # Rest of your app code...
    # [Include the remaining sections from the original code]
    
else:
    st.warning("The app couldn't load currency data. Please try again later.")
