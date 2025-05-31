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
# CHARTING FUNCTIONS
# --------------------------
def plot_symbol_chart(symbol, show_ma_20=True, show_ma_50=True, show_ma_200=True):
    """Enhanced price chart with multiple moving averages"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='6mo')
        
        # Calculate all moving averages
        hist['MA_20'] = hist['Close'].rolling(20).mean()
        hist['MA_50'] = hist['Close'].rolling(50).mean()
        hist['MA_200'] = hist['Close'].rolling(200).mean()
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                          vertical_spacing=0.05, row_heights=[0.7, 0.3])
        
        # Candlestick trace
        fig.add_trace(go.Candlestick(
            x=hist.index,
            open=hist['Open'],
            high=hist['High'],
            low=hist['Low'],
            close=hist['Close'],
            name='Price',
            increasing_line_color='#2ECC71',
            decreasing_line_color='#E74C3C'
        ), row=1, col=1)
        
        # Add moving averages based on user selection
        if show_ma_20:
            fig.add_trace(go.Scatter(
                x=hist.index,
                y=hist['MA_20'],
                name='20-Day MA',
                line=dict(color='#3498DB', width=1.5, dash='dot')
            ), row=1, col=1)
        
        if show_ma_50:
            fig.add_trace(go.Scatter(
                x=hist.index,
                y=hist['MA_50'],
                name='50-Day MA',
                line=dict(color='#9B59B6', width=2)
            ), row=1, col=1)
        
        if show_ma_200:
            fig.add_trace(go.Scatter(
                x=hist.index,
                y=hist['MA_200'],
                name='200-Day MA',
                line=dict(color='#E67E22', width=2.5)
            ), row=1, col=1)
        
        # Volume trace
        fig.add_trace(go.Bar(
            x=hist.index,
            y=hist['Volume'],
            name='Volume',
            marker_color='rgba(100, 100, 255, 0.6)',
            showlegend=False
        ), row=2, col=1)
        
        # Layout configuration
        fig.update_layout(
            title=f"{symbol} Price with Moving Averages",
            height=700,
            hovermode="x unified",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            xaxis_rangeslider_visible=False,
            margin=dict(t=60, l=20, r=20, b=20)
        )
        
        # Y-axis labels
        fig.update_yaxes(title_text="Price ($)", row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)
        
        # Current price and MA values annotation
        last_close = hist['Close'].iloc[-1]
        ma_values = {
            'Price': last_close,
            '20MA': hist['MA_20'].iloc[-1],
            '50MA': hist['MA_50'].iloc[-1],
            '200MA': hist['MA_200'].iloc[-1]
        }
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Display current MA values and relationships
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Current Price", f"${last_close:.2f}")
        col2.metric("20-Day MA", 
                   f"${ma_values['20MA']:.2f}", 
                   f"{(last_close - ma_values['20MA'])/ma_values['20MA']*100:.2f}%")
        col3.metric("50-Day MA", 
                   f"${ma_values['50MA']:.2f}", 
                   f"{(last_close - ma_values['50MA'])/ma_values['50MA']*100:.2f}%")
        col4.metric("200-Day MA", 
                   f"${ma_values['200MA']:.2f}", 
                   f"{(last_close - ma_values['200MA'])/ma_values['200MA']*100:.2f}%")
        
        # MA crossover status
        ma_status = "Golden Cross (Bullish)" if ma_values['50MA'] > ma_values['200MA'] else "Death Cross (Bearish)"
        st.metric("MA Crossover Status", ma_status)
        
    except Exception as e:
        st.error(f"Error loading chart for {symbol}: {str(e)}")

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
        st.header("Chart Settings")
        
        # Moving average visibility toggles
        ma_20 = st.checkbox("Show 20-Day MA", value=True)
        ma_50 = st.checkbox("Show 50-Day MA", value=True)
        ma_200 = st.checkbox("Show 200-Day MA", value=True)
        
        st.header("Momentum Filters")
        mom_1m_min = st.slider("1M Min Momentum (%)", -30.0, 50.0, 5.0)
        mom_3m_min = st.slider("3M Min Momentum (%)", -50.0, 100.0, 10.0)
        mom_6m_min = st.slider("6M Min Momentum (%)", -50.0, 100.0, 0.0)
        
        if st.button("🔄 Load/Refresh Data", type="primary"):
            with st.spinner("Loading market data..."):
                st.session_state.full_data = load_full_dataset()
                st.session_state.filtered_results = st.session_state.full_data[
                    (st.session_state.full_data['1M Momentum (%)'] >= mom_1m_min) &
                    (st.session_state.full_data['3M Momentum (%)'] >= mom_3m_min) &
                    (st.session_state.full_data['6M Momentum (%)'] >= mom_6m_min)
                ].sort_values('1M Momentum (%)', ascending=False)
                st.toast("Data loaded successfully!", icon="✅")
    
    # ------------------
    # MAIN DASHBOARD
    # ------------------
    if not st.session_state.full_data.empty:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.subheader("Filtered Results")
            if not st.session_state.filtered_results.empty:
                # Display results table
                st.dataframe(
                    st.session_state.filtered_results[
                        ['Symbol', 'Name', 'Price', '20_MA', '50_MA', '200_MA',
                         '1M Momentum (%)', '3M Momentum (%)', '6M Momentum (%)',
                         'MA_Status', 'Sector']
                    ],
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
                
                # Symbol selection for detailed chart
                selected_symbol = st.selectbox(
                    "Select symbol for detailed analysis:",
                    options=st.session_state.filtered_results['Symbol'],
                    index=0
                )
                
                if selected_symbol:
                    plot_symbol_chart(selected_symbol, ma_20, ma_50, ma_200)
            else:
                st.warning("No stocks match current filters. Try adjusting criteria.")
        
        with col2:
            st.metric("Stocks Passing Filters", len(st.session_state.filtered_results))
            
            with st.expander("📊 Sector Distribution"):
                if not st.session_state.filtered_results.empty:
                    sector_counts = st.session_state.filtered_results['Sector'].value_counts()
                    st.bar_chart(sector_counts)
            
            with st.expander("🔔 Price Alerts"):
                if not st.session_state.filtered_results.empty:
                    alert_symbol = st.selectbox(
                        "Symbol", 
                        options=st.session_state.filtered_results['Symbol'],
                        key="alert_symbol"
                    )
                    current_price = st.session_state.filtered_results[
                        st.session_state.filtered_results['Symbol'] == alert_symbol
                    ]['Price'].iloc[0]
                    
                    alert_price = st.number_input(
                        "Alert Price", 
                        value=current_price,
                        step=0.01,
                        format="%.2f"
                    )
                    
                    if st.button("Set Alert"):
                        st.session_state.alerts.append({
                            'symbol': alert_symbol,
                            'price': alert_price,
                            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M")
                        })
                        st.success(f"Alert set for {alert_symbol} at ${alert_price:.2f}")
                
                if st.session_state.alerts:
                    st.write("Active Alerts:")
                    for alert in st.session_state.alerts:
                        col1, col2 = st.columns([3, 1])
                        col1.write(f"{alert['symbol']} @ ${alert['price']:.2f}")
                        if col2.button("Remove", key=f"remove_{alert['symbol']}"):
                            st.session_state.alerts.remove(alert)
                            st.rerun()
    else:
        st.warning("Please load data using the button in the sidebar")

if __name__ == "__main__":
    main()
