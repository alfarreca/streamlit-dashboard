import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

# App title and description
st.title("Market Crash Hedge Strategy Simulator")
st.write("""
This app helps you test different hedging strategies against stock market crashes.
Explore how various approaches would have performed during historical market downturns.
""")

# Sidebar controls
st.sidebar.header("Strategy Parameters")

# Strategy selection
strategy = st.sidebar.selectbox(
    "Select Hedging Strategy",
    ["Put Options", "Inverse ETFs", "Gold Allocation", "Dynamic Allocation", "Volatility Index (VIX)"]
)

# Asset selection
ticker = st.sidebar.text_input("Primary Asset (e.g., SPY, QQQ)", "SPY")

# Date range
end_date = datetime.today()
start_date = st.sidebar.date_input(
    "Start Date",
    value=end_date - timedelta(days=365*5),
    max_value=end_date - timedelta(days=1)
)

# Strategy-specific parameters
if strategy == "Put Options":
    strike_offset = st.sidebar.slider("Strike Price (% below current)", 5, 30, 10)
    expiration_days = st.sidebar.slider("Days to Expiration", 30, 180, 30)
elif strategy == "Inverse ETFs":
    hedge_ratio = st.sidebar.slider("Hedge Ratio (% of portfolio)", 5, 50, 20)
    inverse_etf = st.sidebar.selectbox(
        "Inverse ETF",
        ["SQQQ (Nasdaq)", "SDOW (Dow)", "SPXU (S&P)", "SH (S&P)"]
    )
elif strategy == "Gold Allocation":
    gold_percentage = st.sidebar.slider("Gold Allocation (% of portfolio)", 5, 50, 20)
elif strategy == "Dynamic Allocation":
    moving_average_days = st.sidebar.slider("Moving Average Days", 50, 200, 100)
    risk_off_asset = st.sidebar.selectbox(
        "Risk-Off Asset",
        ["BIL (T-Bills)", "GLD (Gold)", "TLT (Long Bonds)", "SHY (Short Bonds)"]
    )
elif strategy == "Volatility Index (VIX)":
    vix_threshold = st.sidebar.slider("VIX Threshold for Hedge", 20, 40, 25)
    hedge_percentage = st.sidebar.slider("Hedge Percentage at Threshold", 10, 100, 50)

# Download data function
@st.cache_data
def load_data(ticker, start_date, end_date):
    data = yf.download(ticker, start=start_date, end=end_date, auto_adjust=True)
    return data

# Main analysis
try:
    # Load primary asset data
    main_data = load_data(ticker, start_date, end_date)
    
    if main_data.empty:
        st.error("No data found for the selected ticker and date range.")
        st.stop()
    
    # Calculate returns
    main_data['Returns'] = main_data['Close'].pct_change()
    main_data['Cumulative'] = (1 + main_data['Returns']).cumprod()
    
    # Strategy simulation
    if strategy == "Put Options":
        st.subheader("Put Options Hedge Strategy")
        st.write(f"""
        Simulating buying {strike_offset}% out-of-the-money put options with {expiration_days} days to expiration,
        rolled monthly.
        """)
        # Simplified simulation (actual option pricing would be more complex)
        main_data['Hedge_Payoff'] = np.where(
            main_data['Close'] < main_data['Close'].shift(expiration_days) * (1 - strike_offset/100),
            (main_data['Close'].shift(expiration_days) * (1 - strike_offset/100) - main_data['Close']) / main_data['Close'].shift(expiration_days),
            0
        )
        # Assume cost of puts is 3% of notional per month
        main_data['Strategy_Returns'] = main_data['Returns'] - 0.03/expiration_days*30 + main_data['Hedge_Payoff']
        
    elif strategy == "Inverse ETFs":
        st.subheader("Inverse ETF Hedge Strategy")
        st.write(f"""
        Allocating {hedge_ratio}% of portfolio to {inverse_etf} as a hedge against market downturns.
        """)
        # Load inverse ETF data
        inverse_data = load_data(inverse_etf.split()[0], start_date, end_date)
        inverse_data['Inverse_Returns'] = inverse_data['Close'].pct_change()
        # Combine returns
        combined = pd.concat([
            main_data['Returns'].rename('Main'),
            inverse_data['Inverse_Returns'].rename('Inverse')
        ], axis=1).dropna()
        main_data['Strategy_Returns'] = (
            (1 - hedge_ratio/100) * combined['Main'] + 
            (hedge_ratio/100) * (-combined['Inverse'])
        )
        
    elif strategy == "Gold Allocation":
        st.subheader("Gold Allocation Strategy")
        st.write(f"""
        Maintaining a {gold_percentage}% allocation to gold (GLD) as a defensive position.
        """)
        # Load gold data
        gold_data = load_data("GLD", start_date, end_date)
        gold_data['Gold_Returns'] = gold_data['Close'].pct_change()
        # Combine returns
        combined = pd.concat([
            main_data['Returns'].rename('Main'),
            gold_data['Gold_Returns'].rename('Gold')
        ], axis=1).dropna()
        main_data['Strategy_Returns'] = (
            (1 - gold_percentage/100) * combined['Main'] + 
            (gold_percentage/100) * combined['Gold']
        )
        
    elif strategy == "Dynamic Allocation":
        st.subheader("Dynamic Allocation Strategy")
        st.write(f"""
        Moving to {risk_off_asset} when price is below {moving_average_days}-day moving average.
        """)
        # Calculate moving average
        main_data['MA'] = main_data['Close'].rolling(moving_average_days).mean()
        # Load risk-off asset data
        risk_off_data = load_data(risk_off_asset.split()[0], start_date, end_date)
        risk_off_data['Risk_Off_Returns'] = risk_off_data['Close'].pct_change()
        # Combine data
        combined = pd.concat([
            main_data[['Returns', 'MA', 'Close']],
            risk_off_data['Risk_Off_Returns']
        ], axis=1).dropna()
        # Strategy logic
        combined['Strategy_Returns'] = np.where(
            combined['Close'] > combined['MA'],
            combined['Returns'],
            combined['Risk_Off_Returns']
        )
        main_data['Strategy_Returns'] = combined['Strategy_Returns']
        
    elif strategy == "Volatility Index (VIX)":
        st.subheader("VIX-Based Hedge Strategy")
        st.write(f"""
        Increasing hedge when VIX rises above {vix_threshold}, up to {hedge_percentage}% allocation to cash.
        """)
        # Load VIX data
        vix_data = load_data("^VIX", start_date, end_date)
        vix_data['VIX_Close'] = vix_data['Close']
        # Combine data
        combined = pd.concat([
            main_data['Returns'],
            vix_data['VIX_Close']
        ], axis=1).dropna()
        # Calculate hedge percentage based on VIX
        combined['Hedge_Pct'] = np.where(
            combined['VIX_Close'] > vix_threshold,
            np.minimum(
                hedge_percentage/100,
                (combined['VIX_Close'] - vix_threshold)/vix_threshold * (hedge_percentage/100)
            ),
            0
        )
        # Assume cash returns 0% (could use BIL returns for more accuracy)
        combined['Strategy_Returns'] = (
            (1 - combined['Hedge_Pct']) * combined['Returns'] +
            combined['Hedge_Pct'] * 0
        )
        main_data['Strategy_Returns'] = combined['Strategy_Returns']
    
    # Calculate strategy performance
    main_data['Strategy_Cumulative'] = (1 + main_data['Strategy_Returns'].fillna(0)).cumprod()
    
    # Plot results
    fig = px.line(
        main_data,
        y=['Cumulative', 'Strategy_Cumulative'],
        title=f"{ticker} vs. Hedge Strategy Performance",
        labels={'value': 'Growth of $1', 'variable': 'Strategy'}
    )
    fig.update_layout(legend_title_text='')
    st.plotly_chart(fig)
    
    # Performance metrics
    st.subheader("Performance Metrics")
    total_return = main_data['Cumulative'].iloc[-1] - 1
    strategy_return = main_data['Strategy_Cumulative'].iloc[-1] - 1
    max_drawdown = (main_data['Cumulative'] / main_data['Cumulative'].cummax() - 1).min()
    strategy_drawdown = (main_data['Strategy_Cumulative'] / main_data['Strategy_Cumulative'].cummax() - 1).min()
    col1, col2 = st.columns(2)
    col1.metric("Buy & Hold Return", f"{total_return:.1%}")
    col2.metric("Strategy Return", f"{strategy_return:.1%}", f"{(strategy_return - total_return):.1%}")
    col3, col4 = st.columns(2)
    col3.metric("Buy & Hold Max Drawdown", f"{max_drawdown:.1%}")
    col4.metric("Strategy Max Drawdown", f"{strategy_drawdown:.1%}", f"{(strategy_drawdown - max_drawdown):.1%}")

    # Drawdown chart
    main_data['Drawdown'] = main_data['Cumulative'] / main_data['Cumulative'].cummax() - 1
    main_data['Strategy_Drawdown'] = main_data['Strategy_Cumulative'] / main_data['Strategy_Cumulative'].cummax() - 1
    fig2 = px.line(
        main_data,
        y=['Drawdown', 'Strategy_Drawdown'],
        title="Drawdown Comparison",
        labels={'value': 'Drawdown', 'variable': 'Strategy'}
    )
    fig2.update_layout(legend_title_text='')
    st.plotly_chart(fig2)
    
    # Strategy explanation
    st.subheader("Strategy Explanation")
    if strategy == "Put Options":
        st.write("""
        **Put Options Strategy:**  
        This strategy involves purchasing put options as insurance against market declines. 
        - You pay a premium for the right to sell at a predetermined price (strike)
        - If the market falls below the strike, the put options increase in value, offsetting losses
        - The cost is the premium paid, which acts like an insurance payment
        """)
    elif strategy == "Inverse ETFs":
        st.write("""
        **Inverse ETFs Strategy:**  
        Inverse ETFs are designed to move opposite to their benchmark index.
        - They provide a hedge by gaining when the market falls
        - No options or margin required
        - However, they have tracking error and decay over time, especially leveraged ones
        """)
    elif strategy == "Gold Allocation":
        st.write("""
        **Gold Allocation Strategy:**  
        Gold has historically been a safe haven during market turmoil.
        - Gold often moves independently of stocks
        - Provides diversification benefits
        - Doesn't perfectly correlate with market crashes but can provide stability
        """)
    elif strategy == "Dynamic Allocation":
        st.write("""
        **Dynamic Allocation Strategy:**  
        This trend-following approach moves to safety when markets weaken.
        - Uses moving averages to identify market trends
        - Shifts to defensive assets when trend is down
        - Avoids large drawdowns but may whipsaw in volatile markets
        """)
    elif strategy == "Volatility Index (VIX)":
        st.write("""
        **VIX-Based Strategy:**  
        The VIX measures expected market volatility and spikes during crashes.
        - Increases hedges when volatility rises (market stress)
        - Reduces hedges when markets are calm
        - Attempts to be more capital efficient than constant hedging
        """)
    st.write("""
    *Note: This is a simplified simulation. Actual implementation would require more sophisticated modeling,
    especially for options strategies. Past performance is not indicative of future results.*
    """)
except Exception as e:
    st.error(f"An error occurred: {str(e)}")
