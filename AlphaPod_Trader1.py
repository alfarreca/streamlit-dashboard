# --- Updated Earnings Data Fetching ---
def fetch_earnings_dates(ticker):
    """Get accurate earnings dates from yfinance"""
    try:
        stock = yf.Ticker(ticker)
        dates = stock.calendar
        if dates is not None and not dates.empty:
            next_earnings = dates.iloc[0]['Earnings Date']
            if isinstance(next_earnings, pd.Timestamp):
                return next_earnings.strftime('%Y-%m-%d')
            elif isinstance(next_earnings, list):
                return next_earnings[0].strftime('%Y-%m-%d')
        return None
    except Exception as e:
        st.error(f"Error fetching earnings date: {str(e)}")
        return None

# --- Modified Stock Card ---
def render_stock_card(ticker, earnings_data):
    """Updated with verified earnings date"""
    verified_date = fetch_earnings_dates(ticker)
    display_date = verified_date or earnings_data.get('reportDate', 'N/A')
    
    with st.expander(f"{ticker}", expanded=False):
        tab1, tab2, tab3 = st.tabs(["Overview", "Chart", "Fundamentals"])
        
        with tab1:
            cols = st.columns(2)
            with cols[0]:
                st.metric("EPS Surprise", f"{earnings_data.get('surprisePercent', 0):.2f}%")
                st.metric("Revenue", f"${earnings_data.get('revenue', 0)/1e9:.2f}B")
                
            with cols[1]:
                current_price = get_historical_data(ticker, "1d")['Close'].iloc[-1]
                st.metric("Current Price", f"${current_price:,.2f}")
                st.metric("Next Earnings", display_date)  # Updated here
                
            if st.button("📊 Full Analysis", key=f"analyze_{ticker}"):
                st.session_state.current_ticker = ticker
                
            if st.button("➕ Watchlist", key=f"watch_{ticker}"):
                if ticker not in st.session_state.watchlist:
                    st.session_state.watchlist.append(ticker)
                    st.toast(f"Added {ticker} to watchlist")
        
        # ... [rest of the function remains the same]
