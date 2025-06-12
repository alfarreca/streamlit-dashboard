import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import io

# App configuration
st.set_page_config(
    page_title="Gold Miners Fundamental Analysis",
    page_icon="💰",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .positive {
        color: #28a745;
    }
    .negative {
        color: #dc3545;
    }
    .header {
        color: #d4af37;
    }
</style>
""", unsafe_allow_html=True)

# Default gold miners tickers
DEFAULT_MINERS = {
    'Newmont Corporation': 'NEM',
    'Barrick Gold': 'GOLD',
    'Franco-Nevada': 'FNV',
    'Agnico Eagle Mines': 'AEM',
    'Wheaton Precious Metals': 'WPM'
}

# Gold price data
@st.cache_data
def get_gold_price():
    gold = yf.Ticker("GC=F")
    hist = gold.history(period="1mo")
    current_price = hist['Close'].iloc[-1]
    prev_price = hist['Close'].iloc[-2]
    change_pct = ((current_price - prev_price) / prev_price) * 100
    return current_price, change_pct

# Get company fundamentals
@st.cache_data
def get_fundamentals(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info
    
    fundamentals = {
        'Market Cap': info.get('marketCap', 'N/A'),
        'P/E': info.get('trailingPE', 'N/A'),
        'P/B': info.get('priceToBook', 'N/A'),
        'Debt/Equity': info.get('debtToEquity', 'N/A'),
        'Current Ratio': info.get('currentRatio', 'N/A'),
        'ROE': info.get('returnOnEquity', 'N/A'),
        'ROA': info.get('returnOnAssets', 'N/A'),
        'Profit Margin': info.get('profitMargins', 'N/A'),
        'Operating Margin': info.get('operatingMargins', 'N/A'),
        'Dividend Yield': info.get('dividendYield', 'N/A'),
        '5Y Rev Growth': info.get('revenueGrowth', 'N/A'),
        'Production (oz)': 'N/A',
        'AISC (All-in Sustaining Costs)': 'N/A',
        'Reserves (moz)': 'N/A'
    }
    
    return fundamentals

# Get news for gold miners
@st.cache_data
def get_news(ticker):
    stock = yf.Ticker(ticker)
    news = stock.news
    return news[:5]  # Return top 5 news items

# Load tickers from uploaded file
def load_tickers(uploaded_file):
    try:
        df = pd.read_excel(uploaded_file)
        if 'Symbol' not in df.columns or 'Exchange' not in df.columns:
            st.error("The uploaded file must contain 'Symbol' and 'Exchange' columns")
            return None
        
        # Create a dictionary of company names and tickers
        tickers_dict = {}
        for _, row in df.iterrows():
            company_name = f"{row['Symbol']} ({row['Exchange']})"
            tickers_dict[company_name] = row['Symbol']
        
        return tickers_dict
    except Exception as e:
        st.error(f"Error reading file: {e}")
        return None

# Main app
def main():
    st.title("💰 Gold Miners Fundamental Analysis")
    
    # Gold price header
    gold_price, gold_change = get_gold_price()
    st.markdown(f"""
    <div class="metric-card">
        <h3>Gold Price: ${gold_price:,.2f} <span class="{ 'positive' if gold_change > 0 else 'negative' }">{gold_change:+.2f}%</span></h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.header("Gold Miners Selection")
    
    # File upload
    uploaded_file = st.sidebar.file_uploader(
        "Upload your tickers list (Excel with 'Symbol' and 'Exchange' columns)",
        type=["xlsx"]
    )
    
    if uploaded_file is not None:
        custom_tickers = load_tickers(uploaded_file)
        if custom_tickers:
            GOLD_MINERS = custom_tickers
        else:
            GOLD_MINERS = DEFAULT_MINERS
    else:
        GOLD_MINERS = DEFAULT_MINERS
    
    selected_miners = st.sidebar.multiselect(
        "Select companies to analyze",
        list(GOLD_MINERS.keys()),
        default=list(GOLD_MINERS.keys())[:3]
    )
    
    analysis_type = st.sidebar.radio(
        "Analysis Type",
        ("Single Company Deep Dive", "Multi-Company Comparison")
    )
    
    # Main content
    if analysis_type == "Single Company Deep Dive":
        selected_company = st.selectbox("Select a company", selected_miners)
        ticker = GOLD_MINERS[selected_company]
        
        st.header(f"{selected_company} ({ticker}) Fundamental Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Stock price chart
            st.subheader("Price Chart")
            period = st.selectbox("Time Period", ["1mo", "3mo", "6mo", "1y", "5y"])
            stock_data = yf.Ticker(ticker).history(period=period)
            fig = px.line(stock_data, x=stock_data.index, y="Close", title=f"{ticker} Price")
            st.plotly_chart(fig, use_container_width=True)
            
            # Key metrics
            st.subheader("Key Metrics")
            fundamentals = get_fundamentals(ticker)
            
            metrics_col1, metrics_col2 = st.columns(2)
            
            with metrics_col1:
                st.metric("Market Cap", f"${fundamentals['Market Cap']/1e9:,.2f}B" if isinstance(fundamentals['Market Cap'], (int, float)) else 'N/A')
                st.metric("P/E Ratio", f"{fundamentals['P/E']:.2f}" if isinstance(fundamentals['P/E'], (int, float)) else 'N/A')
                st.metric("Debt/Equity", f"{fundamentals['Debt/Equity']:.2f}" if isinstance(fundamentals['Debt/Equity'], (int, float)) else 'N/A')
                st.metric("ROE", f"{fundamentals['ROE']*100:.2f}%" if isinstance(fundamentals['ROE'], (int, float)) else 'N/A')
                
            with metrics_col2:
                st.metric("Dividend Yield", f"{fundamentals['Dividend Yield']*100:.2f}%" if isinstance(fundamentals['Dividend Yield'], (int, float)) else 'N/A')
                st.metric("P/B Ratio", f"{fundamentals['P/B']:.2f}" if isinstance(fundamentals['P/B'], (int, float)) else 'N/A')
                st.metric("Current Ratio", f"{fundamentals['Current Ratio']:.2f}" if isinstance(fundamentals['Current Ratio'], (int, float)) else 'N/A')
                st.metric("Profit Margin", f"{fundamentals['Profit Margin']*100:.2f}%" if isinstance(fundamentals['Profit Margin'], (int, float)) else 'N/A')
        
        with col2:
            # Company news
            st.subheader("Recent News")
            news = get_news(ticker)
            for item in news:
                st.markdown(f"""
                <div class="metric-card">
                    <h4><a href="{item['link']}" target="_blank">{item['title']}</a></h4>
                    <p>{item['publisher']} - {datetime.fromtimestamp(item['providerPublishTime']).strftime('%Y-%m-%d')}</p>
                </div>
                """, unsafe_allow_html=True)
            
            # Production and cost metrics
            st.subheader("Mining-Specific Metrics")
            st.write("""
            For more accurate production and cost metrics, please refer to company reports.
            """)
            
            production_data = {
                'Metric': ['Annual Production (oz)', 'AISC ($/oz)', 'Reserves (moz)'],
                'Value': ['N/A', 'N/A', 'N/A']
            }
            st.table(pd.DataFrame(production_data))
            
    else:  # Multi-Company Comparison
        st.header("Gold Miners Comparison")
        
        # Get fundamentals for all selected companies
        comparison_data = []
        for company in selected_miners:
            ticker = GOLD_MINERS[company]
            fundamentals = get_fundamentals(ticker)
            fundamentals['Company'] = company
            fundamentals['Ticker'] = ticker
            comparison_data.append(fundamentals)
        
        df = pd.DataFrame(comparison_data)
        df.set_index('Company', inplace=True)
        
        # Select metrics to compare
        metrics_options = [
            'P/E', 'P/B', 'Debt/Equity', 'Current Ratio', 
            'ROE', 'ROA', 'Profit Margin', 'Dividend Yield'
        ]
        selected_metrics = st.multiselect("Select metrics to compare", metrics_options, default=metrics_options[:4])
        
        # Display comparison table
        st.subheader("Fundamentals Comparison")
        comparison_df = df[['Ticker'] + selected_metrics]
        st.dataframe(comparison_df.style.format({
            'P/E': '{:.2f}',
            'P/B': '{:.2f}',
            'Debt/Equity': '{:.2f}',
            'Current Ratio': '{:.2f}',
            'ROE': '{:.2%}',
            'ROA': '{:.2%}',
            'Profit Margin': '{:.2%}',
            'Dividend Yield': '{:.2%}'
        }))
        
        # Visual comparison
        st.subheader("Visual Comparison")
        metric_to_plot = st.selectbox("Select metric to visualize", selected_metrics)
        
        fig = px.bar(
            comparison_df.reset_index(),
            x='Company',
            y=metric_to_plot,
            color='Ticker',
            title=f"{metric_to_plot} Comparison"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Correlation analysis
        st.subheader("Correlation Analysis")
        numeric_df = comparison_df.select_dtypes(include=['float64', 'int64'])
        if not numeric_df.empty:
            corr_matrix = numeric_df.corr()
            
            fig = px.imshow(
                corr_matrix,
                text_auto=True,
                aspect="auto",
                title="Correlation Between Metrics"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Not enough numeric data for correlation analysis")

if __name__ == "__main__":
    main()
