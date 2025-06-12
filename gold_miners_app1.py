import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime
import time

def setup_app():
    st.set_page_config(
        page_title="Gold Miners Fundamental Analysis",
        page_icon="💰",
        layout="wide"
    )
    st.markdown("""
    <style>
        .metric-card {
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .mining-metric {
            background-color: #e9f7ef;
            border-left: 4px solid #28a745;
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

MINING_METRICS_DB = {
    'NEM': {
        'Production (koz)': 5970,
        'AISC ($/oz)': 1275,
        'Reserves (moz)': 96.1,
        'Mines': 12,
        'Production Growth (%)': 2.4
    },
    'GOLD': {
        'Production (koz)': 4140,
        'AISC ($/oz)': 1256,
        'Reserves (moz)': 69,
        'Mines': 15,
        'Production Growth (%)': 1.8
    },
    'FNV': {
        'Production (koz)': 3200,
        'AISC ($/oz)': 900,
        'Reserves (moz)': 42,
        'Mines': 0,
        'Production Growth (%)': 3.2
    },
    'AEM': {
        'Production (koz)': 3340,
        'AISC ($/oz)': 1050,
        'Reserves (moz)': 22.9,
        'Mines': 8,
        'Production Growth (%)': 5.1
    }
}

DEFAULT_MINERS = {
    'Newmont Corporation (NEM)': 'NEM',
    'Barrick Gold (GOLD)': 'GOLD',
    'Franco-Nevada (FNV)': 'FNV',
    'Agnico Eagle Mines (AEM)': 'AEM'
}

def safe_fetch(callback, *args, max_retries=3, **kwargs):
    for attempt in range(max_retries):
        try:
            return callback(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                st.error(f"Operation failed after {max_retries} attempts: {str(e)}")
                return None
            time.sleep(1 * (attempt + 1))

@st.cache_data(ttl=60*15)
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

@st.cache_data(ttl=60*30)
def get_fundamentals(ticker):
    def _fetch():
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        return {
            'Market Cap': info.get('marketCap'),
            'P/E': info.get('trailingPE'),
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

def get_mining_metrics(ticker):
    return MINING_METRICS_DB.get(ticker, {
        'Production (koz)': None,
        'AISC ($/oz)': None,
        'Reserves (moz)': None,
        'Mines': None,
        'Production Growth (%)': None
    })

@st.cache_data(ttl=60*10)
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
            } for item in news[:3]]
        except:
            return []
    return safe_fetch(_fetch) or []

def load_tickers(uploaded_file):
    try:
        df = pd.read_excel(uploaded_file)
        if 'Symbol' not in df.columns or 'Exchange' not in df.columns:
            st.error("File must contain 'Symbol' and 'Exchange' columns")
            return None
        df = df.dropna(subset=['Symbol', 'Exchange'])
        if df.empty:
            st.warning("No valid tickers found in uploaded file.")
            return None
        tickers_dict = {f"{row['Symbol']} ({row['Exchange']})": row['Symbol']
                        for _, row in df.iterrows()}
        st.success(f"{len(tickers_dict)} tickers loaded from file.")
        return tickers_dict
    except Exception as e:
        st.error(f"Error reading file: {str(e)}")
        return None

def format_metric(value, style='default'):
    if value is None:
        return 'N/A'
    if style == 'currency':
        return f"${value/1e9:,.2f}B" if abs(value) >= 1e9 else f"${value/1e6:,.1f}M"
    if style == 'percentage':
        return f"{value*100:.1f}%"
    if style == 'ratio':
        return f"{value:.2f}"
    if style == 'oz':
        return f"{value:,.0f} oz"
    if style == 'koz':
        return f"{value:,.0f} koz"
    if style == 'moz':
        return f"{value:,.1f} Moz"
    if style == 'cost':
        return f"${value:,.0f}/oz"
    return str(value)

def main():
    setup_app()
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False
    st.title("💰 Gold Miners Analysis")

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

    with st.sidebar:
        st.header("Gold Miners Selection")
        uploaded_file = st.file_uploader(
            "Upload tickers list (Excel with Symbol/Exchange)",
            type=["xlsx"],
            key="file_uploader"
        )
        if uploaded_file:
            custom_tickers = load_tickers(uploaded_file)
            if custom_tickers:
                tickers = custom_tickers
            else:
                st.warning("Using default list because uploaded file was invalid or empty.")
                tickers = DEFAULT_MINERS
        else:
            tickers = DEFAULT_MINERS

        selected_miners = st.multiselect(
            "Select companies",
            list(tickers.keys()),
            default=list(tickers.keys())[:min(2, len(tickers))],
            key="miner_select"
        )
        analysis_type = st.radio(
            "Analysis Type",
            ["Single Company", "Multi-Company Compare"],
            index=0,
            key="analysis_type"
        )

    if not selected_miners:
        st.warning("Please select at least one company")
        return

    if analysis_type == "Single Company":
        render_single_company(tickers, selected_miners, gold_price)
    else:
        render_multi_company(tickers, selected_miners)

def render_single_company(tickers, selected_miners, gold_price):
    selected_company = st.selectbox("Select company", selected_miners)
    ticker = tickers[selected_company]
    st.header(f"{selected_company} Analysis")
    col1, col2 = st.columns([2, 1])

    mining_metrics = get_mining_metrics(ticker)

    with col1:
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
            except:
                st.error("Failed to load price chart")
        
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
                cols[i % 2].metric(metric, format_metric(fundamentals.get(metric), style))
        else:
            st.markdown('<div class="data-warning">Fundamental data unavailable</div>',
                        unsafe_allow_html=True)
        
        # Mining-specific metrics section
        st.subheader("Mining Operations")
        if any(value is not None for value in mining_metrics.values()):
            cols = st.columns(2)
            mining_metrics_list = [
                ('Production (koz)', 'koz'),
                ('AISC ($/oz)', 'cost'),
                ('Reserves (moz)', 'moz'),
                ('Production Growth (%)', 'percentage'),
                ('Mines', 'default')
            ]
            for i, (metric, style) in enumerate(mining_metrics_list):
                cols[i % 2].metric(
                    metric, 
                    format_metric(mining_metrics.get(metric), style),
                    help="Latest reported figures" if i == 0 else None
                )
            
            # Calculate and display margin over AISC
            if gold_price is not None and mining_metrics.get('AISC ($/oz)'):
                aisc = mining_metrics['AISC ($/oz)']
                margin = gold_price - aisc
                margin_pct = (margin / aisc) * 100
                st.markdown(f"""
                <div class="metric-card mining-metric">
                    <h4>Current Gold Price Margin Over AISC</h4>
                    <p>${margin:,.0f}/oz ({margin_pct:.1f}%)</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="data-warning">Mining metrics unavailable</div>',
                        unsafe_allow_html=True)

    with col2:
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
        
        st.subheader("Key Mining Ratios")
        if gold_price is not None and mining_metrics.get('AISC ($/oz)'):
            aisc = mining_metrics['AISC ($/oz)']
            cols = st.columns(2)
            cols[0].metric("Gold Price/AISC", f"{gold_price/aisc:.1f}x")
            if fundamentals and fundamentals.get('Market Cap') and mining_metrics.get('Reserves (moz)'):
                reserves_value = mining_metrics['Reserves (moz)'] * 1e6 * gold_price
                cols[1].metric(
                    "Market Cap/Reserves Value", 
                    f"{(fundamentals['Market Cap']/reserves_value):.2f}x",
                    help="Lower ratio may indicate better value"
                )

def render_multi_company(tickers, selected_miners):
    st.header("Company Comparison")
    progress_bar = st.progress(0)
    all_data = []
    for i, company in enumerate(selected_miners):
        progress_bar.progress((i + 1) / len(selected_miners))
        ticker = tickers[company]
        fundamentals = get_fundamentals(ticker)
        mining_metrics = get_mining_metrics(ticker)
        if fundamentals:
            combined_data = {**fundamentals, **mining_metrics}
            combined_data['Company'] = company
            combined_data['Ticker'] = ticker
            all_data.append(combined_data)
    if not all_data:
        st.error("No comparable data available")
        return
    df = pd.DataFrame(all_data).set_index('Company')
    st.subheader("Financial Metrics")
    metrics = ['P/E', 'P/B', 'Debt/Equity', 'ROE', 'Dividend Yield']
    selected_metrics = st.multiselect("Select financial metrics", metrics, default=metrics[:3])
    st.subheader("Mining Metrics")
    mining_metrics_list = ['Production (koz)', 'AISC ($/oz)', 'Reserves (moz)', 'Production Growth (%)']
    selected_mining_metrics = st.multiselect("Select mining metrics", mining_metrics_list, default=mining_metrics_list[:2])
    if selected_metrics or selected_mining_metrics:
        compare_df = df[['Ticker'] + selected_metrics + selected_mining_metrics]
        format_dict = {}
        for col in compare_df.columns:
            if col == 'P/E':
                format_dict[col] = '{:.1f}'
            elif col == 'P/B':
                format_dict[col] = '{:.2f}'
            elif col == 'Debt/Equity':
                format_dict[col] = '{:.2f}'
            elif col == 'ROE':
                format_dict[col] = '{:.1%}'
            elif col == 'Dividend Yield':
                format_dict[col] = '{:.2%}'
            elif col == 'Production (koz)':
                format_dict[col] = '{:,.0f}'
            elif col == 'AISC ($/oz)':
                format_dict[col] = '${:,.0f}'
            elif col == 'Reserves (moz)':
                format_dict[col] = '{:,.1f}'
            elif col == 'Production Growth (%)':
                format_dict[col] = '{:.1f}%'
        st.dataframe(
            compare_df.style.format(format_dict),
            height=min(400, 50 * len(compare_df))
        )
        st.subheader("Visual Comparison")
        if selected_metrics or selected_mining_metrics:
            chart_metric = st.selectbox("Select metric to visualize", selected_metrics + selected_mining_metrics)
            try:
                fig = px.bar(
                    compare_df.reset_index(),
                    x='Company',
                    y=chart_metric,
                    color='Ticker',
                    text=chart_metric,
                    title=f"{chart_metric} Comparison"
                )
                st.plotly_chart(fig, use_container_width=True)
            except:
                st.warning("Could not render comparison chart")

if __name__ == "__main__":
    main()
