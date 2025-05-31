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

# Sample Russell 2000 symbols (replace with actual constituents in production)
RUSSEL_2000_SYMBOLS = [
    'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META',
    'TSLA', 'NVDA', 'PYPL', 'ADBE', 'NFLX',
    'INTC', 'CSCO', 'PEP', 'COST', 'TMUS'
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
        
        with st.status("Loading 2000+ stocks...", expanded=True) as status:
            for i, symbol in enumerate(RUSSEL_2000_SYMBOLS):
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period='1y')
                    
                    if len(hist) < 200: continue
                    
                    # Momentum calculations
                    close = hist['Close']
                    momentum_1m = (close.iloc[-1] / close.iloc[-21] - 1) * 100  # 21 trading days
                    momentum_3m = (close.iloc[-1] / close.iloc[-63] - 1) * 100  # 63 trading days
                    momentum_6m = (close.iloc[-1] / close.iloc[-126] - 1) * 100  # 126 trading days
                    
                    # Relative strength vs benchmark
                    benchmark_1m = (benchmark.iloc[-1] / benchmark.iloc[-21] - 1) * 100
                    rel_strength = momentum_1m - benchmark_1m
                    
                    # Volatility and volume
                    volatility = hist['Close'].pct_change().std() * np.sqrt(21) * 100
                    avg_volume = hist['Volume'].mean()
                    
                    # Composite score
                    composite_score = (0.4*momentum_1m + 0.3*momentum_3m + 0.3*momentum_6m)
                    
                    data.append({
                        'Symbol': symbol,
                        'Name': ticker.info.get('shortName', symbol),
                        'Price': close.iloc[-1],
                        '1M Momentum (%)': momentum_1m,
                        '3M Momentum (%)': momentum_3m,
                        '6M Momentum (%)': momentum_6m,
                        'Rel Strength (%)': rel_strength,
                        'Volatility (%)': volatility,
                        'Avg Volume': avg_volume,
                        'Composite Score': composite_score,
                        'Sector': ticker.info.get('sector', 'Unknown')
                    })
                    
                    if i % 10 == 0:
                        status.update(label=f"Processed {i}/{len(RUSSEL_2000_SYMBOLS)} symbols...")
                
                except Exception as e:
                    continue
            
            status.update(label="Data loaded successfully!", state="complete")
            return pd.DataFrame(data)
    
    except Exception as e:
        st.error(f"Data loading failed: {str(e)}")
        return pd.DataFrame()

# --------------------------
# FILTERING FUNCTIONS
# --------------------------
def apply_filters(df, params):
    """Apply momentum filters based on user parameters"""
    if df.empty:
        return df
    
    filtered = df.copy()
    
    # Momentum filters
    filtered = filtered[filtered['1M Momentum (%)'] >= params['mom_1m_min']]
    filtered = filtered[filtered['3M Momentum (%)'] >= params['mom_3m_min']]
    filtered = filtered[filtered['6M Momentum (%)'] >= params['mom_6m_min']]
    
    # Advanced filters
    filtered = filtered[filtered['Rel Strength (%)'] >= params['rel_strength_min']]
    filtered = filtered[filtered['Volatility (%)'] <= params['max_volatility']]
    filtered = filtered[filtered['Avg Volume'] >= params['min_volume']]
    
    return filtered.sort_values('Composite Score', ascending=False)

# --------------------------
# VISUALIZATION FUNCTIONS
# --------------------------
def plot_symbol_chart(symbol):
    """Detailed price chart for selected symbol"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='6mo')
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                          vertical_spacing=0.05, row_heights=[0.7, 0.3])
        
        # Candlestick chart
        fig.add_trace(go.Candlestick(
            x=hist.index,
            open=hist['Open'],
            high=hist['High'],
            low=hist['Low'],
            close=hist['Close'],
            name='Price'
        ), row=1, col=1)
        
        # Volume chart
        fig.add_trace(go.Bar(
            x=hist.index,
            y=hist['Volume'],
            name='Volume',
            marker_color='rgba(100, 100, 255, 0.6)'
        ), row=2, col=1)
        
        fig.update_layout(
            title=f"{symbol} Price and Volume",
            height=600,
            showlegend=False,
            xaxis_rangeslider_visible=False
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"Couldn't load chart for {symbol}: {str(e)}")

def plot_radial_momentum(symbol):
    """Radial momentum visualization"""
    try:
        data = st.session_state.filtered_results
        row = data[data['Symbol'] == symbol].iloc[0]
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatterpolar(
            r=[row['1M Momentum (%)'], row['3M Momentum (%)'], row['6M Momentum (%)']],
            theta=['1M', '3M', '6M'],
            fill='toself',
            name='Momentum'
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[min(row['1M Momentum (%)'], row['3M Momentum (%)'], row['6M Momentum (%)']) - 10, 
                    max(row['1M Momentum (%)'], row['3M Momentum (%)'], row['6M Momentum (%)']) + 10]
                )
            ),
            title=f"{symbol} Momentum Profile",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    except Exception as e:
        st.warning(f"Couldn't generate radial chart: {str(e)}")

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
        
        params = {
            'mom_1m_min': st.slider("1M Min Momentum (%)", -30.0, 50.0, 5.0),
            'mom_3m_min': st.slider("3M Min Momentum (%)", -50.0, 100.0, 10.0),
            'mom_6m_min': st.slider("6M Min Momentum (%)", -50.0, 100.0, 0.0),
            'rel_strength_min': st.slider("Min Rel Strength (%)", -20.0, 30.0, 0.0),
            'max_volatility': st.slider("Max Volatility (%)", 5.0, 50.0, 30.0),
            'min_volume': st.slider("Min Avg Volume", 0, 10_000_000, 500_000)
        }
        
        if st.button("🔄 Load/Refresh Data", type="primary"):
            with st.spinner("Loading market data..."):
                st.session_state.full_data = load_full_dataset()
                st.session_state.filtered_results = apply_filters(
                    st.session_state.full_data, params)
    
    # ------------------
    # MAIN DASHBOARD
    # ------------------
    tab1, tab2 = st.tabs(["Stock Scanner", "Sector Analysis"])
    
    with tab1:
        if not st.session_state.full_data.empty:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.subheader("Filtered Results")
                if not st.session_state.filtered_results.empty:
                    st.dataframe(
                        st.session_state.filtered_results,
                        column_config={
                            "1M Momentum (%)": st.column_config.NumberColumn(format="%.1f%%"),
                            "3M Momentum (%)": st.column_config.NumberColumn(format="%.1f%%"),
                            "6M Momentum (%)": st.column_config.NumberColumn(format="%.1f%%")
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    selected_symbol = st.selectbox(
                        "Select symbol for detailed analysis:",
                        options=st.session_state.filtered_results['Symbol']
                    )
                    
                    if selected_symbol:
                        plot_symbol_chart(selected_symbol)
                        plot_radial_momentum(selected_symbol)
                else:
                    st.warning("No stocks match current filters. Try adjusting criteria.")
            
            with col2:
                st.metric("Stocks Passing Filters", len(st.session_state.filtered_results))
                
                with st.expander("📊 Sector Distribution"):
                    if not st.session_state.filtered_results.empty:
                        sector_counts = st.session_state.filtered_results['Sector'].value_counts()
                        st.bar_chart(sector_counts)
                
                with st.expander("🔔 Price Alerts"):
                    alert_symbol = st.selectbox(
                        "Symbol", 
                        options=st.session_state.filtered_results['Symbol'] if not st.session_state.filtered_results.empty else []
                    )
                    alert_price = st.number_input("Alert Price", value=0.0)
                    if st.button("Set Alert"):
                        st.session_state.alerts.append({
                            'symbol': alert_symbol,
                            'price': alert_price
                        })
                        st.success(f"Alert set for {alert_symbol} at ${alert_price:.2f}")
        
        else:
            st.warning("Please load data using the button in the sidebar")
    
    with tab2:
        st.subheader("Sector Momentum Analysis")
        if not st.session_state.full_data.empty:
            sector_mom = st.session_state.full_data.groupby('Sector')['1M Momentum (%)'].mean().sort_values()
            st.bar_chart(sector_mom)
        else:
            st.info("Load data to see sector analysis")

if __name__ == "__main__":
    main()
