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

# Sample Russell 2000 symbols (limited for testing)
RUSSEL_2000_SYMBOLS = [
    'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META',
    'TSLA', 'NVDA', 'PYPL', 'ADBE', 'NFLX'
]

# --------------------------
# TECHNICAL INDICATOR FUNCTIONS (Pure Python)
# --------------------------
def calculate_rsi(prices, period=14):
    """Calculate Relative Strength Index (RSI) without TA-Lib"""
    deltas = np.diff(prices)
    seed = deltas[:period+1]
    up = seed[seed >= 0].sum()/period
    down = -seed[seed < 0].sum()/period
    rs = up/down
    rsi = np.zeros_like(prices)
    rsi[:period] = 100. - 100./(1.+rs)
    
    for i in range(period, len(prices)):
        delta = deltas[i-1]
        if delta > 0:
            upval = delta
            downval = 0.
        else:
            upval = 0.
            downval = -delta
        
        up = (up*(period-1) + upval)/period
        down = (down*(period-1) + downval)/period
        rs = up/down
        rsi[i] = 100. - 100./(1.+rs)
        
    return rsi[-1] if len(rsi) > 0 else 50  # Default to neutral if no data

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calculate MACD without TA-Lib"""
    exp1 = pd.Series(prices).ewm(span=fast, adjust=False).mean()
    exp2 = pd.Series(prices).ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    return macd.values[-1], signal_line.values[-1], histogram.values[-1]

# --------------------------
# DATA LOADING FUNCTIONS (Optimized)
# --------------------------
@st.cache_data(ttl=3600, max_entries=1)  # Stronger caching
def load_full_dataset():
    """Optimized data loading with progress tracking"""
    try:
        data = []
        benchmark = yf.Ticker("IWM").history(period='1y')['Close']
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, symbol in enumerate(RUSSEL_2000_SYMBOLS):
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='6mo')  # Reduced timeframe
                
                if len(hist) < 20: continue  # Minimum data check
                
                # Price and moving averages
                close = hist['Close'].values
                ma_50 = pd.Series(close).rolling(50).mean().iloc[-1]
                ma_200 = pd.Series(close).rolling(200).mean().iloc[-1]
                
                # Technical indicators
                rsi = calculate_rsi(close)
                macd, macd_signal, macd_hist = calculate_macd(close)
                
                # Momentum calculations (optimized)
                momentum_1m = (close[-1] / close[-21] - 1) * 100 if len(close) >= 21 else 0
                momentum_3m = (close[-1] / close[-63] - 1) * 100 if len(close) >= 63 else 0
                momentum_6m = (close[-1] / close[-126] - 1) * 100 if len(close) >= 126 else 0
                
                # Relative strength vs benchmark
                benchmark_1m = (benchmark.iloc[-1] / benchmark.iloc[-21] - 1) * 100 if len(benchmark) >= 21 else 0
                rel_strength = momentum_1m - benchmark_1m
                
                # Volatility and volume
                volatility = pd.Series(close).pct_change().std() * np.sqrt(21) * 100
                avg_volume = hist['Volume'].mean()
                
                data.append({
                    'Symbol': symbol,
                    'Name': ticker.info.get('shortName', symbol),
                    'Price': close[-1],
                    '50_MA': ma_50,
                    '200_MA': ma_200,
                    'RSI (14)': rsi,
                    'MACD': macd,
                    'MACD_Signal': macd_signal,
                    '1M Momentum (%)': momentum_1m,
                    '3M Momentum (%)': momentum_3m,
                    '6M Momentum (%)': momentum_6m,
                    'Rel Strength (%)': rel_strength,
                    'Volatility (%)': volatility,
                    'Avg Volume': avg_volume,
                    'Sector': ticker.info.get('sector', 'Unknown'),
                    'MA_Status': 'Golden Cross' if ma_50 > ma_200 else 'Death Cross'
                })
                
                # Update progress
                progress = (i + 1) / len(RUSSEL_2000_SYMBOLS)
                progress_bar.progress(progress)
                status_text.text(f"Loading {symbol} ({i+1}/{len(RUSSEL_2000_SYMBOLS)})")
                
            except Exception as e:
                continue
        
        progress_bar.empty()
        status_text.empty()
        return pd.DataFrame(data)
    
    except Exception as e:
        st.error(f"Data loading failed: {str(e)}")
        return pd.DataFrame()

# --------------------------
# FILTERING FUNCTIONS
# --------------------------
def apply_filters(df, params):
    """Apply all filters with validation"""
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
    
    return filtered.sort_values('1M Momentum (%)', ascending=False)

# --------------------------
# VISUALIZATION FUNCTIONS (Optimized)
# --------------------------
def plot_technical_chart(symbol):
    """Optimized chart with RSI and MACD"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='3mo')  # Reduced timeframe for performance
        
        if hist.empty:
            st.warning(f"No data available for {symbol}")
            return
        
        # Calculate indicators
        closes = hist['Close'].values
        rsi = np.array([calculate_rsi(closes[:i+14]) if i+14 <= len(closes) else 50 
                      for i in range(len(closes))])
        macd, signal, hist_macd = zip(*[calculate_macd(closes[:i+26]) if i+26 <= len(closes) else (0,0,0) 
                                  for i in range(len(closes))])
        
        # Create subplots
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                          vertical_spacing=0.05, row_heights=[0.6, 0.2, 0.2])
        
        # Price
        fig.add_trace(go.Candlestick(
            x=hist.index,
            open=hist['Open'],
            high=hist['High'],
            low=hist['Low'],
            close=hist['Close'],
            name='Price'
        ), row=1, col=1)
        
        # Volume
        fig.add_trace(go.Bar(
            x=hist.index,
            y=hist['Volume'],
            name='Volume',
            marker_color='rgba(100, 100, 255, 0.6)'
        ), row=2, col=1)
        
        # RSI
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=rsi,
            name='RSI (14)',
            line=dict(color='purple', width=1)
        ), row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
        
        fig.update_layout(
            title=f"{symbol} Technical Analysis",
            height=700,
            showlegend=False,
            xaxis_rangeslider_visible=False
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Current values
        col1, col2 = st.columns(2)
        col1.metric("RSI (14)", f"{rsi[-1]:.1f}", 
                   "Overbought" if rsi[-1] > 70 else ("Oversold" if rsi[-1] < 30 else "Neutral"))
        col2.metric("MACD", f"{macd[-1]:.2f}", 
                   "Bullish" if macd[-1] > signal[-1] else "Bearish")
        
    except Exception as e:
        st.error(f"Error loading chart: {str(e)}")

# --------------------------
# MAIN APP LAYOUT (Optimized)
# --------------------------
def main():
    st.set_page_config(layout="wide", page_title="Russell 2000 Scanner")
    st.title("🚀 Russell 2000 Momentum Scanner (Optimized)")
    
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
            'ma_filter': st.selectbox("MA Crossover", ['All', 'Golden Cross', 'Death Cross'], index=0)
        }
        
        if st.button("🔄 Load Data", type="primary", help="Load optimized dataset"):
            with st.spinner("Loading optimized data..."):
                st.session_state.full_data = load_full_dataset()
                if not st.session_state.full_data.empty:
                    st.session_state.filtered_results = apply_filters(st.session_state.full_data, params)
                    st.toast("Data loaded successfully!", icon="✅")
                else:
                    st.error("Failed to load data")
    
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
                            ['Symbol', 'Name', 'Price', 'RSI (14)', 'MACD',
                             '1M Momentum (%)', '3M Momentum (%)', '6M Momentum (%)']
                        ].sort_values('1M Momentum (%)', ascending=False),
                        column_config={
                            "Price": st.column_config.NumberColumn(format="$%.2f"),
                            "RSI (14)": st.column_config.NumberColumn(format="%.1f"),
                            "MACD": st.column_config.NumberColumn(format="%.2f"),
                            "1M Momentum (%)": st.column_config.NumberColumn(format="%.1f%%"),
                            "3M Momentum (%)": st.column_config.NumberColumn(format="%.1f%%"),
                            "6M Momentum (%)": st.column_config.NumberColumn(format="%.1f%%")
                        },
                        hide_index=True,
                        use_container_width=True,
                        height=600
                    )
                    
                    selected_symbol = st.selectbox(
                        "Select symbol for analysis:",
                        options=st.session_state.filtered_results['Symbol'],
                        index=0
                    )
                    
                    if selected_symbol:
                        plot_technical_chart(selected_symbol)
                else:
                    st.warning("No stocks match current filters")
            
            with col2:
                st.metric("Stocks Found", len(st.session_state.filtered_results))
                
                with st.expander("Sector Distribution"):
                    if not st.session_state.filtered_results.empty:
                        sector_counts = st.session_state.filtered_results['Sector'].value_counts()
                        st.bar_chart(sector_counts)
        else:
            st.info("Please load data using the sidebar controls")
    
    with tab2:
        st.subheader("Sector Analysis")
        if not st.session_state.full_data.empty:
            sector_mom = st.session_state.full_data.groupby('Sector').agg({
                '1M Momentum (%)': 'mean',
                '3M Momentum (%)': 'mean',
                '6M Momentum (%)': 'mean'
            }).sort_values('1M Momentum (%)', ascending=False)
            
            st.dataframe(
                sector_mom.style.format("{:.1f}%"),
                use_container_width=True
            )
        else:
            st.warning("No sector data available")

if __name__ == "__main__":
    main()
