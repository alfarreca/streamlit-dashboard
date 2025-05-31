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
                    
                    # Price and moving averages
                    close = hist['Close'].values
                    ma_20 = pd.Series(close).rolling(20).mean().iloc[-1]
                    ma_50 = pd.Series(close).rolling(50).mean().iloc[-1]
                    ma_200 = pd.Series(close).rolling(200).mean().iloc[-1]
                    
                    # Technical indicators
                    rsi = calculate_rsi(close)
                    macd, macd_signal, macd_hist = calculate_macd(close)
                    
                    # Momentum calculations
                    momentum_1m = (close[-1] / close[-21] - 1) * 100
                    momentum_3m = (close[-1] / close[-63] - 1) * 100
                    momentum_6m = (close[-1] / close[-126] - 1) * 100
                    
                    # Relative strength vs benchmark
                    benchmark_1m = (benchmark.iloc[-1] / benchmark.iloc[-21] - 1) * 100
                    rel_strength = momentum_1m - benchmark_1m
                    
                    # Volatility and volume
                    volatility = pd.Series(close).pct_change().std() * np.sqrt(21) * 100
                    avg_volume = hist['Volume'].mean()
                    
                    data.append({
                        'Symbol': symbol,
                        'Name': ticker.info.get('shortName', symbol),
                        'Price': close[-1],
                        '20_MA': ma_20,
                        '50_MA': ma_50,
                        '200_MA': ma_200,
                        'RSI (14)': rsi,
                        'MACD': macd,
                        'MACD_Signal': macd_signal,
                        'MACD_Hist': macd_hist,
                        '1M Momentum (%)': momentum_1m,
                        '3M Momentum (%)': momentum_3m,
                        '6M Momentum (%)': momentum_6m,
                        'Rel Strength (%)': rel_strength,
                        'Volatility (%)': volatility,
                        'Avg Volume': avg_volume,
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
    
    return filtered.sort_values('1M Momentum (%)', ascending=False)

# --------------------------
# VISUALIZATION FUNCTIONS
# --------------------------
def plot_symbol_chart(symbol):
    """Enhanced price chart with technical indicators"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='6mo')
        closes = hist['Close'].values
        
        # Calculate technical indicators
        rsi_values = calculate_rsi(closes, return_all=True)
        macd_values, macd_signal, macd_hist = calculate_macd(closes, return_all=True)
        
        # Create subplots
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True,
                          vertical_spacing=0.03, 
                          row_heights=[0.5, 0.2, 0.15, 0.15])
        
        # Price Chart (row 1)
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
            y=hist['Close'].rolling(20).mean(),
            name='20-Day MA',
            line=dict(color='blue', width=1)
        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=hist['Close'].rolling(50).mean(),
            name='50-Day MA',
            line=dict(color='purple', width=1.5)
        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=hist['Close'].rolling(200).mean(),
            name='200-Day MA',
            line=dict(color='orange', width=2)
        ), row=1, col=1)
        
        # Volume (row 2)
        fig.add_trace(go.Bar(
            x=hist.index,
            y=hist['Volume'],
            name='Volume',
            marker_color='rgba(100, 100, 255, 0.6)'
        ), row=2, col=1)
        
        # RSI (row 3)
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=rsi_values,
            name='RSI (14)',
            line=dict(color='purple', width=1.5)
        ), row=3, col=1)
        
        fig.add_hline(y=30, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
        
        # MACD (row 4)
        fig.add_trace(go.Bar(
            x=hist.index,
            y=macd_hist,
            name='MACD Histogram',
            marker_color=np.where(macd_hist < 0, 'red', 'green')
        ), row=4, col=1)
        
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=macd_values,
            name='MACD',
            line=dict(color='blue', width=1.5)
        ), row=4, col=1)
        
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=macd_signal,
            name='Signal',
            line=dict(color='orange', width=1.5)
        ), row=4, col=1)
        
        # Layout
        fig.update_layout(
            title=f"{symbol} Technical Analysis",
            height=800,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis_rangeslider_visible=False,
            hovermode="x unified"
        )
        
        # Y-axis titles
        fig.update_yaxes(title_text="Price", row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)
        fig.update_yaxes(title_text="RSI (14)", row=3, col=1)
        fig.update_yaxes(title_text="MACD", row=4, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Current indicator values
        col1, col2 = st.columns(2)
        col1.metric("RSI (14)", f"{rsi_values[-1]:.2f}", 
                   "Overbought" if rsi_values[-1] > 70 else ("Oversold" if rsi_values[-1] < 30 else "Neutral"))
        col2.metric("MACD", 
                   f"{macd_values[-1]:.2f} (Signal: {macd_signal[-1]:.2f})", 
                   "Bullish" if macd_values[-1] > macd_signal[-1] else "Bearish")
        
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
                            ['Symbol', 'Name', 'Price', 'RSI (14)', 'MACD',
                             '1M Momentum (%)', '3M Momentum (%)', '6M Momentum (%)',
                             'MA_Status', 'Sector']
                        ].sort_values('1M Momentum (%)', ascending=False),
                        column_config={
                            "Price": st.column_config.NumberColumn(format="$%.2f"),
                            "RSI (14)": st.column_config.NumberColumn(format="%.2f"),
                            "MACD": st.column_config.NumberColumn(format="%.2f"),
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
            sector_mom = st.session_state.full_data.groupby('Sector').agg({
                '1M Momentum (%)': 'mean',
                '3M Momentum (%)': 'mean',
                '6M Momentum (%)': 'mean'
            }).sort_values('1M Momentum (%)', ascending=False)
            
            st.dataframe(
                sector_mom,
                use_container_width=True
            )
            
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
