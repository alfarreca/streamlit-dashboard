import streamlit as st
import pandas as pd
import yfinance as yf
import time
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import requests
from bs4 import BeautifulSoup
from pytz import timezone
import numpy as np

# Configure page
st.set_page_config(
    page_title="Crypto Dashboard Pro",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
<style>
    .main {
        background-color: #0E1117;
    }
    .stDataFrame {
        border-radius: 10px;
    }
    .metric-card {
        background: #1E2130;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .header {
        color: #00D1B2;
    }
    .positive {
        color: #00D1B2;
    }
    .negative {
        color: #FF4B4B;
    }
    .ticker-header {
        font-size: 1.2rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    .refresh-button {
        margin-bottom: 1rem;
    }
    .news-item {
        padding: 10px;
        margin: 5px 0;
        background: #1E2130;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Constants
TIMEZONE = timezone('UTC')
REFRESH_INTERVAL = 300  # 5 minutes in seconds

@st.cache_data(ttl=REFRESH_INTERVAL, show_spinner=False)
def get_yahoo_crypto_data(ticker, days=7):
    """Fetch comprehensive crypto data from Yahoo Finance with enhanced caching"""
    try:
        # Clean and map ticker symbol
        base_ticker = ticker.split('.')[0].split('-')[0].upper()
        yahoo_ticker = f"{base_ticker}-USD"
        
        # Get data from Yahoo Finance
        data = yf.Ticker(yahoo_ticker)
        hist = data.history(period=f"{days}d", interval="1d")
        
        if hist.empty:
            return None, None, None
        
        # Calculate metrics
        current_price = hist['Close'].iloc[-1]
        prev_price = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        week_ago_price = hist['Close'].iloc[0] if len(hist) > 1 else current_price
        
        daily_change = ((current_price - prev_price) / prev_price) * 100
        weekly_change = ((current_price - week_ago_price) / week_ago_price) * 100
        
        return current_price, daily_change, weekly_change, hist
    
    except Exception as e:
        st.error(f"Error fetching data for {ticker}: {str(e)}")
        return None, None, None, None

@st.cache_data(ttl=3600, show_spinner=False)  # Cache news for 1 hour
def get_crypto_news():
    """Fetch recent crypto news headlines with enhanced parsing"""
    try:
        url = "https://cryptonews.com/news/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        news_items = []
        for article in soup.select('.article__title')[:8]:
            title = article.text.strip()
            link = article.find('a')['href']
            if not link.startswith('http'):
                link = f"https://cryptonews.com{link}"
            news_items.append((title, link))
        
        return news_items
    
    except Exception as e:
        st.error(f"Error fetching news: {str(e)}")
        return [("Could not fetch news. Please try again later.", "#")]

def create_price_chart(historical_data, ticker):
    """Create interactive price chart with moving average"""
    if historical_data is None or historical_data.empty:
        return None
    
    df = historical_data.reset_index()
    df['7D MA'] = df['Close'].rolling(window=7).mean()
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['Date'],
        y=df['Close'],
        name='Price',
        line=dict(color='#00D1B2', width=2)
    ))
    
    fig.add_trace(go.Scatter(
        x=df['Date'],
        y=df['7D MA'],
        name='7D MA',
        line=dict(color='#FFA15A', width=2, dash='dot')
    ))
    
    fig.update_layout(
        title=f"{ticker} Price History",
        xaxis_title="Date",
        yaxis_title="Price (USD)",
        hovermode="x unified",
        template="plotly_dark",
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    return fig

def main():
    st.title("🚀 Crypto Dashboard Pro")
    st.markdown("---")
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("Configuration")
        auto_refresh = st.checkbox("Enable auto-refresh", value=True)
        selected_interval = st.selectbox(
            "Refresh interval",
            options=["5 minutes", "15 minutes", "1 hour"],
            index=0
        )
        st.markdown("---")
        st.header("About")
        st.info("""
        This dashboard tracks cryptocurrency prices using Yahoo Finance data.
        Prices update automatically or can be refreshed manually.
        """)
    
    # Convert selected interval to seconds
    refresh_intervals = {
        "5 minutes": 300,
        "15 minutes": 900,
        "1 hour": 3600
    }
    refresh_interval = refresh_intervals[selected_interval]
    
    # Sample data with additional columns
    crypto_data = [
        {"Token ID": "UNI-USD", "Symbol": "UNI", "Project": "Uniswap"},
        {"Token ID": "AAVE-USD", "Symbol": "AAVE", "Project": "Aave"},
        {"Token ID": "DYDX", "Symbol": "DYDX", "Project": "dYdX"},
        {"Token ID": "CRV", "Symbol": "CRV", "Project": "Curve Finance"},
        {"Token ID": "ONDO", "Symbol": "ONDO", "Project": "Ondo Finance"},
        {"Token ID": "MPL", "Symbol": "MPL", "Project": "Maple Finance"},
        {"Token ID": "CFG", "Symbol": "CFG", "Project": "Centrifuge"},
        {"Token ID": "POLYX", "Symbol": "POLYX", "Project": "Polymesh"},
    ]
    
    df = pd.DataFrame(crypto_data)
    
    # Initialize columns for dynamic data
    for col in ["Price", "24h Change", "7d Trend", "Volume"]:
        if col not in df.columns:
            df[col] = np.nan
    
    # Main content
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.subheader("Live Market Data")
        
        # Refresh button
        if st.button("🔄 Refresh All Data", key="refresh_button", type="primary"):
            st.cache_data.clear()
            st.rerun()
    
    with col2:
        st.metric("Tracked Assets", len(df))
    
    with col3:
        if len(df) > 0:
            avg_change = df['24h Change'].mean()
            change_class = "positive" if not pd.isna(avg_change) and avg_change >= 0 else "negative"
            st.metric(
                "Avg 24h Change", 
                f"{avg_change:.2f}%" if not pd.isna(avg_change) else "N/A", 
                delta=f"{avg_change:.2f}%" if not pd.isna(avg_change) else None
            )
    
    # Fetch and display data
    with st.spinner("Loading market data..."):
        progress_bar = st.progress(0)
        
        for i, row in df.iterrows():
            ticker = row['Token ID']
            price, daily_change, weekly_change, hist = get_yahoo_crypto_data(ticker)
            
            if price is not None:
                df.at[i, 'Price'] = price
                df.at[i, '24h Change'] = daily_change
                df.at[i, '7d Trend'] = weekly_change
                df.at[i, 'Volume'] = hist['Volume'].iloc[-1] if hist is not None else 0
            
            progress_bar.progress((i + 1) / len(df))
    
    # Display data table
    st.dataframe(
        df.style.format({
            "Price": "${:.4f}",
            "24h Change": "{:.2f}%",
            "7d Trend": "{:.2f}%",
            "Volume": "{:,.0f}"
        }).applymap(
            lambda x: "color: #00D1B2" if isinstance(x, (int, float)) and x >= 0 else "color: #FF4B4B", 
            subset=["24h Change", "7d Trend"]
        ).bar(
            subset=["Volume"],
            color='#5DADE2'
        ),
        use_container_width=True,
        height=500,
        column_config={
            "Token ID": st.column_config.TextColumn(width="medium"),
            "Symbol": st.column_config.TextColumn(width="small"),
            "Project": st.column_config.TextColumn(width="large"),
            "Price": st.column_config.NumberColumn(width="medium", format="$%.4f"),
            "24h Change": st.column_config.NumberColumn(width="medium", format="%.2f%%"),
            "7d Trend": st.column_config.NumberColumn(width="medium", format="%.2f%%"),
            "Volume": st.column_config.NumberColumn(width="medium", format="%.0f")
        }
    )
    
    # Visualization section
    st.markdown("---")
    st.subheader("Market Analysis")
    
    tab1, tab2, tab3 = st.tabs(["Price Trends", "Performance Comparison", "Volume Analysis"])
    
    with tab1:
        selected_ticker = st.selectbox(
            "Select cryptocurrency for detailed analysis",
            options=df['Symbol'].unique(),
            index=0
        )
        
        selected_row = df[df['Symbol'] == selected_ticker].iloc[0]
        _, _, _, hist_data = get_yahoo_crypto_data(selected_row['Token ID'], days=30)
        
        if hist_data is not None:
            fig = create_price_chart(hist_data, selected_row['Symbol'])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning(f"No historical data available for {selected_row['Symbol']}")
    
    with tab2:
        fig = px.bar(
            df.sort_values('24h Change', ascending=False),
            x='Symbol',
            y=['24h Change', '7d Trend'],
            barmode='group',
            title="24h vs 7d Performance",
            color_discrete_map={
                '24h Change': '#00D1B2',
                '7d Trend': '#FFA15A'
            }
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        fig = px.scatter(
            df,
            x='24h Change',
            y='Volume',
            size='Price',
            color='Symbol',
            hover_name='Project',
            log_y=True,
            title="Volume vs Price Change"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # News section
    st.markdown("---")
    st.subheader("Latest Crypto News")
    
    news_items = get_crypto_news()
    for title, link in news_items:
        st.markdown(
            f"""
            <div class="news-item">
                <a href="{link}" target="_blank" style="color: white; text-decoration: none;">
                    📌 {title}
                </a>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # Last updated timestamp
    st.markdown("---")
    st.caption(f"Last updated: {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Auto-refresh logic
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()

if __name__ == "__main__":
    main()
