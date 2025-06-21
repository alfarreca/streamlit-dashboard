import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

try:
    from scipy.stats import norm
    has_scipy = True
except ImportError:
    has_scipy = False

st.set_page_config(page_title="Enhanced Market Hedge Simulator", layout="wide")

# Black-Scholes Model for Put Options Pricing
def black_scholes_put(S, K, T, r, sigma):
    from math import log, sqrt, exp
    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
        return 0
    d1 = (log(S / K) + (r + sigma ** 2 / 2.) * T) / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)
    put_price = K * exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    return max(put_price, 0)

st.title("📉 Enhanced Market Crash Hedge Simulator")
st.markdown("""
Explore realistic hedging strategies and analyze their historical performance against market downturns with advanced metrics and interactive visualizations.
""")

st.sidebar.header("Strategy Parameters")

strategy = st.sidebar.selectbox(
    "Select Hedging Strategy",
    [
        "Put Options", "Inverse ETFs", "Gold Allocation",
        "Dynamic Allocation", "Volatility Index (VIX)"
    ]
)

ticker = st.sidebar.text_input("Primary Asset (e.g., SPY)", "SPY")
end_date = datetime.today()
start_date = st.sidebar.date_input(
    "Start Date", value=end_date - timedelta(days=365*5),
    max_value=end_date - timedelta(days=1)
)

@st.cache_data
def load_data(ticker, start_date, end_date):
    return yf.download(ticker, start=start_date, end=end_date, auto_adjust=True)

main_data = load_data(ticker, start_date, end_date)
if main_data.empty:
    st.error("No data available for the selected ticker/date.")
    st.stop()

main_data['Returns'] = main_data['Close'].pct_change()
main_data['Cumulative'] = (1 + main_data['Returns']).cumprod()

# Strategy Logic
if strategy == "Put Options":
    if not has_scipy:
        st.error("scipy is required for Black-Scholes option pricing. Please add 'scipy' to your requirements.txt.")
        st.stop()
    strike_offset = st.sidebar.slider("Strike Price (% below current)", 5, 30, 10)
    expiration_days = st.sidebar.slider("Days to Expiration", 30, 180, 30)
    annual_volatility = main_data['Returns'].std() * np.sqrt(252)
    risk_free_rate = 0.03

    # Calculate put option price for each day (row-wise, robust)
    def safe_black_scholes(row):
        S = row['Close']
        K = S * (1 - strike_offset / 100) if pd.notnull(S) else np.nan
        T = expiration_days / 365
        r = risk_free_rate
        sigma = annual_volatility
        if pd.notnull(S) and S > 0 and K > 0 and T > 0 and sigma > 0:
            return black_scholes_put(S, K, T, r, sigma)
        else:
            return np.nan

    main_data['Put_Price'] = main_data.apply(safe_black_scholes, axis=1)

    # Robust put cost calculation
    main_data['Put_Cost'] = np.where(
        (main_data['Close'] > 0) & (~main_data['Put_Price'].isna()),
        main_data['Put_Price'] / main_data['Close'],
        np.nan
    )
    main_data['Put_Cost'].fillna(method='ffill', inplace=True)
    main_data['Put_Cost'].fillna(0, inplace=True)

    # Simplified hedge payoff
    main_data['Hedge_Payoff'] = np.where(
        main_data['Close'].shift(-expiration_days) < main_data['Close'] * (1 - strike_offset/100),
        (main_data['Close'] * (1 - strike_offset/100) - main_data['Close'].shift(-expiration_days)) / main_data['Close'],
        0
    )

    # Strategy returns
    main_data['Strategy_Returns'] = main_data['Returns'] - main_data['Put_Cost']/expiration_days*30 + main_data['Hedge_Payoff']

else:
    st.info("This demo version only implements the Put Options strategy in detail for demonstration. Contact support for the full multi-strategy version.")

main_data['Strategy_Cumulative'] = (1 + main_data['Strategy_Returns'].fillna(0)).cumprod()

# Advanced Metrics
sharpe_ratio = np.sqrt(252) * main_data['Strategy_Returns'].mean() / main_data['Strategy_Returns'].std() if main_data['Strategy_Returns'].std() > 0 else np.nan
sortino_ratio = np.sqrt(252) * main_data['Strategy_Returns'].mean() / main_data[main_data['Strategy_Returns'] < 0]['Strategy_Returns'].std() if main_data[main_data['Strategy_Returns'] < 0]['Strategy_Returns'].std() > 0 else np.nan

# Visualization
fig = px.line(
    main_data,
    y=['Cumulative', 'Strategy_Cumulative'],
    title=f"{ticker} vs. Strategy Performance",
    labels={'value': 'Growth of $1', 'variable': 'Strategy'}
)
st.plotly_chart(fig, use_container_width=True)

# Metrics Display
st.subheader("📊 Performance Metrics")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Buy & Hold Return", f"{main_data['Cumulative'].iloc[-1]-1:.1%}")
col2.metric("Strategy Return", f"{main_data['Strategy_Cumulative'].iloc[-1]-1:.1%}")
col3.metric("Sharpe Ratio", f"{sharpe_ratio:.2f}" if not np.isnan(sharpe_ratio) else "N/A")
col4.metric("Sortino Ratio", f"{sortino_ratio:.2f}" if not np.isnan(sortino_ratio) else "N/A")

# Drawdown chart
main_data['Drawdown'] = main_data['Cumulative'] / main_data['Cumulative'].cummax() - 1
main_data['Strategy_Drawdown'] = main_data['Strategy_Cumulative'] / main_data['Strategy_Cumulative'].cummax() - 1

fig_dd = px.line(main_data, y=['Drawdown', 'Strategy_Drawdown'], title="Drawdown Comparison")
st.plotly_chart(fig_dd, use_container_width=True)

# Download results
csv = main_data.to_csv().encode('utf-8')
st.download_button("📥 Download Results CSV", csv, "results.csv")

# Strategy Explanation
st.info("""
**🔍 Strategy Insights:**

- **Put Options:** Protect your portfolio from sharp declines by using options as insurance.
- **Sharpe & Sortino Ratios:** Evaluate risk-adjusted returns. Sharpe measures overall volatility, while Sortino focuses specifically on downside risk.

*Note: This simulation provides enhanced realism but remains illustrative. Always consider transaction costs and market conditions for practical applications.*
""")
