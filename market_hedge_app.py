import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta
from scipy.stats import norm

st.set_page_config(page_title="Enhanced Market Hedge Simulator", layout="wide")

# Black-Scholes Model for Put Options Pricing
def black_scholes_put(S, K, T, r, sigma):
    d1 = (np.log(S / K) + (r + sigma**2 / 2.) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    put_price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    return put_price

# App Title and Introduction
st.title("📉 Enhanced Market Crash Hedge Simulator")
st.markdown("""
Explore realistic hedging strategies and analyze their historical performance against market downturns with advanced metrics and interactive visualizations.
""")

# Sidebar Controls
st.sidebar.header("Strategy Parameters")

strategy = st.sidebar.selectbox("Select Hedging Strategy", [
    "Put Options", "Inverse ETFs", "Gold Allocation", "Dynamic Allocation", "Volatility Index (VIX)"
])

ticker = st.sidebar.text_input("Primary Asset (e.g., SPY)", "SPY")
end_date = datetime.today()
start_date = st.sidebar.date_input("Start Date", value=end_date - timedelta(days=365*5), max_value=end_date - timedelta(days=1))

# Fetch Market Data
@st.cache_data
def load_data(ticker, start_date, end_date):
    return yf.download(ticker, start=start_date, end=end_date, auto_adjust=True)

# Primary Asset Data
main_data = load_data(ticker, start_date, end_date)
if main_data.empty:
    st.error("No data available for the selected ticker/date.")
    st.stop()

main_data['Returns'] = main_data['Close'].pct_change()
main_data['Cumulative'] = (1 + main_data['Returns']).cumprod()

# Strategy Simulation Logic
if strategy == "Put Options":
    strike_offset = st.sidebar.slider("Strike Price (% below current)", 5, 30, 10)
    expiration_days = st.sidebar.slider("Days to Expiration", 30, 180, 30)
    annual_volatility = main_data['Returns'].std() * np.sqrt(252)
    risk_free_rate = 0.03
    
    main_data['Put_Price'] = main_data['Close'].apply(lambda S: black_scholes_put(
        S, S*(1 - strike_offset/100), expiration_days/365, risk_free_rate, annual_volatility
    ))
    main_data['Put_Cost'] = main_data['Put_Price'] / main_data['Close']
    main_data['Hedge_Payoff'] = np.where(
        main_data['Close'].shift(-expiration_days) < main_data['Close'] * (1 - strike_offset/100),
        (main_data['Close'] * (1 - strike_offset/100) - main_data['Close'].shift(-expiration_days)) / main_data['Close'],
        0
    )
    main_data['Strategy_Returns'] = main_data['Returns'] - main_data['Put_Cost']/expiration_days*30 + main_data['Hedge_Payoff']

# Performance Metrics
main_data['Strategy_Cumulative'] = (1 + main_data['Strategy_Returns'].fillna(0)).cumprod()

sharpe_ratio = np.sqrt(252) * main_data['Strategy_Returns'].mean() / main_data['Strategy_Returns'].std()
sortino_ratio = np.sqrt(252) * main_data['Strategy_Returns'].mean() / main_data[main_data['Strategy_Returns'] < 0]['Strategy_Returns'].std()

# Visualization
fig = px.line(main_data, y=['Cumulative', 'Strategy_Cumulative'],
              title=f"{ticker} vs. Strategy Performance", labels={'value': 'Growth of $1', 'variable': 'Strategy'})
st.plotly_chart(fig, use_container_width=True)

# Metrics Display
st.subheader("📊 Performance Metrics")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Buy & Hold Return", f"{main_data['Cumulative'].iloc[-1]-1:.1%}")
col2.metric("Strategy Return", f"{main_data['Strategy_Cumulative'].iloc[-1]-1:.1%}")
col3.metric("Sharpe Ratio", f"{sharpe_ratio:.2f}")
col4.metric("Sortino Ratio", f"{sortino_ratio:.2f}")

# Interactive Drawdown Chart
main_data['Drawdown'] = main_data['Cumulative']/main_data['Cumulative'].cummax() - 1
main_data['Strategy_Drawdown'] = main_data['Strategy_Cumulative']/main_data['Strategy_Cumulative'].cummax() - 1

fig_dd = px.line(main_data, y=['Drawdown', 'Strategy_Drawdown'], title="Drawdown Comparison")
st.plotly_chart(fig_dd, use_container_width=True)

# Download Results
csv = main_data.to_csv().encode('utf-8')
st.download_button("📥 Download Results CSV", csv, "results.csv")

# Strategy Explanation
st.info("""
**🔍 Strategy Insights:**

- **Put Options:** Protect your portfolio from sharp declines by using options as insurance.
- **Sharpe & Sortino Ratios:** Evaluate risk-adjusted returns. Sharpe measures overall volatility, while Sortino focuses specifically on downside risk.

*Note: This simulation provides enhanced realism but remains illustrative. Always consider transaction costs and market conditions for practical applications.*
""")
