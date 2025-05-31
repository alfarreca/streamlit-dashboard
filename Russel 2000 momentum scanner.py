import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
from plotly.subplots import make_subplots

# Initialize session state
if 'filtered_results' not in st.session_state:
    st.session_state.filtered_results = pd.DataFrame()
if 'full_data' not in st.session_state:
    st.session_state.full_data = pd.DataFrame()
if 'alerts' not in st.session_state:
    st.session_state.alerts = []

# Sample Russell 2000 symbols
RUSSEL_2000_SYMBOLS = [
    'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META',
    'TSLA', 'NVDA', 'PYPL', 'ADBE', 'NFLX'
]

# --------------------------
# DATA LOADING FUNCTIONS
# --------------------------
@st.cache_data(ttl=3600)
def load_full_dataset():
    """Load and process Russell 2000 data with momentum metrics"""
    try:
        data = []
        benchmark = yf.Ticker("IWM").history(period='1y')['Close']
        
        with st.status("Loading market data...", expanded=True) as status:
            for i, symbol in enumerate(RUSSEL_2000_SYMBOLS):
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period='1y')
                    
                    if len(hist) < 200: continue
                    
                    # Price and moving averages
                    close = hist['Close']
                    ma_20 = close.rolling(20).mean().iloc[-1]
                    ma_50 = close.rolling(50).mean().iloc[-1]
                    ma_200 = close.rolling(200).mean().iloc[-1]
                    
                    # Momentum calculations
                    momentum_1m = (close.iloc[-1] / close.iloc[-21] - 1) * 100
                    momentum_3m = (close.iloc[-1] / close.iloc[-63] - 1) * 100
                    momentum_6m = (close.iloc[-1] / close.iloc[-126] - 1) * 100
                    
                    # Relative strength vs benchmark
                    benchmark_1m = (benchmark.iloc[-1] / benchmark.iloc[-21] - 1) * 100
                    rel_strength = momentum_1m - benchmark_1m
                    
                    # Volatility and volume
                    volatility = hist['Close'].pct_change().std() * np.sqrt(21) * 100
                    avg_volume = hist['Volume'].mean()
                    
                    # MA cross status
                    ma_status = "Golden Cross" if ma_50 > ma_200 else ("Death Cross" if ma_50 < ma_200 else "Neutral")
                    
                    data.append({
                        'Symbol': symbol,
                        'Name': ticker.info.get('shortName', symbol),
                        'Price': close.iloc[-1],
                        '20_MA': ma_20,
                        '50_MA': ma_50,
                        '200_MA': ma_200,
                        '1M Momentum (%)': momentum_1m,
                        '3M Momentum (%)': momentum_3m,
                        '6M Momentum (%)': momentum_6m,
                        'Rel Strength (%)': rel_strength,
                        'Volatility (%)': volatility,
                        'Avg Volume': avg_volume,
                        'MA_Status': ma_status,
                        'Sector': ticker.info.get('sector', 'Unknown')
                    })
                    
                    if i % 5 == 0:
                        status.update(label=f"Processed {i}/{len(RUSSEL_2000_SYMBOLS)} symbols...")
                
                except Exception as e:
                    continue
            
            status.update(label="Data loaded successfully!", state="complete")
            return pd.DataFrame(data)
    
    except Exception as e:
        st.error(f"Data loading failed: {str(e)}")
        return pd.DataFrame()

# --------------------------
# FILTERING FUNCTION
# --------------------------
def apply_filters(df, params):
    """Apply all filters based on user parameters"""
    if df.empty:
        return df
    
    filtered = df.copy()
    
    # Apply each filter if the parameter exists
    if 'rel_strength_min' in params:
        filtered = filtered[filtered['Rel Strength (%)'] >= params['rel_strength_min']]
    if 'max_volatility' in params:
        filtered = filtered[filtered['Volatility (%)'] <= params['max_volatility']]
    if 'min_volume' in params:
        filtered = filtered[filtered['Avg Volume'] >= params['min_volume']]
    if 'ma_filter' in params and params['ma_filter'] != 'All':
        filtered = filtered[filtered['MA_Status'] == params['ma_filter']]
    
    return filtered.sort_values('1M Momentum (%)', ascending=False)

# --------------------------
# MAIN APP LAYOUT
# --------------------------
def main():
    st.set_page_config(layout="wide", page_title="Russell 2000 Momentum Scanner")
    st.title("🚀 Russell 2000 Momentum Scanner")
    
    # ------------------
    # SIDEBAR CONTROLS
    # ------------------
    with st.sidebar:
        st.header("Momentum Filters")
        
        # Relative Strength Filter
        rel_strength_min = st.slider(
            "Min Rel Strength (%)",
            min_value=-20.0,
            max_value=30.0,
            value=0.0,
            step=0.1
        )
        
        # Volatility Filter
        max_volatility = st.slider(
            "Max Volatility (%)",
            min_value=5.0,
            max_value=50.0,
            value=30.0,
            step=0.1
        )
        
        # Volume Filter
        min_volume = st.slider(
            "Min Avg Volume",
            min_value=0,
            max_value=10_000_000,
            value=500_000,
            step=100_000
        )
        
        # MA Crossover Filter
        ma_filter = st.selectbox(
            "MA Crossover",
            options=['All', 'Golden Cross', 'Death Cross'],
            index=0
        )
        
        if st.button("🔄 Load/Refresh Data", type="primary"):
            with st.spinner("Loading market data..."):
                st.session_state.full_data = load_full_dataset()
                st.session_state.filtered_results = apply_filters(
                    st.session_state.full_data,
                    {
                        'rel_strength_min': rel_strength_min,
                        'max_volatility': max_volatility,
                        'min_volume': min_volume,
                        'ma_filter': ma_filter
                    }
                )
                st.toast("Data loaded successfully!", icon="✅")
    
    # ------------------
    # MAIN DASHBOARD
    # ------------------
    if not st.session_state.full_data.empty:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.subheader("Filtered Results")
            if not st.session_state.filtered_results.empty:
                st.dataframe(
                    st.session_state.filtered_results,
                    column_config={
                        "Price": st.column_config.NumberColumn(format="$%.2f"),
                        "20_MA": st.column_config.NumberColumn(format="$%.2f"),
                        "50_MA": st.column_config.NumberColumn(format="$%.2f"),
                        "200_MA": st.column_config.NumberColumn(format="$%.2f"),
                        "1M Momentum (%)": st.column_config.ProgressColumn(
                            format="%.1f%%",
                            min_value=-50,
                            max_value=100
                        ),
                        "3M Momentum (%)": st.column_config.ProgressColumn(
                            format="%.1f%%",
                            min_value=-50,
                            max_value=100
                        ),
                        "6M Momentum (%)": st.column_config.ProgressColumn(
                            format="%.1f%%",
                            min_value=-50,
                            max_value=100
                        )
                    },
                    hide_index=True,
                    use_container_width=True,
                    height=700
                )
            else:
                st.warning("No stocks match current filters. Try adjusting criteria.")
        
        with col2:
            st.metric("Stocks Passing Filters", len(st.session_state.filtered_results))
            
            with st.expander("📊 Sector Distribution"):
                if not st.session_state.filtered_results.empty:
                    sector_counts = st.session_state.filtered_results['Sector'].value_counts()
                    st.bar_chart(sector_counts)
    else:
        st.warning("Please load data using the button in the sidebar")

if __name__ == "__main__":
    main()
