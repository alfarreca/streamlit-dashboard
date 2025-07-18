import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import yfinance as yf
from datetime import datetime, timedelta

# App config
st.set_page_config(page_title="HEEM FX Hedge App", layout="wide")

# Cache data to improve performance
@st.cache_data(ttl=3600)  # Cache for 1 hour
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
            # Download each ticker separately to handle failures
            prices = pd.DataFrame()
            for ticker, name in tickers.items():
                try:
                    data = yf.download(
                        ticker, 
                        start=start_date, 
                        end=end_date,
                        progress=False
                    )
                    if not data.empty and 'Close' in data.columns:
                        prices[name] = data['Close']
                    else:
                        st.warning(f"Could not load data for {name}")
                except Exception as e:
                    st.warning(f"Error loading {name}: {str(e)}")
            
            if prices.empty:
                st.error("No currency data could be loaded. Using sample data.")
                # Fallback to sample data
                date_range = pd.date_range(start=start_date, end=end_date)
                prices = pd.DataFrame(
                    np.random.uniform(0.8, 1.2, (len(date_range), len(tickers))),
                    index=date_range,
                    columns=list(tickers.values())
                )
            
            returns = prices.pct_change().dropna()
            volatility = returns.rolling(21).std() * np.sqrt(252)  # Annualized volatility
            
            return prices, returns, volatility
            
        except Exception as e:
            st.error(f"Error loading data: {str(e)}")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# Load data
currency_prices, currency_returns, currency_volatility = load_currency_data()

# Sidebar controls
st.sidebar.header("HEEM Configuration")
available_currencies = currency_prices.columns.tolist()
selected_currencies = st.sidebar.multiselect(
    "Select EM Currencies",
    options=available_currencies,
    default=available_currencies[:3] if len(available_currencies) > 0 else []
)

if len(selected_currencies) == 0:
    st.warning("Please select at least one currency")
    st.stop()

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
    recent_vol = currency_volatility[selected_currencies].iloc[-lookback_period:].mean().sort_values(ascending=False)
    fig = px.bar(recent_vol, 
                title=f"Annualized Volatility (Last {lookback_period} days)")
    st.plotly_chart(fig, use_container_width=True)

# Hedge Calculator section
st.header("Hedge Calculator")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Hedge Impact Simulation")
    investment_amount = st.number_input("Investment Amount (USD)", min_value=1000, value=100000, step=1000)
    
    selected_currency = st.selectbox("Select Currency to Hedge", selected_currencies)
    if len(currency_returns) > 0:
        currency_return = currency_returns[selected_currency].iloc[-1] * 100
    else:
        currency_return = 0
    
    st.metric(f"Last Period {selected_currency} Return", f"{currency_return:.2f}%")
    
    unhedged_value = investment_amount * (1 + currency_return/100)
    hedged_value = investment_amount * (1 + (currency_return/100)*(1-hedge_ratio/100))
    
    st.metric("Unhedged Value", f"${unhedged_value:,.2f}")
    st.metric(f"Hedged Value ({hedge_ratio}% hedge)", f"${hedged_value:,.2f}")

with col2:
    st.subheader("Correlation Matrix")
    if len(currency_returns) > 0:
        corr_matrix = currency_returns[selected_currencies].corr()
        fig = px.imshow(corr_matrix, 
                       text_auto=True,
                       color_continuous_scale='RdBu',
                       range_color=[-1, 1],
                       title="Currency Return Correlations")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No correlation data available")

# Performance Attribution
st.header("Performance Attribution")

portfolio_return = st.number_input("Enter Portfolio Local Return (%)", min_value=-100.0, max_value=100.0, value=8.0)

attribution_data = []
for currency in selected_currencies:
    if len(currency_returns) > 0:
        fx_return = currency_returns[currency].iloc[-1] * 100
    else:
        fx_return = 0
        
    total_return = (1 + portfolio_return/100) * (1 + fx_return/100) - 1
    hedged_return = (1 + portfolio_return/100) * (1 + fx_return/100 * (1-hedge_ratio/100)) - 1
    
    attribution_data.append({
        'Currency': currency,
        'Local Return': portfolio_return,
        'FX Return': fx_return,
        'Unhedged Return': total_return * 100,
        'Hedged Return': hedged_return * 100,
        'Hedge Benefit': (hedged_return - total_return) * 100
    })

attribution_df = pd.DataFrame(attribution_data)
st.dataframe(attribution_df.style.format({
    'Local Return': '{:.2f}%',
    'FX Return': '{:.2f}%',
    'Unhedged Return': '{:.2f}%',
    'Hedged Return': '{:.2f}%',
    'Hedge Benefit': '{:.2f}%'
}))

fig = px.bar(attribution_df, 
             x='Currency', 
             y=['Unhedged Return', 'Hedged Return'],
             barmode='group',
             title="Hedged vs Unhedged Returns")
st.plotly_chart(fig, use_container_width=True)

# Footer
st.markdown("---")
st.markdown("""
**HEEM FX Hedge App** - This tool helps investors manage currency risk in emerging markets.
""")
