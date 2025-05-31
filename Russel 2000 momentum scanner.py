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
                    momentum_1m = (close.iloc[-1] / close.iloc[-21] - 1) * 100
                    momentum_3m = (close.iloc[-1] / close.iloc[-63] - 1) * 100
                    momentum_6m = (close.iloc[-1] / close.iloc[-126] - 1) * 100
                    
                    # Relative strength vs benchmark
                    benchmark_1m = (benchmark.iloc[-1] / benchmark.iloc[-21] - 1) * 100
                    rel_strength = momentum_1m - benchmark_1m
                    
                    # Volatility and volume
                    volatility = hist['Close'].pct_change().std() * np.sqrt(21) * 100
                    avg_volume = hist['Volume'].mean()
                    
                    # Moving averages
                    ma_50 = close.rolling(50).mean().iloc[-1]
                    ma_200 = close.rolling(200).mean().iloc[-1]
                    
                    # Composite score
                    composite_score = (0.4*momentum_1m + 0.3*momentum_3m + 0.3*momentum_6m)
                    
                    data.append({
                        'Symbol': symbol,
                        'Name': ticker.info.get('shortName', symbol),
                        'Price': close.iloc[-1],
                        '50_MA': ma_50,
                        '200_MA': ma_200,
                        '1M Momentum (%)': momentum_1m,
                        '3M Momentum (%)': momentum_3m,
                        '6M Momentum (%)': momentum_6m,
                        'Rel Strength (%)': rel_strength,
                        'Volatility (%)': volatility,
                        'Avg Volume': avg_volume,
                        'Composite Score': composite_score,
                        'Sector': ticker.info.get('sector', 'Unknown'),
                        'MA_Status': 'Golden Cross' if ma_50 > ma_200 else 'Death Cross'
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
    
    # MA Status filter
    if params['ma_filter'] != 'All':
        filtered = filtered[filtered['MA_Status'] == params['ma_filter']]
    
    return filtered.sort_values('Composite Score', ascending=False)

# --------------------------
# VISUALIZATION FUNCTIONS
# --------------------------
def plot_symbol_chart(symbol):
    """Detailed price chart with moving averages"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='6mo')
        
        # Calculate moving averages
        hist['MA_50'] = hist['Close'].rolling(50).mean()
        hist['MA_200'] = hist['Close'].rolling(200).mean()
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                          vertical_spacing=0.05, row_heights=[0.7, 0.3])
        
        # Candlestick
        fig.add_trace(go.Candlestick(
            x=hist.index,
            open=hist['Open'],
            high=hist['High'],
            low=hist['Low'],
            close=hist['Close'],
            name='Price'
        ), row=1, col=1)
        
        # Moving Averages
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=hist['MA_50'],
            name='50-Day MA',
            line=dict(color='blue', width=1.5)
        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=hist['MA_200'],
            name='200-Day MA',
            line=dict(color='red', width=1.5)
        ), row=1, col=1)
        
        # Volume
        fig.add_trace(go.Bar(
            x=hist.index,
            y=hist['Volume'],
            name='Volume',
            marker_color='rgba(100, 100, 255, 0.6)'
        ), row=2, col=1)
        
        # Layout
        fig.update_layout(
            title=f"{symbol} Price with Moving Averages",
            height=600,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis_rangeslider_visible=False,
            hovermode="x unified"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # MA Crossover Status
        current_status = "Golden Cross (Bullish)" if hist['MA_50'].iloc[-1] > hist['MA_200'].iloc[-1] else "Death Cross (Bearish)"
        st.metric("MA Crossover Status", current_status)
        
    except Exception as e:
        st.error(f"Chart error for {symbol}: {str(e)}")

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
            'min_volume': st.slider("Min Avg Volume", 0, 10_000_000, 500_000),
            'ma_filter': st.selectbox("MA Crossover", 
                                   ['All', 'Golden Cross', 'Death Cross'],
                                   index=0)
        }
        
        if st.button("🔄 Load/Refresh Data", type="primary"):
            with st.spinner("Loading market data..."):
                st.session_state.full_data = load_full_dataset()
                st.session_state.filtered_results = apply_filters(
                    st.session_state.full_data, params)
                st.toast("Data loaded successfully!", icon="✅")
    
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
                        st.session_state.filtered_results[
                            ['Symbol', 'Name', 'Price', '50_MA', '200_MA',
                             '1M Momentum (%)', '3M Momentum (%)', '6M Momentum (%)',
                             'MA_Status', 'Sector']
                        ].sort_values('1M Momentum (%)', ascending=False),
                        column_config={
                            "Price": st.column_config.NumberColumn(format="$%.2f"),
                            "50_MA": st.column_config.NumberColumn(format="$%.2f"),
                            "200_MA": st.column_config.NumberColumn(format="$%.2f"),
                            "1M Momentum (%)": st.column_config.NumberColumn(format="%.1f%%"),
                            "3M Momentum (%)": st.column_config.NumberColumn(format="%.1f%%"),
                            "6M Momentum (%)": st.column_config.NumberColumn(format="%.1f%%")
                        },
                        hide_index=True,
                        use_container_width=True,
                        height=700
                    )
                    
                    selected_symbol = st.selectbox(
                        "Select symbol for detailed analysis:",
                        options=st.session_state.filtered_results['Symbol'],
                        index=0
                    )
                    
                    if selected_symbol:
                        plot_symbol_chart(selected_symbol)
                else:
                    st.warning("No stocks match current filters. Try adjusting criteria.")
            
            with col2:
                st.metric("Stocks Passing Filters", len(st.session_state.filtered_results))
                
                with st.expander("📊 Sector Distribution"):
                    if not st.session_state.filtered_results.empty:
                        sector_counts = st.session_state.filtered_results['Sector'].value_counts()
                        st.bar_chart(sector_counts)
    
    with tab2:
        st.subheader("Sector Momentum Analysis")
        if not st.session_state.full_data.empty:
            # FIXED: Properly handle styled dataframe
            sector_mom = st.session_state.full_data.groupby('Sector').agg({
                '1M Momentum (%)': 'mean',
                '3M Momentum (%)': 'mean',
                '6M Momentum (%)': 'mean'
            }).sort_values('1M Momentum (%)', ascending=False)
            
            # Display the dataframe without style first
            st.dataframe(
                sector_mom,
                use_container_width=True
            )
            
            # Then create a visualization
            fig = go.Figure()
            for col in sector_mom.columns:
                fig.add_trace(go.Bar(
                    x=sector_mom.index,
                    y=sector_mom[col],
                    name=col
                ))
            
            fig.update_layout(
                barmode='group',
                title="Sector Momentum by Timeframe",
                xaxis_title="Sector",
                yaxis_title="Momentum (%)"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Load data to see sector analysis")

if __name__ == "__main__":
    main()
