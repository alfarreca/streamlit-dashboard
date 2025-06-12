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
    .small-font {
        font-size: 14px;
    }
</style>
""", unsafe_allow_html=True)

# Default gold miners tickers
DEFAULT_MINERS = {
    'Newmont Corporation (NEM)': 'NEM',
    'Barrick Gold (GOLD)': 'GOLD',
    'Franco-Nevada (FNV)': 'FNV',
    'Agnico Eagle Mines (AEM)': 'AEM',
    'Wheaton Precious Metals (WPM)': 'WPM'
}

# Gold price data
@st.cache_data
def get_gold_price():
    try:
        gold = yf.Ticker("GC=F")
        hist = gold.history(period="1mo")
        if hist.empty:
            return None, 0
        
        current_price = hist['Close'].iloc[-1]
        prev_price = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        change_pct = ((current_price - prev_price) / prev_price) * 100
        return current_price, change_pct
    except Exception as e:
        st.error(f"Error fetching gold price: {str(e)}")
        return None, 0

# Get company fundamentals with robust error handling
@st.cache_data
def get_fundamentals(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Safely get each metric with defaults
        fundamentals = {
            'Market Cap': info.get('marketCap', None),
            'P/E': info.get('trailingPE', None),
            'P/B': info.get('priceToBook', None),
            'Debt/Equity': info.get('debtToEquity', None),
            'Current Ratio': info.get('currentRatio', None),
            'ROE': info.get('returnOnEquity', None),
            'ROA': info.get('returnOnAssets', None),
            'Profit Margin': info.get('profitMargins', None),
            'Operating Margin': info.get('operatingMargins', None),
            'Dividend Yield': info.get('dividendYield', None),
            '5Y Rev Growth': info.get('revenueGrowth', None),
            'Production (oz)': None,
            'AISC ($/oz)': None,
            'Reserves (moz)': None
        }
        
        return fundamentals
    except Exception as e:
        st.error(f"Error fetching fundamentals for {ticker}: {str(e)}")
        return None

# Get news for gold miners with robust error handling
@st.cache_data
def get_news(ticker):
    try:
        stock = yf.Ticker(ticker)
        news = stock.news or []
        
        processed_news = []
        for item in news[:5]:  # Return top 5 news items
            processed_item = {
                'title': item.get('title', 'No title available'),
                'link': item.get('link', '#'),
                'publisher': item.get('publisher', 'Unknown publisher'),
                'date': item.get('providerPublishTime', datetime.now().timestamp())
            }
            processed_news.append(processed_item)
        return processed_news
    except Exception as e:
        st.error(f"Error fetching news for {ticker}: {str(e)}")
        return []

# Load tickers from uploaded file with robust error handling
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
        st.error(f"Error reading file: {str(e)}")
        return None

# Format metric values consistently
def format_metric(value, metric_type='default'):
    if value is None:
        return 'N/A'
    
    if metric_type == 'currency':
        if abs(value) >= 1e9:
            return f"${value/1e9:,.2f}B"
        elif abs(value) >= 1e6:
            return f"${value/1e6:,.2f}M"
        else:
            return f"${value:,.2f}"
    elif metric_type == 'percentage':
        return f"{value*100:.2f}%"
    elif metric_type == 'ratio':
        return f"{value:.2f}"
    else:
        return str(value)

# Main app function
def main():
    st.title("💰 Gold Miners Fundamental Analysis")
    
    # Gold price header with error handling
    gold_price, gold_change = get_gold_price()
    if gold_price is not None:
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
            st.sidebar.info("Using default tickers due to upload issue")
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
    if not selected_miners:
        st.warning("Please select at least one company to analyze")
        return
    
    if analysis_type == "Single Company Deep Dive":
        selected_company = st.selectbox("Select a company", selected_miners)
        ticker = GOLD_MINERS[selected_company]
        
        st.header(f"{selected_company} Fundamental Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Stock price chart with error handling
            st.subheader("Price Chart")
            period = st.selectbox("Time Period", ["1mo", "3mo", "6mo", "1y", "5y"])
            
            try:
                stock_data = yf.Ticker(ticker).history(period=period)
                if not stock_data.empty:
                    fig = px.line(stock_data, x=stock_data.index, y="Close", 
                                title=f"{ticker} Price History")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("No price data available for this period")
            except Exception as e:
                st.error(f"Error loading price data: {str(e)}")
            
            # Key metrics with error handling
            st.subheader("Key Metrics")
            fundamentals = get_fundamentals(ticker)
            
            if fundamentals:
                metrics_col1, metrics_col2 = st.columns(2)
                
                with metrics_col1:
                    st.metric("Market Cap", format_metric(fundamentals['Market Cap'], 'currency'))
                    st.metric("P/E Ratio", format_metric(fundamentals['P/E'], 'ratio'))
                    st.metric("Debt/Equity", format_metric(fundamentals['Debt/Equity'], 'ratio'))
                    st.metric("ROE", format_metric(fundamentals['ROE'], 'percentage'))
                    
                with metrics_col2:
                    st.metric("Dividend Yield", format_metric(fundamentals['Dividend Yield'], 'percentage'))
                    st.metric("P/B Ratio", format_metric(fundamentals['P/B'], 'ratio'))
                    st.metric("Current Ratio", format_metric(fundamentals['Current Ratio'], 'ratio'))
                    st.metric("Profit Margin", format_metric(fundamentals['Profit Margin'], 'percentage'))
            else:
                st.warning("Could not load fundamentals for this company")
        
        with col2:
            # Company news with error handling
            st.subheader("Recent News")
            news = get_news(ticker)
            
            if not news:
                st.info("No news available for this company")
            else:
                for item in news:
                    st.markdown(f"""
                    <div class="metric-card small-font">
                        <h4><a href="{item['link']}" target="_blank">{item['title']}</a></h4>
                        <p>{item['publisher']} - {datetime.fromtimestamp(item['date']).strftime('%Y-%m-%d')}</p>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Production and cost metrics section
            st.subheader("Mining-Specific Metrics")
            st.write("""
            For accurate production and cost metrics, please refer to company reports.
            Typical metrics to consider:
            - Annual gold production (ounces)
            - All-In Sustaining Costs (AISC) per ounce
            - Mineral reserves and resources
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
            if fundamentals:
                fundamentals['Company'] = company
                fundamentals['Ticker'] = ticker
                comparison_data.append(fundamentals)
        
        if not comparison_data:
            st.error("No fundamental data available for selected companies")
            return
            
        df = pd.DataFrame(comparison_data)
        df.set_index('Company', inplace=True)
        
        # Select metrics to compare
        metrics_options = [
            'P/E', 'P/B', 'Debt/Equity', 'Current Ratio', 
            'ROE', 'ROA', 'Profit Margin', 'Dividend Yield'
        ]
        selected_metrics = st.multiselect("Select metrics to compare", metrics_options, default=metrics_options[:4])
        
        if not selected_metrics:
            st.warning("Please select at least one metric to compare")
            return
        
        # Display comparison table
        st.subheader("Fundamentals Comparison")
        comparison_df = df[['Ticker'] + selected_metrics]
        
        # Formatting dictionary for display
        format_dict = {
            'P/E': '{:.2f}',
            'P/B': '{:.2f}',
            'Debt/Equity': '{:.2f}',
            'Current Ratio': '{:.2f}',
            'ROE': '{:.2%}',
            'ROA': '{:.2%}',
            'Profit Margin': '{:.2%}',
            'Dividend Yield': '{:.2%}'
        }
        
        st.dataframe(comparison_df.style.format(format_dict))
        
        # Visual comparison
        st.subheader("Visual Comparison")
        metric_to_plot = st.selectbox("Select metric to visualize", selected_metrics)
        
        try:
            fig = px.bar(
                comparison_df.reset_index(),
                x='Company',
                y=metric_to_plot,
                color='Ticker',
                title=f"{metric_to_plot} Comparison"
            )
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Could not create visualization: {str(e)}")
        
        # Correlation analysis
        st.subheader("Correlation Analysis")
        numeric_df = comparison_df.select_dtypes(include=['float64', 'int64'])
        
        if not numeric_df.empty and len(numeric_df.columns) > 1:
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
