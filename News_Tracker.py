import streamlit as st
import feedparser
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
import plotly.express as px
import requests
from bs4 import BeautifulSoup
import re

# Initialize NLTK
nltk.download('vader_lexicon')
nltk.download('punkt')

# Set up the app
st.set_page_config(page_title="Global News & Market Tracker", layout="wide")
st.title("🌍 Global News & Market Impact Tracker")
st.markdown("""
Tracking the most important financial and geopolitical news from the last 24 hours with market impact analysis.
""")

# Initialize session state
if 'processed' not in st.session_state:
    st.session_state.processed = False
if 'all_news' not in st.session_state:
    st.session_state.all_news = []
if 'market_data' not in st.session_state:
    st.session_state.market_data = {}

# News categories
NEWS_CATEGORIES = {
    'financial': {
        'keywords': [
            'stock', 'market', 'earnings', 'financial', 'economy', 'economic',
            'investment', 'investor', 'IPO', 'merger', 'acquisition', 'buyout',
            'quarterly', 'annual', 'results', 'forecast', 'outlook', 'guidance',
            'dow', 'nasdaq', 's&p', 's&p 500', 'fed', 'interest rate', 'inflation',
            'recession', 'growth', 'gdp', 'unemployment', 'trade', 'tariff',
            'currency', 'dollar', 'euro', 'yen', 'pound', 'bitcoin', 'crypto',
            'commodity', 'oil', 'gold', 'silver', 'bond', 'yield', 'treasury',
            'sec', 'regulation', 'lawsuit', 'fine', 'settlement', 'dividend',
            'buyback', 'shareholder', 'ceo', 'cfo', 'executive', 'layoff',
            'hire', 'job', 'bank', 'jpmorgan', 'goldman', 'morgan stanley',
            'hedge fund', 'private equity', 'venture capital'
        ],
        'sources': {
            'Google Finance': 'https://news.google.com/rss/headlines/section/topic/BUSINESS',
            'Yahoo Finance': 'https://finance.yahoo.com/news/rssindex',
            'Reuters Business': 'http://feeds.reuters.com/reuters/businessNews',
            'Bloomberg Markets': 'https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en'
        }
    },
    'geopolitical': {
        'keywords': [
            'war', 'conflict', 'treaty', 'sanction', 'embargo', 'diplomacy',
            'summit', 'g7', 'g20', 'united nations', 'nato', 'european union',
            'trade war', 'china', 'russia', 'ukraine', 'middle east', 'iran',
            'north korea', 'south china sea', 'taiwan', 'hong kong',
            'brexit', 'eurozone', 'imf', 'world bank', 'wto', 'opec',
            'energy security', 'food security', 'supply chain', 'shipping',
            'critical minerals', 'semiconductors', 'technology transfer',
            'cyber attack', 'espionage', 'election', 'political', 'government',
            'regulation', 'legislation', 'tax', 'subsidy', 'tariff', 'import',
            'export', 'sanction', 'ban', 'restriction', 'alliance', 'partnership'
        ],
        'sources': {
            'Reuters World': 'http://feeds.reuters.com/Reuters/worldNews',
            'AP Top World': 'https://news.google.com/rss/headlines/section/topic/WORLD',
            'BBC World': 'http://feeds.bbci.co.uk/news/world/rss.xml',
            'Foreign Policy': 'https://foreignpolicy.com/feed/'
        }
    }
}

# Enhanced ticker pattern matching
TICKER_PATTERN = r'\b([A-Z]{2,4})\b(?=\s*\(?\d*\)?)'

# Get all S&P 500 tickers for reference
@st.cache_data
def get_sp500_tickers():
    table = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
    df = table[0]
    return df['Symbol'].tolist()

# Commodities and geopolitical-sensitive assets
GEOPOLITICAL_ASSETS = {
    'OIL': 'CL=F',  # Crude Oil
    'GOLD': 'GC=F',
    'SILVER': 'SI=F',
    'NATURAL GAS': 'NG=F',
    'WHEAT': 'KE=F',
    'CORN': 'ZC=F',
    'USD': 'DX-Y.NYB',  # USD Index
    'BITCOIN': 'BTC-USD',
    'TREASURIES': '^TNX'  # 10-Year Yield
}

# News relevance filtering
def is_relevant_news(text, category):
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in NEWS_CATEGORIES[category]['keywords'])

# Enhanced ticker extraction
def extract_tickers(text, known_tickers):
    # Find all potential ticker matches
    potential_tickers = re.findall(TICKER_PATTERN, text)
    
    # Filter for known tickers
    valid_tickers = []
    for ticker in potential_tickers:
        if ticker in known_tickers:
            valid_tickers.append(ticker)
    
    # Also check for company names that might be mentioned
    company_names = {
        'apple': 'AAPL',
        'microsoft': 'MSFT',
        'amazon': 'AMZN',
        'google': 'GOOGL',
        'meta': 'META',
        'tesla': 'TSLA',
        'nvidia': 'NVDA',
        'exxon': 'XOM',
        'chevron': 'CVX',
        'lockheed': 'LMT',
        'boeing': 'BA',
        'raytheon': 'RTX'
    }
    
    text_lower = text.lower()
    for name, ticker in company_names.items():
        if name in text_lower and ticker not in valid_tickers:
            valid_tickers.append(ticker)
    
    return list(set(valid_tickers))

# News fetching with strict 24-hour window
@st.cache_data(ttl=3600, show_spinner="Fetching latest news...")
def fetch_all_news():
    sp500_tickers = get_sp500_tickers()
    all_news = []
    cutoff_time = datetime.now() - timedelta(hours=24)
    
    # Fetch financial news
    for source, url in NEWS_CATEGORIES['financial']['sources'].items():
        feed = feedparser.parse(url)
        for entry in feed.entries[:50]:  # Limit to 50 items per source
            pub_date = datetime(*entry.published_parsed[:6])
            if pub_date >= cutoff_time and is_relevant_news(entry.title, 'financial'):
                tickers = extract_tickers(entry.title + " " + entry.get('summary', ''), sp500_tickers)
                all_news.append({
                    'title': entry.title,
                    'link': entry.link,
                    'published': pub_date.strftime('%Y-%m-%d %H:%M'),
                    'source': source,
                    'tickers': tickers,
                    'category': 'financial',
                    'has_market_data': len(tickers) > 0
                })
    
    # Fetch geopolitical news
    for source, url in NEWS_CATEGORIES['geopolitical']['sources'].items():
        feed = feedparser.parse(url)
        for entry in feed.entries[:50]:  # Limit to 50 items per source
            pub_date = datetime(*entry.published_parsed[:6])
            if pub_date >= cutoff_time and is_relevant_news(entry.title, 'geopolitical'):
                # Geopolitical news affects commodities and indices
                affected_assets = []
                text_lower = (entry.title + " " + entry.get('summary', '')).lower()
                
                for asset in GEOPOLITICAL_ASSETS:
                    if asset.lower() in text_lower:
                        affected_assets.append(GEOPOLITICAL_ASSETS[asset])
                
                all_news.append({
                    'title': entry.title,
                    'link': entry.link,
                    'published': pub_date.strftime('%Y-%m-%d %H:%M'),
                    'source': source,
                    'tickers': affected_assets,
                    'category': 'geopolitical',
                    'has_market_data': len(affected_assets) > 0
                })
    
    # Sort by most recent first
    all_news.sort(key=lambda x: x['published'], reverse=True)
    return all_news

# Get market data for tickers and commodities
@st.cache_data(ttl=1800, show_spinner="Fetching market data...")
def get_market_data(tickers):
    data = {}
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")
            info = stock.info
            
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
                prev_close = info.get('previousClose', hist['Close'].iloc[-1] if len(hist) > 1 else current_price)
                change_pct = ((current_price - prev_close) / prev_close) * 100 if prev_close else 0
                
                data[ticker] = {
                    'price': current_price,
                    'change': change_pct,
                    'name': info.get('shortName', ticker),
                    'pe_ratio': info.get('trailingPE'),
                    'sector': info.get('sector', 'Commodity' if '=F' in ticker else 'Index'),
                    'news_sentiment': None,
                    'type': 'commodity' if '=F' in ticker else ('index' if '^' in ticker else 'stock')
                }
        except Exception as e:
            continue
    return data

# Sentiment analysis
def analyze_news_sentiment(news_items, market_data):
    sia = SentimentIntensityAnalyzer()
    
    # Create sentiment scores for each ticker
    ticker_sentiments = {}
    for item in news_items:
        if not item['tickers']:
            continue
            
        # Simple sentiment analysis
        sentiment = sia.polarity_scores(item['title'])
        
        # Apply to each mentioned ticker
        for ticker in item['tickers']:
            if ticker in market_data:
                if ticker not in ticker_sentiments:
                    ticker_sentiments[ticker] = []
                ticker_sentiments[ticker].append(sentiment['compound'])
    
    # Calculate average sentiment per ticker
    for ticker, scores in ticker_sentiments.items():
        market_data[ticker]['news_sentiment'] = sum(scores) / len(scores) if scores else 0
    
    return market_data

# Format price display
def format_price(price):
    if isinstance(price, float):
        return f"${price:.2f}"
    return f"${price}"

# Main processing function
def process_news():
    with st.spinner("Processing global news and market data..."):
        # Fetch and filter news
        all_news = fetch_all_news()
        
        # Get all unique tickers/commodities mentioned
        all_tickers = list(set(ticker for item in all_news for ticker in item['tickers']))
        all_tickers += list(GEOPOLITICAL_ASSETS.values())  # Always include key commodities
        
        # Get market data
        market_data = get_market_data(all_tickers) if all_tickers else {}
        
        # Analyze sentiment impact
        if market_data:
            market_data = analyze_news_sentiment(all_news, market_data)
        
        # Store results
        st.session_state.all_news = all_news
        st.session_state.market_data = market_data
        st.session_state.processed = True

# Process data if not already done
if not st.session_state.processed:
    process_news()

# Display controls in sidebar
with st.sidebar:
    st.header("Filters")
    news_category = st.multiselect(
        "News Categories",
        ['financial', 'geopolitical'],
        default=['financial', 'geopolitical']
    )
    
    show_only_market_news = st.checkbox("Only show news with market data", True)
    min_sentiment = st.slider("Minimum sentiment score", -1.0, 1.0, -1.0, 0.1)
    
    asset_types = st.multiselect(
        "Asset Types",
        ['stock', 'commodity', 'index'],
        default=['stock', 'commodity', 'index']
    )
    
    if st.button("Refresh Data"):
        st.cache_data.clear()
        st.session_state.processed = False
        st.rerun()

# Display news
st.header("Global News & Market Impact (Last 24 Hours)")

if not st.session_state.all_news:
    st.warning("No relevant news found in the last 24 hours.")
else:
    displayed_count = 0
    
    for item in st.session_state.all_news:
        # Apply filters
        if item['category'] not in news_category:
            continue
        if show_only_market_news and not item['tickers']:
            continue
            
        # Display the news item
        with st.expander(f"{item['title']} ({item['source']} - {item['published']})"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                # Try to get article summary
                try:
                    response = requests.get(item['link'], timeout=5)
                    soup = BeautifulSoup(response.text, 'html.parser')
                    paragraphs = soup.find_all('p')
                    summary = ' '.join(p.get_text() for p in paragraphs[:3])
                    st.markdown(f"**Summary**: {summary[:500]}...")
                except:
                    st.markdown("*Could not fetch article content*")
                
                st.markdown(f"[Read full article]({item['link']})")
                st.markdown(f"**Category**: {item['category'].capitalize()}")
            
            with col2:
                if item['tickers']:
                    st.markdown("**Related Assets:**")
                    for ticker in item['tickers']:
                        if ticker in st.session_state.market_data:
                            data = st.session_state.market_data[ticker]
                            if data['type'] not in asset_types:
                                continue
                                
                            change_color = "green" if data['change'] >= 0 else "red"
                            change_icon = "↑" if data['change'] >= 0 else "↓"
                            
                            st.markdown(
                                f"""
                                **{ticker}** ({data['name']})
                                - Price: {format_price(data['price'])}
                                - Change: <span style='color:{change_color}'>{change_icon} {abs(data['change']):.2f}%</span>
                                - Type: {data['type'].capitalize()}
                                - Sentiment: {data['news_sentiment']:.2f if data['news_sentiment'] is not None else 'N/A'}
                                """,
                                unsafe_allow_html=True
                            )
                        else:
                            st.markdown(f"- {ticker} (data unavailable)")
            
            displayed_count += 1
    
    if displayed_count == 0:
        st.warning("No news matches current filters.")

# Market impact visualization
if st.session_state.market_data:
    st.header("Global Market Impact Analysis")
    
    # Prepare data for visualization
    impact_data = []
    for ticker, data in st.session_state.market_data.items():
        if data['type'] in asset_types and (data['news_sentiment'] is None or data['news_sentiment'] >= min_sentiment):
            impact_data.append({
                'Ticker': ticker,
                'Name': data['name'],
                'Price': data['price'],
                'Daily Change (%)': data['change'],
                'P/E Ratio': data['pe_ratio'],
                'News Sentiment': data['news_sentiment'] if data['news_sentiment'] is not None else 0,
                'Type': data['type'],
                'Sector': data['sector']
            })
    
    if impact_data:
        df = pd.DataFrame(impact_data)
        
        # Sentiment vs Price Change by Type
        st.subheader("News Sentiment vs Price Movement")
        fig = px.scatter(
            df,
            x='News Sentiment',
            y='Daily Change (%)',
            color='Type',
            hover_data=['Name', 'Sector'],
            title="How News Correlates with Market Movements",
            color_discrete_map={
                'stock': '#636EFA',
                'commodity': '#EF553B',
                'index': '#00CC96'
            }
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Top movers by category
        st.subheader("Top Market Movers by Category")
        
        for asset_type in asset_types:
            if asset_type in df['Type'].unique():
                st.markdown(f"**{asset_type.capitalize()}s**")
                type_df = df[df['Type'] == asset_type].sort_values('Daily Change (%)', key=abs, ascending=False)
                st.dataframe(type_df.head(10), hide_index=True)
    else:
        st.warning("No market impact data meets the current criteria.")

# Geopolitical risk dashboard
if 'geopolitical' in news_category:
    st.header("Geopolitical Risk Dashboard")
    
    # Get key commodities data
    commodities_data = []
    for name, ticker in GEOPOLITICAL_ASSETS.items():
        if ticker in st.session_state.market_data:
            data = st.session_state.market_data[ticker]
            commodities_data.append({
                'Commodity': name,
                'Ticker': ticker,
                'Price': data['price'],
                'Daily Change (%)': data['change'],
                'Type': data['type']
            })
    
    if commodities_data:
        commodities_df = pd.DataFrame(commodities_data)
        
        # Commodities performance
        st.subheader("Key Geopolitical Assets Performance")
        fig = px.bar(
            commodities_df.sort_values('Daily Change (%)', ascending=False),
            x='Commodity',
            y='Daily Change (%)',
            color='Daily Change (%)',
            color_continuous_scale=['red', 'gray', 'green'],
            title="1-Day Change in Geopolitically-Sensitive Assets"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Display commodities table
        st.dataframe(commodities_df, hide_index=True)
