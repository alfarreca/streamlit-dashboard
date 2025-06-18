# In the sidebar section (around line 50), add this:
    st.header("Data Granularity")
    data_granularity = st.radio("Time Resolution", ["Daily", "Intraday (15min)"], index=0)

# Replace the load_stock_data function with this:
@st.cache_data
def load_stock_data(ticker, start_date, end_date, granularity="Daily"):
    try:
        # Remove any duplicate .HK suffix if present
        if ticker.endswith('.HK.HK'):
            ticker = ticker.replace('.HK.HK', '.HK')
            
        if granularity == "Daily":
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        else:  # Intraday (15min)
            data = yf.download(ticker, start=start_date, end=end_date, interval="15m", progress=False)
            
        if data.empty:
            st.error(f"No data found for {ticker}. Please verify:")
            st.error("- For HKEX stocks, use format 'XXXX.HK' (e.g., '9618.HK')")
            st.error("- Check if the ticker exists on Yahoo Finance")
            st.error("- Note: Intraday data is typically only available for recent periods")
            return None
        
        # Ensure we have numeric data and proper formatting
        data = data.apply(pd.to_numeric, errors='coerce')
        data = data.dropna()
        
        # Ensure Close prices are properly formatted
        if isinstance(data['Close'], pd.DataFrame):
            data['Close'] = data['Close'].squeeze()
            
        return data
    except Exception as e:
        st.error(f"Error downloading data for {ticker}: {e}")
        return None

# In the main logic where stock_data is loaded (around line 300), modify to:
            stock_data = load_stock_data(base_symbol, start_date, end_date, data_granularity)

# And in the comparison section (around line 380), modify to:
                        stock_data = load_stock_data(base_symbol, start_date, end_date, data_granularity)
