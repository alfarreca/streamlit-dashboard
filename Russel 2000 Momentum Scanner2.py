# Add these imports at the top of your script
import talib
from talib import abstract

# Update the load_full_dataset() function to include RSI and MACD calculations
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
                    
                    # Calculate technical indicators
                    closes = hist['Close'].values
                    rsi = talib.RSI(closes, timeperiod=14)[-1]  # 14-day RSI
                    
                    # MACD calculation
                    macd, macdsignal, macdhist = talib.MACD(closes, 
                                                           fastperiod=12, 
                                                           slowperiod=26, 
                                                           signalperiod=9)
                    macd_value = macd[-1]
                    macd_signal = macdsignal[-1]
                    macd_hist = macdhist[-1]
                    
                    # Existing calculations...
                    close = hist['Close']
                    momentum_1m = (close.iloc[-1] / close.iloc[-21] - 1) * 100
                    momentum_3m = (close.iloc[-1] / close.iloc[-63] - 1) * 100
                    momentum_6m = (close.iloc[-1] / close.iloc[-126] - 1) * 100
                    
                    # Add to your data dictionary
                    data.append({
                        'Symbol': symbol,
                        'Name': ticker.info.get('shortName', symbol),
                        'Price': close.iloc[-1],
                        'RSI (14)': rsi,
                        'MACD': macd_value,
                        'MACD_Signal': macd_signal,
                        'MACD_Hist': macd_hist,
                        # ... rest of your existing data fields
                    })
                    
                except Exception as e:
                    continue
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Data loading failed: {str(e)}")
        return pd.DataFrame()

# Update the plot_symbol_chart() function to include RSI and MACD plots
def plot_symbol_chart(symbol):
    """Enhanced price chart with technical indicators"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period='6mo')
        
        # Calculate technical indicators
        closes = hist['Close'].values
        rsi = talib.RSI(closes, timeperiod=14)
        macd, macdsignal, macdhist = talib.MACD(closes)
        
        # Create subplots (price + volume + RSI + MACD)
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True,
                          vertical_spacing=0.03, 
                          row_heights=[0.5, 0.2, 0.15, 0.15])
        
        # Price Chart with MAs (row 1)
        fig.add_trace(go.Candlestick(
            x=hist.index,
            open=hist['Open'],
            high=hist['High'],
            low=hist['Low'],
            close=hist['Close'],
            name='Price'
        ), row=1, col=1)
        
        # Add your existing MA traces here...
        
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
            y=rsi,
            name='RSI (14)',
            line=dict(color='purple', width=1.5)
        ), row=3, col=1)
        
        # Add RSI reference lines
        fig.add_hline(y=30, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
        
        # MACD (row 4)
        fig.add_trace(go.Bar(
            x=hist.index,
            y=macdhist,
            name='MACD Histogram',
            marker_color=np.where(macdhist < 0, 'red', 'green')
        ), row=4, col=1)
        
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=macd,
            name='MACD',
            line=dict(color='blue', width=1.5)
        ), row=4, col=1)
        
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=macdsignal,
            name='Signal',
            line=dict(color='orange', width=1.5)
        ), row=4, col=1)
        
        # Update layout
        fig.update_layout(
            title=f"{symbol} Technical Analysis",
            height=800,
            showlegend=True,
            xaxis_rangeslider_visible=False,
            hovermode="x unified"
        )
        
        # Y-axis titles
        fig.update_yaxes(title_text="Price", row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)
        fig.update_yaxes(title_text="RSI (14)", row=3, col=1)
        fig.update_yaxes(title_text="MACD", row=4, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Display current indicator values
        col1, col2 = st.columns(2)
        col1.metric("RSI (14)", f"{rsi[-1]:.2f}", 
                   "Overbought" if rsi[-1] > 70 else ("Oversold" if rsi[-1] < 30 else "Neutral"))
        col2.metric("MACD", 
                   f"{macd[-1]:.2f} (Signal: {macdsignal[-1]:.2f})", 
                   "Bullish" if macd[-1] > macdsignal[-1] else "Bearish")
        
    except Exception as e:
        st.error(f"Chart error for {symbol}: {str(e)}")

# Update your dataframe display to include the new indicators
# In your main dashboard section where you display filtered_results:
st.dataframe(
    st.session_state.filtered_results[
        ['Symbol', 'Name', 'Price', 'RSI (14)', 'MACD', 
         '1M Momentum (%)', '3M Momentum (%)', '6M Momentum (%)']
    ],
    column_config={
        "RSI (14)": st.column_config.NumberColumn(
            format="%.2f",
            help="Relative Strength Index (30 = oversold, 70 = overbought)"
        ),
        "MACD": st.column_config.NumberColumn(
            format="%.2f",
            help="MACD Line (12,26,9)"
        ),
        # ... your existing column configs
    },
    hide_index=True,
    use_container_width=True
)
