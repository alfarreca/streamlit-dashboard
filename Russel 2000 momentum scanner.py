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

# Sample Russell 2000 symbols (in a real app, you'd load all 2000+)
RUSSEL_2000_SYMBOLS = [
    'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META',
    'TSLA', 'NVDA', 'PYPL', 'ADBE', 'NFLX',
    'INTC', 'CSCO', 'PEP', 'COST', 'TMUS'
]

@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_full_dataset():
    """Load and return the full Russell 2000 dataset with metrics"""
    try:
        # In a real app, you would load actual Russell 2000 data here
        # This is a simplified version with mock data
        data = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        for symbol in RUSSEL_2000_SYMBOLS:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='1y')
                if not hist.empty:
                    close = hist['Close']
                    momentum_3m = (close.iloc[-1] / close.iloc[-63] - 1) * 100  # 3 month momentum (63 trading days)
                    momentum_6m = (close.iloc[-1] / close.iloc[-126] - 1) * 100  # 6 month momentum
                    volume_avg = hist['Volume'].mean()
                    
                    data.append({
                        'Symbol': symbol,
                        'Name': ticker.info.get('shortName', ''),
                        'Price': close.iloc[-1],
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

def apply_filters(df, momentum_3m_min, momentum_6m_min, volume_min):
    """Apply momentum and volume filters to the dataframe"""
    if df.empty:
        return df
    
    filtered = df.copy()
    filtered = filtered[filtered['3M Momentum (%)'] >= momentum_3m_min]
    filtered = filtered[filtered['6M Momentum (%)'] >= momentum_6m_min]
    filtered = filtered[filtered['Avg Volume'] >= volume_min]
    
    return filtered.sort_values('3M Momentum (%)', ascending=False)

def plot_symbol_chart(symbol):
    """Plot detailed chart for selected symbol"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='1y')
        
        if hist.empty:
            st.warning(f"No data available for {symbol}")
            return
        
        fig = go.Figure()
        
        # Candlestick chart
        fig.add_trace(go.Candlestick(
            x=hist.index,
            open=hist['Open'],
            high=hist['High'],
            low=hist['Low'],
            close=hist['Close'],
            name='Price'
        ))
        
        # 50-day moving average
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=hist['Close'].rolling(50).mean(),
            name='50-Day MA',
            line=dict(color='blue', width=1)
        ))
        
        # 200-day moving average
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=hist['Close'].rolling(200).mean(),
            name='200-Day MA',
            line=dict(color='red', width=1)
        ))
        
        fig.update_layout(
            title=f"{symbol} Price Chart",
            xaxis_title='Date',
            yaxis_title='Price ($)',
            xaxis_rangeslider_visible=False,
            height=600
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Show company info
        info = ticker.info
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Company Info")
            st.write(f"**Name:** {info.get('shortName', 'N/A')}")
            st.write(f"**Sector:** {info.get('sector', 'N/A')}")
            st.write(f"**Industry:** {info.get('industry', 'N/A')}")
        
        with col2:
            st.subheader("Key Metrics")
            st.write(f"**Market Cap:** {info.get('marketCap', 'N/A'):,}")
            st.write(f"**PE Ratio:** {info.get('trailingPE', 'N/A')}")
            st.write(f"**52W High:** {info.get('fiftyTwoWeekHigh', 'N/A')}")
            st.write(f"**52W Low:** {info.get('fiftyTwoWeekLow', 'N/A')}")
            
    except Exception as e:
        st.error(f"Error loading chart for {symbol}: {str(e)}")

# Main app logic
def main():
    # Sidebar filters
    with st.sidebar:
        st.header("Momentum Filters")
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
            value=15.0,
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
    
    # Load data and apply filters
    if st.session_state.full_data_loaded:
        st.session_state.filtered_results = apply_filters(
            st.session_state.full_data,
            momentum_3m_min,
            momentum_6m_min,
            volume_min
        )
    else:
        st.warning("Please load the dataset first using the button in the sidebar")
        return
    
    # Display results
    st.header("Filtered Results")
    if not st.session_state.filtered_results.empty:
        st.dataframe(
            st.session_state.filtered_results,
            use_container_width=True,
            hide_index=True
        )
        
        # Symbol selection for detailed chart
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
