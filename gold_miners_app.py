import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime
import time

# App configuration with loading state management
def setup_app():
    st.set_page_config(
        page_title="Gold Miners Fundamental Analysis",
        page_icon="💰",
        layout="wide"
    )
    
    # Custom CSS with loading spinner
    st.markdown("""
    <style>
        .metric-card {
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #3498db;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 2s linear infinite;
            margin: 20px auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .data-warning {
            color: #856404;
            background-color: #fff3cd;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
        }
    </style>
    """, unsafe_allow_html=True)

# Default tickers with loading safeguards
DEFAULT_MINERS = {
    'Newmont Corporation (NEM)': 'NEM',
    'Barrick Gold (GOLD)': 'GOLD',
    'Franco-Nevada (FNV)': 'FNV',
    'Agnico Eagle Mines (AEM)': 'AEM'
}

# Safe data fetching with timeouts
def safe_fetch(callback, *args, max_retries=3, **kwargs):
    for attempt in range(max_retries):
        try:
            return callback(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                st.error(f"Operation failed after {max_retries} attempts: {str(e)}")
                return None
            time.sleep(1 * (attempt + 1))

# Gold price with loading state
@st.cache_data(ttl=60*15)  # 15 minute cache
def get_gold_price():
    def _fetch():
        gold = yf.Ticker("GC=F")
        hist = gold.history(period="1mo")
        if hist.empty:
            return None, 0
        current_price = hist['Close'].iloc[-1]
        prev_price = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        change_pct = ((current_price - prev_price) / prev_price) * 100
        return current_price, change_pct
    return safe_fetch(_fetch)

# Company fundamentals with error boundaries
@st.cache_data(ttl=60*30)  # 30 minute cache
def get_fundamentals(ticker):
    def _fetch():
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        
        return {
            'Market Cap': info.get('marketCap'),
            'P/E': info.get('trailingPE'),  # Fixed typo from 'trailingPE'
            'P/B': info.get('priceToBook'),
            'Debt/Equity': info.get('debtToEquity'),
            'Current Ratio': info.get('currentRatio'),
            'ROE': info.get('returnOnEquity'),
            'ROA': info.get('returnOnAssets'),
            'Profit Margin': info.get('profitMargins'),
            'Dividend Yield': info.get('dividendYield'),
            '5Y Rev Growth': info.get('revenueGrowth')
        }
    return safe_fetch(_fetch)

# News with safe defaults
@st.cache_data(ttl=60*10)  # 10 minute cache
def get_news(ticker):
    def _fetch():
        try:
            stock = yf.Ticker(ticker)
            news = stock.news or []
            return [{
                'title': item.get('title', 'No title available'),
                'link': item.get('link', '#'),
                'publisher': item.get('publisher', 'Unknown'),
                'date': item.get('providerPublishTime', time.time())
            } for item in news[:3]]  # Only first 3 news items
        except:
            return []
    return safe_fetch(_fetch) or []

# File upload with validation
def load_tickers(uploaded_file):
    try:
        df = pd.read_excel(uploaded_file)
        if {'Symbol', 'Exchange'}.issubset(df.columns):
            return {f"{row['Symbol']} ({row['Exchange']})": row['Symbol'] 
                   for _, row in df.iterrows()}
        st.error("File must contain 'Symbol' and 'Exchange' columns")
    except Exception as e:
        st.error(f"Error reading file: {str(e)}")
    return None

# Formatting utilities
def format_metric(value, style='default'):
    if value is None:
        return 'N/A'
    if style == 'currency':
        return f"${value/1e9:,.2f}B" if abs(value) >= 1e9 else f"${value/1e6:,.1f}M"
    if style == 'percentage':
        return f"{value*100:.1f}%"
    if style == 'ratio':
        return f"{value:.2f}"
    return str(value)

# Main app with loading states
def main():
    setup_app()
    
    # Initialize session state for loading control
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False
    
    # Header with loading awareness
    st.title("💰 Gold Miners Analysis")
    
    # Gold price display with loading state
    with st.spinner("Loading market data..."):
        gold_price, gold_change = get_gold_price() or (None, 0)
    
    if gold_price is not None:
        st.markdown(f"""
        <div class="metric-card">
            <h3>Gold Price: ${gold_price:,.2f} 
            <span style="color: {'#28a745' if gold_change > 0 else '#dc3545'}">
            {gold_change:+.2f}%</span></h3>
        </div>
        """, unsafe_allow_html=True)
    
    # Sidebar with controlled rendering
    with st.sidebar:
        st.header("Gold Miners Selection")
        
        uploaded_file = st.file_uploader(
            "Upload tickers list (Excel with Symbol/Exchange)",
            type=["xlsx"],
            key="file_uploader"
        )
        
        if uploaded_file:
            custom_tickers = load_tickers(uploaded_file)
            tickers = custom_tickers if custom_tickers else DEFAULT_MINERS
        else:
            tickers = DEFAULT_MINERS
        
        selected_miners = st.multiselect(
            "Select companies",
            list(tickers.keys()),
            default=list(tickers.keys())[:2],
            key="miner_select"
        )
        
        analysis_type = st.radio(
            "Analysis Type",
            ["Single Company", "Multi-Company Compare"],
            index=0,
            key="analysis_type"
        )
    
    # Main content with loading guards
    if not selected_miners:
        st.warning("Please select at least one company")
        return
    
    if analysis_type == "Single Company":
        render_single_company(tickers, selected_miners)
    else:
        render_multi_company(tickers, selected_miners)

# Single company view with error boundaries
def render_single_company(tickers, selected_miners):
    selected_company = st.selectbox("Select company", selected_miners)
    ticker = tickers[selected_company]
    
    st.header(f"{selected_company} Analysis")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Price chart with loading state
        st.subheader("Price Performance")
        period = st.selectbox("Time Period", ["1mo", "3mo", "6mo", "1y"], index=2)
        
        with st.spinner(f"Loading {ticker} price data..."):
            try:
                stock_data = yf.Ticker(ticker).history(period=period)
                if not stock_data.empty:
                    fig = px.line(stock_data, x=stock_data.index, y="Close")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.markdown('<div class="data-warning">No price data available</div>', 
                              unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Failed to load price chart: {str(e)}")
        
        # Fundamentals display
        st.subheader("Fundamentals")
        with st.spinner("Loading financial data..."):
            fundamentals = get_fundamentals(ticker) or {}
        
        if fundamentals:
            cols = st.columns(2)
            metrics = [
                ('Market Cap', 'currency'),
                ('P/E', 'ratio'),
                ('P/B', 'ratio'),
                ('Debt/Equity', 'ratio'),
                ('ROE', 'percentage'),
                ('Dividend Yield', 'percentage')
            ]
            
            for i, (metric, style) in enumerate(metrics):
                cols[i%2].metric(metric, format_metric(fundamentals.get(metric), style)
        else:
            st.markdown('<div class="data-warning">Fundamental data unavailable</div>', 
                       unsafe_allow_html=True)
    
    with col2:
        # News section
        st.subheader("Recent News")
        with st.spinner("Checking for news..."):
            news = get_news(ticker)
        
        if not news:
            st.info("No recent news found")
        else:
            for item in news:
                st.markdown(f"""
                <div class="metric-card">
                    <p><strong><a href="{item['link']}" target="_blank">{item['title']}</a></strong></p>
                    <small>{item['publisher']} • {datetime.fromtimestamp(item['date']).strftime('%b %d, %Y')}</small>
                </div>
                """, unsafe_allow_html=True)
        
        # Mining metrics placeholder
        st.subheader("Production Metrics")
        st.info("""
        For detailed production metrics:
        - Annual production (ounces)
        - All-in sustaining costs
        - Reserve estimates
        """)

# Multi-company comparison with loading states
def render_multi_company(tickers, selected_miners):
    st.header("Company Comparison")
    
    # Load all data first with progress
    progress_bar = st.progress(0)
    all_data = []
    
    for i, company in enumerate(selected_miners):
        progress_bar.progress((i + 1) / len(selected_miners), 
                            f"Loading {company} data...")
        ticker = tickers[company]
        fundamentals = get_fundamentals(ticker)
        if fundamentals:
            fundamentals['Company'] = company
            fundamentals['Ticker'] = ticker
            all_data.append(fundamentals)
    
    if not all_data:
        st.error("No comparable data available")
        return
    
    df = pd.DataFrame(all_data).set_index('Company')
    
    # Comparison metrics
    st.subheader("Financial Metrics")
    metrics = ['P/E', 'P/B', 'Debt/Equity', 'ROE', 'Dividend Yield']
    selected_metrics = st.multiselect("Select metrics", metrics, default=metrics[:3])
    
    if selected_metrics:
        compare_df = df[['Ticker'] + selected_metrics]
        st.dataframe(
            compare_df.style.format({
                'P/E': '{:.1f}',
                'P/B': '{:.2f}',
                'Debt/Equity': '{:.2f}',
                'ROE': '{:.1%}',
                'Dividend Yield': '{:.2%}'
            }),
            height=min(400, 50 * len(compare_df))
        )
        
        # Visualization
        st.subheader("Visual Comparison")
        chart_metric = st.selectbox("Chart metric", selected_metrics)
        
        try:
            fig = px.bar(
                compare_df.reset_index(),
                x='Company',
                y=chart_metric,
                color='Ticker',
                text=chart_metric
            )
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.warning(f"Could not render comparison chart: {str(e)}")

if __name__ == "__main__":
    main()
