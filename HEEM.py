import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import yfinance as yf
from datetime import datetime, timedelta

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
                        group_by='ticker'
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

# Rest of the app remains the same...
# [Include all the remaining code from the previous implementation]
