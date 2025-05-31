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

# Sample Russell 2000 symbols
RUSSEL_2000_SYMBOLS = [
    'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META',
    'TSLA', 'NVDA', 'PYPL', 'ADBE', 'NFLX'
]

# --------------------------
# TECHNICAL INDICATOR FUNCTIONS
# --------------------------
def calculate_rsi(prices, period=14):
    """Calculate RSI without TA-Lib"""
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
        
    return rsi[-1] if len(rsi) > 0 else 50

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
    """Load and process Russell 2000 data"""
    try:
        data = []
        benchmark = yf.Ticker("IWM").history(period='1y')['Close']
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, symbol in enumerate(RUSSEL_2000_SYMBOLS):
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='6mo')
                
                if len(hist) < 50: continue
                
                # Calculate moving averages
                close = hist['Close'].values
                ma_20 = pd.Series(close).rolling(20).mean().iloc[-1]
                ma_50 = pd.Series(close).rolling(50).mean().iloc[-1]
                ma_200 = pd.Series(close).rolling(200).mean().iloc[-1]
                
                # Technical indicators
                rsi = calculate_rsi(close)
                macd, macd_signal, _ = calculate_macd(close)
                
                # Momentum calculations
                momentum_1m = (close[-1] / close[-21] - 1) * 100 if len(close) >= 21 else 0
                momentum_3m = (close[-1] / close[-63] - 1) * 100 if len(close) >= 63 else 0
                
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
                    '1M Momentum (%)': momentum_1m,
                    '3M Momentum (%)': momentum_3m,
                    'Sector': ticker.info.get('sector', 'Unknown'),
                    'MA_Status': 'Golden Cross' if ma_50 > ma_200 else 'Death Cross'
                })
                
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
# CHARTING FUNCTIONS
# --------------------------
def plot_technical_chart(symbol):
    """Enhanced chart with moving averages and indicators"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='3mo')
        
        if hist.empty:
            st.warning(f"No data available for {symbol}")
            return
        
        # Calculate moving averages
        hist['MA_20'] = hist['Close'].rolling(20).mean()
        hist['MA_50'] = hist['Close'].rolling(50).mean()
        hist['MA_200'] = hist['Close'].rolling(200).mean()
        
        # Calculate indicators
        closes = hist['Close'].values
        rsi = np.array([calculate_rsi(closes[:i+14]) if i+14 <= len(closes) else 50 
                      for i in range(len(closes))])
        
        # Create subplots
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                          vertical_spacing=0.05, row_heights=[0.6, 0.2, 0.2])
        
        # Price with Moving Averages
        fig.add_trace(go.Candlestick(
            x=hist.index,
            open=hist['Open'],
            high=hist['High'],
            low=hist['Low'],
            close=hist['Close'],
            name='Price'
        ), row=1, col=1)
        
        # Add moving averages
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=hist['MA_20'],
            name='20-Day MA',
            line=dict(color='blue', width=1)
        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=hist['MA_50'],
            name='50-Day MA',
            line=dict(color='purple', width=1.5)
        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=hist['MA_200'],
            name='200-Day MA',
            line=dict(color='orange', width=2)
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
            line=dict(color='green', width=1)
        ), row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
        
        # Layout
        fig.update_layout(
            title=f"{symbol} Technical Analysis",
            height=700,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis_rangeslider_visible=False,
            hovermode="x unified"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Current values display
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Price", f"${hist['Close'].iloc[-1]:.2f}")
        col2.metric("20-Day MA", f"${hist['MA_20'].iloc[-1]:.2f}")
        col3.metric("50-Day MA", f"${hist['MA_50'].iloc[-1]:.2f}")
        col4.metric("200-Day MA", f"${hist['MA_200'].iloc[-1]:.2f}")
        
        st.metric("MA Crossover Status", 
                "Golden Cross (Bullish)" if hist['MA_50'].iloc[-1] > hist['MA_200'].iloc[-1] 
                else "Death Cross (Bearish)")
        
    except Exception as e:
        st.error(f"Chart error: {str(e)}")

# --------------------------
# MAIN APP
# --------------------------
def main():
    st.set_page_config(layout="wide", page_title="Russell 2000 Scanner")
    st.title("🚀 Russell 2000 Technical Scanner")
    
    # Sidebar Filters
    with st.sidebar:
        st.header("Filters")
        params = {
            'mom_1m_min': st.slider("1M Min Momentum (%)", -30.0, 50.0, 5.0),
            'mom_3m_min': st.slider("3M Min Momentum (%)", -50.0, 100.0, 10.0),
            'rel_strength_min': st.slider("Min Rel Strength (%)", -20.0, 30.0, 0.0),
            'ma_filter': st.selectbox("MA Crossover", ['All', 'Golden Cross', 'Death Cross'])
        }
        
        if st.button("🔄 Load Data"):
            with st.spinner("Loading data..."):
                st.session_state.full_data = load_full_dataset()
                if not st.session_state.full_data.empty:
                    st.session_state.filtered_results = st.session_state.full_data[
                        (st.session_state.full_data['1M Momentum (%)'] >= params['mom_1m_min']) &
                        (st.session_state.full_data['3M Momentum (%)'] >= params['mom_3m_min']) &
                        (st.session_state.full_data['Rel Strength (%)'] >= params['rel_strength_min'])
                    ]
                    if params['ma_filter'] != 'All':
                        st.session_state.filtered_results = st.session_state.filtered_results[
                            st.session_state.filtered_results['MA_Status'] == params['ma_filter']
                        ]
                    st.session_state.filtered_results = st.session_state.filtered_results.sort_values('1M Momentum (%)', ascending=False)
                    st.success("Data loaded!")
    
    # Main Display
    if not st.session_state.full_data.empty:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.subheader("Filtered Results")
            if not st.session_state.filtered_results.empty:
                st.dataframe(
                    st.session_state.filtered_results[
                        ['Symbol', 'Name', 'Price', '20_MA', '50_MA', '200_MA', 
                         'RSI (14)', '1M Momentum (%)', '3M Momentum (%)']
                    ],
                    column_config={
                        "Price": st.column_config.NumberColumn(format="$%.2f"),
                        "20_MA": st.column_config.NumberColumn(format="$%.2f"),
                        "50_MA": st.column_config.NumberColumn(format="$%.2f"),
                        "200_MA": st.column_config.NumberColumn(format="$%.2f"),
                        "RSI (14)": st.column_config.NumberColumn(format="%.1f"),
                        "1M Momentum (%)": st.column_config.NumberColumn(format="%.1f%%"),
                        "3M Momentum (%)": st.column_config.NumberColumn(format="%.1f%%")
                    },
                    hide_index=True,
                    use_container_width=True,
                    height=600
                )
                
                selected_symbol = st.selectbox(
                    "Select symbol:",
                    options=st.session_state.filtered_results['Symbol'],
                    index=0
                )
                
                if selected_symbol:
                    plot_technical_chart(selected_symbol)
            else:
                st.warning("No stocks match filters")
        
        with col2:
            st.metric("Stocks Found", len(st.session_state.filtered_results))
            with st.expander("Sectors"):
                if not st.session_state.filtered_results.empty:
                    sector_counts = st.session_state.filtered_results['Sector'].value_counts()
                    st.bar_chart(sector_counts)
    else:
        st.info("Please load data using sidebar controls")

if __name__ == "__main__":
    main()
