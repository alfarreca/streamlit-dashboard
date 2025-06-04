# Add this new chart function to the CHART FUNCTIONS section
def create_dmi_chart(hist, symbol):
    """Create a chart showing +DI, -DI, and ADX"""
    # Calculate the indicators
    high = hist['High']
    low = hist['Low']
    close = hist['Close']
    
    # Calculate True Range
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    
    # Calculate +DM and -DM
    plus_dm = high.diff()
    minus_dm = -low.diff()
    
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
    
    # Calculate +DI and -DI
    plus_di = 100 * (plus_dm.rolling(14).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr)
    
    # Calculate ADX
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.rolling(14).mean()
    
    # Create figure with secondary y-axis
    fig = go.Figure()
    
    # Price on primary y-axis
    fig.add_trace(go.Scatter(
        x=hist.index,
        y=hist['Close'],
        name='Price',
        line=dict(color='#1f77b4'),
        yaxis='y1'
    ))
    
    # +DI, -DI, ADX on secondary y-axis
    fig.add_trace(go.Scatter(
        x=hist.index,
        y=plus_di,
        name='+DI',
        line=dict(color='green'),
        yaxis='y2'
    ))
    
    fig.add_trace(go.Scatter(
        x=hist.index,
        y=minus_di,
        name='-DI',
        line=dict(color='red'),
        yaxis='y2'
    ))
    
    fig.add_trace(go.Scatter(
        x=hist.index,
        y=adx,
        name='ADX',
        line=dict(color='blue', width=2),
        yaxis='y2'
    ))
    
    # Add horizontal line at ADX 25 level (common threshold)
    fig.add_shape(
        type="line",
        x0=hist.index[0],
        y0=25,
        x1=hist.index[-1],
        y1=25,
        line=dict(color="blue", width=1, dash="dot"),
        yref="y2"
    )
    
    fig.update_layout(
        title=f'{symbol} Price with DMI Indicators',
        xaxis_title='Date',
        yaxis_title='Price',
        yaxis2=dict(
            title='DMI Values',
            overlaying='y',
            side='right',
            range=[0, max(plus_di.max(), minus_di.max(), adx.max()) * 1.1]
        ),
        hovermode='x unified',
        height=400,
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig

# Modify the display_symbol_details function to include the DMI chart
def display_symbol_details(selected_symbol):
    if not selected_symbol:
        return
    with st.spinner(f'Loading {selected_symbol} analysis...'):
        try:
            symbol_data = st.session_state.filtered_results[
                st.session_state.filtered_results["Symbol"] == selected_symbol
            ].iloc[0]
            
            st.subheader(f"{selected_symbol} Detailed Analysis")
            
            # Create tabs for different views
            tab1, tab2, tab3 = st.tabs(["Price Chart", "DMI Indicators", "Details"])
            
            with tab1:
                # Get historical data for the chart
                ticker_obj = yf.Ticker(symbol_data["YF_Symbol"])
                hist = safe_yfinance_fetch(ticker_obj)
                
                if not hist.empty:
                    st.plotly_chart(create_price_chart(hist, selected_symbol), use_container_width=True)
                else:
                    st.warning("Could not load price history for chart")
            
            with tab2:
                # Get historical data for DMI chart
                ticker_obj = yf.Ticker(symbol_data["YF_Symbol"])
                hist = safe_yfinance_fetch(ticker_obj)
                
                if not hist.empty:
                    st.plotly_chart(create_dmi_chart(hist, selected_symbol), use_container_width=True)
                    
                    # Add interpretation guide
                    with st.expander("DMI Indicators Interpretation"):
                        st.markdown("""
                        - **+DI (Green)**: Measures upward movement strength
                        - **-DI (Red)**: Measures downward movement strength
                        - **ADX (Blue)**: Measures trend strength (values > 25 suggest strong trend)
                        - **Bullish Signal**: +DI crosses above -DI
                        - **Bearish Signal**: -DI crosses above +DI
                        """)
                else:
                    st.warning("Could not load price history for DMI chart")
            
            with tab3:
                st.json(symbol_data.to_dict())
                
        except Exception as e:
            st.error(f"Error loading {selected_symbol}: {str(e)}")
