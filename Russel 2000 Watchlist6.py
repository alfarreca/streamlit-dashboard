import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Initialize session state variables
if 'filtered_results' not in st.session_state:
    st.session_state.filtered_results = pd.DataFrame()
if 'full_data_loaded' not in st.session_state:
    st.session_state.full_data_loaded = False

# App title and description
st.title("Russell 2000 Momentum Scanner")
st.markdown("""
This app scans Russell 2000 stocks for momentum opportunities.
Select filters to narrow down the results.
""")

# Sample Russell 2000 symbols
RUSSEL_2000_SYMBOLS = [
    'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META',
    'TSLA', 'NVDA', 'PYPL', 'ADBE', 'NFLX',
    'INTC', 'CSCO', 'PEP', 'COST', 'TMUS'
]

@st.cache_data(ttl=3600)
def load_full_dataset():
    """Load and return the full Russell 2000 dataset with metrics"""
    try:
        data = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        for symbol in RUSSEL_2000_SYMBOLS:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='1y')
                if not hist.empty:
                    close = hist['Close']
                    momentum_1m = (close.iloc[-1] / close.iloc[-21] - 1) * 100  # 1 month momentum (21 trading days)
                    momentum_3m = (close.iloc[-1] / close.iloc[-63] - 1) * 100  # 3 month momentum
                    momentum_6m = (close.iloc[-1] / close.iloc[-126] - 1) * 100  # 6 month momentum
                    volume_avg = hist['Volume'].mean()
                    
                    data.append({
                        'Symbol': symbol,
                        'Name': ticker.info.get('shortName', ''),
                        'Price': close.iloc[-1],
                        '1M Momentum (%)': momentum_1m,
                        '3M Momentum (%)': momentum_3m,
                        '6M Momentum (%)': momentum_6m,
                        'Avg Volume': volume_avg,
                        'Sector': ticker.info.get('sector', 'Unknown')
                    })
            except:
                continue
        
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame()

def apply_filters(df, momentum_1m_min, momentum_3m_min, momentum_6m_min, volume_min):
    """Apply momentum and volume filters to the dataframe"""
    if df.empty:
        return df
    
    filtered = df.copy()
    filtered = filtered[filtered['1M Momentum (%)'] >= momentum_1m_min]
    filtered = filtered[filtered['3M Momentum (%)'] >= momentum_3m_min]
    filtered = filtered[filtered['6M Momentum (%)'] >= momentum_6m_min]
    filtered = filtered[filtered['Avg Volume'] >= volume_min]
    
    return filtered.sort_values('1M Momentum (%)', ascending=False)

# ... [rest of your existing functions like plot_symbol_chart remain unchanged] ...

def main():
    # Sidebar filters - UPDATED WITH 1M MOMENTUM
    with st.sidebar:
        st.header("Momentum Filters")
        
        # NEW 1-MONTH MOMENTUM FILTER
        momentum_1m_min = st.slider(
            "Minimum 1M Momentum (%)",
            min_value=-30.0,  # More sensitive to recent drops, so narrower range
            max_value=50.0,   # Extreme 1-month gains are less common
            value=5.0,        # Default threshold
            step=1.0
        )
        
        momentum_3m_min = st.slider(
            "Minimum 3M Momentum (%)",
            min_value=-50.0,
            max_value=100.0,
            value=10.0,
            step=1.0
        )
        
        momentum_6m_min = st.slider(
            "Minimum 6M Momentum (%)",
            min_value=-50.0,
            max_value=100.0,
            value=-12.0,
            step=1.0
        )
        
        volume_min = st.slider(
            "Minimum Average Volume",
            min_value=0,
            max_value=10_000_000,
            value=500_000,
            step=100_000
        )
        
        if st.button("Load Full Dataset (500+ Symbols)", key='load_data'):
            with st.spinner("Loading Russell 2000 data..."):
                st.session_state.full_data = load_full_dataset()
                st.session_state.full_data_loaded = True
                st.success("Data loaded successfully!")
    
    # Load data and apply filters - UPDATED TO INCLUDE 1M MOMENTUM
    if st.session_state.full_data_loaded:
        st.session_state.filtered_results = apply_filters(
            st.session_state.full_data,
            momentum_1m_min,
            momentum_3m_min,
            momentum_6m_min,
            volume_min
        )
    else:
        st.warning("Please load the dataset first using the button in the sidebar")
        return
    
    # Display results (unchanged)
    st.header("Filtered Results")
    if not st.session_state.filtered_results.empty:
        st.dataframe(
            st.session_state.filtered_results,
            use_container_width=True,
            hide_index=True
        )
        
        selected_symbol = st.selectbox(
            "Select symbol for detailed chart:",
            options=st.session_state.filtered_results['Symbol'].tolist()
        )
        
        if selected_symbol:
            plot_symbol_chart(selected_symbol)
    else:
        st.warning("No stocks match the current filters. Try adjusting your criteria.")

if __name__ == "__main__":
    main()
