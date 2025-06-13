import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import yfinance as yf
from datetime import datetime, timedelta

# Suppress yfinance warnings
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

# App config
st.set_page_config(page_title="Global FX Hedge App", layout="wide")

# Comprehensive currency list - EM + Major currencies
CURRENCY_PAIRS = {
    # Emerging Market Currencies
    'EM_LatinAmerica': {
        'BRLUSD=X': 'Brazilian Real (BRL)',
        'MXNUSD=X': 'Mexican Peso (MXN)',
        'COPUSD=X': 'Colombian Peso (COP)',
        'CLPUSD=X': 'Chilean Peso (CLP)',
        'ARSUSD=X': 'Argentine Peso (ARS)'
    },
    'EM_Asia': {
        'CNYUSD=X': 'Chinese Yuan (CNY)',
        'INRUSD=X': 'Indian Rupee (INR)',
        'KRWUSD=X': 'South Korean Won (KRW)',
        'IDRUSD=X': 'Indonesian Rupiah (IDR)',
        'THBUSD=X': 'Thai Baht (THB)',
        'MYRUSD=X': 'Malaysian Ringgit (MYR)'
    },
    'EM_EMEA': {
        'ZARUSD=X': 'South African Rand (ZAR)',
        'TRYUSD=X': 'Turkish Lira (TRY)',
        'PLNUSD=X': 'Polish Zloty (PLN)',
        'HUFUSD=X': 'Hungarian Forint (HUF)',
        'CZKUSD=X': 'Czech Koruna (CZK)'
    },
    
    # Major World Currencies
    'Major_G10': {
        'EURUSD=X': 'Euro (EUR)',
        'JPYUSD=X': 'Japanese Yen (JPY)',
        'GBPUSD=X': 'British Pound (GBP)',
        'CHFUSD=X': 'Swiss Franc (CHF)',
        'AUDUSD=X': 'Australian Dollar (AUD)',
        'NZDUSD=X': 'New Zealand Dollar (NZD)',
        'CADUSD=X': 'Canadian Dollar (CAD)',
        'SEKUSD=X': 'Swedish Krona (SEK)',
        'NOKUSD=X': 'Norwegian Krone (NOK)'
    },
    
    'Major_Others': {
        'SGDUSD=X': 'Singapore Dollar (SGD)',
        'HKDUSD=X': 'Hong Kong Dollar (HKD)',
        'ILSUSD=X': 'Israeli Shekel (ILS)'
    }
}

# Create a flattened version of all currencies for easy access
ALL_CURRENCIES = {}
for group in CURRENCY_PAIRS.values():
    ALL_CURRENCIES.update(group)

@st.cache_data(ttl=3600)
def load_currency_data():
    """Load currency data with robust error handling"""
    end_date = datetime.today()
    start_date = end_date - timedelta(days=365*3)
    
    with st.spinner(f"Loading {len(ALL_CURRENCIES)} currency pairs..."):
        try:
            # Download in batches
            prices = pd.DataFrame()
            tickers = list(ALL_CURRENCIES.keys())
            batch_size = 5
            
            for i in range(0, len(tickers), batch_size):
                batch = tickers[i:i + batch_size]
                try:
                    data = yf.download(
                        batch,
                        start=start_date,
                        end=end_date,
                        progress=False,
                        group_by='ticker',
                        auto_adjust=True  # Explicitly set to avoid warning
                    )
                    
                    for ticker in batch:
                        col_name = ALL_CURRENCIES[ticker]
                        if ticker in data:
                            if 'Close' in data[ticker]:
                                prices[col_name] = data[ticker]['Close']
                            else:
                                st.warning(f"No close price for {col_name}")
                except Exception as e:
                    st.warning(f"Failed to download batch: {str(e)}")
                    continue
            
            if prices.empty:
                st.error("No data loaded. Using sample data.")
                date_range = pd.date_range(start=start_date, end=end_date)
                prices = pd.DataFrame(
                    np.random.uniform(0.5, 1.5, (len(date_range), len(ALL_CURRENCIES))),
                    index=date_range,
                    columns=list(ALL_CURRENCIES.values())
                )
            
            returns = prices.pct_change().dropna()
            volatility = returns.rolling(21).std() * np.sqrt(252)
            
            return prices, returns, volatility
            
        except Exception as e:
            st.error(f"Critical error: {str(e)}")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# Load data
currency_prices, currency_returns, currency_volatility = load_currency_data()

# Sidebar with expandable currency groups
st.sidebar.header("Currency Selection")

selected_currencies = []
for group_name, currencies in CURRENCY_PAIRS.items():
    with st.sidebar.expander(group_name.replace("_", " ")):
        group_selected = st.multiselect(
            f"Select {group_name.replace('_', ' ')}",
            options=[ALL_CURRENCIES[t] for t in currencies.keys()],
            default=[list(currencies.values())[0]] if currencies else []
        )
        selected_currencies.extend(group_selected)

if not selected_currencies:
    st.warning("Please select at least one currency")
    st.stop()

# Hedge parameters
st.sidebar.header("Hedge Parameters")
hedge_ratio = st.sidebar.slider(
    "Base Hedge Ratio (%)",
    min_value=0,
    max_value=100,
    value=50,
    step=5,
    help="Percentage of exposure to hedge"
)

adaptive_hedge = st.sidebar.checkbox(
    "Enable Adaptive Hedging",
    value=True,
    help="Adjust hedge ratio based on volatility"
)

if adaptive_hedge:
    vol_adjustment = st.sidebar.slider(
        "Volatility Sensitivity",
        min_value=0.0,
        max_value=2.0,
        value=1.0,
        step=0.1,
        help="Higher values increase hedge ratio when volatility is high"
    )

# Main app
st.title("Global Currency Hedge Analyzer")
st.markdown("""
**Hedge against USD depreciation** by selecting currencies from emerging markets and major global currencies.
""")

# Dashboard
st.header("Currency Performance Dashboard")

tab1, tab2, tab3 = st.tabs(["Trends", "Volatility", "Correlations"])

with tab1:
    st.subheader("Currency Trends (USD per unit)")
    fig = px.line(currency_prices[selected_currencies])
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Annualized Volatility")
    vol_window = st.select_slider(
        "Lookback Period (days)",
        options=[30, 60, 90, 180, 365],
        value=90
    )
    recent_vol = currency_volatility[selected_currencies].iloc[-vol_window:].mean().sort_values()
    fig = px.bar(recent_vol, orientation='h')
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("Currency Correlations")
    corr_window = st.select_slider(
        "Correlation Period (days)",
        options=[30, 60, 90, 180, 365],
        value=90
    )
    corr_data = currency_returns[selected_currencies].iloc[-corr_window:].corr()
    fig = px.imshow(corr_data, text_auto=True, color_continuous_scale='RdBu')
    st.plotly_chart(fig, use_container_width=True)

# Hedge Calculator
st.header("Hedge Strategy Builder")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Portfolio Configuration")
    portfolio_value = st.number_input("Portfolio Value (USD)", min_value=1000, value=1000000)
    currency_allocation = {}
    
    for currency in selected_currencies:
        allocation = st.slider(
            f"{currency} Allocation (%)",
            min_value=0,
            max_value=100,
            value=100//len(selected_currencies),
            step=1
        )
        currency_allocation[currency] = allocation

with col2:
    st.subheader("Hedge Impact Analysis")
    
    if st.button("Calculate Hedge Impact"):
        results = []
        total_unhedged = 0
        total_hedged = 0
        
        for currency, alloc in currency_allocation.items():
            if alloc == 0:
                continue
                
            amount = portfolio_value * (alloc/100)
            curr_return = currency_returns[currency].iloc[-1] if currency in currency_returns else 0
            
            if adaptive_hedge and currency in currency_volatility:
                # Adjust hedge ratio based on volatility
                curr_vol = currency_volatility[currency].iloc[-90:].mean()
                avg_vol = currency_volatility.mean().mean()
                adj_factor = min(2.0, max(0.5, (curr_vol/avg_vol)**vol_adjustment))
                effective_hr = min(100, hedge_ratio * adj_factor)
            else:
                effective_hr = hedge_ratio
                
            unhedged = amount * (1 + curr_return)
            hedged = amount * (1 + curr_return * (1 - effective_hr/100))
            
            results.append({
                "Currency": currency,
                "Allocation (%)": alloc,
                "Unhedged Value": unhedged,
                "Hedged Value": hedged,
                "Hedge Ratio (%)": effective_hr,
                "FX Return (%)": curr_return * 100
            })
            
            total_unhedged += unhedged
            total_hedged += hedged
        
        # Display results
        results_df = pd.DataFrame(results)
        st.dataframe(
            results_df.style.format({
                "FX Return (%)": "{:.2f}%",
                "Hedge Ratio (%)": "{:.1f}%",
                "Unhedged Value": "${:,.2f}",
                "Hedged Value": "${:,.2f}"
            })
        )
        
        st.metric("Total Portfolio Value (Unhedged)", f"${total_unhedged:,.2f}")
        st.metric("Total Portfolio Value (Hedged)", f"${total_hedged:,.2f}",
                 delta=f"{(total_hedged-total_unhedged):,.2f} vs unhedged")

# Footer
st.markdown("---")
st.markdown("""
**Global FX Hedge App** | *Data from Yahoo Finance* | [Methodology](#)
""")
