# --- NLTK Download-in-Code Block for Streamlit Cloud ---
import nltk

def safe_nltk_download(package):
    try:
        if package == "vader_lexicon":
            nltk.data.find("sentiment/vader_lexicon")
        elif package == "punkt":
            nltk.data.find("tokenizers/punkt")
    except LookupError:
        nltk.download(package, quiet=True)

safe_nltk_download("vader_lexicon")
safe_nltk_download("punkt")
# --------------------------------------------------------

import streamlit as st
import feedparser
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from nltk.sentiment import SentimentIntensityAnalyzer
import plotly.express as px
import requests
from bs4 import BeautifulSoup
import re

st.set_page_config(page_title="Global News & Market Tracker", layout="wide")
st.title("🌍 Global News & Market Impact Tracker")
st.markdown("""
Tracking the most important financial, monetary, and geopolitical news from the last 24 hours with market impact analysis.
""")

if 'processed' not in st.session_state:
    st.session_state.processed = False
if 'all_news' not in st.session_state:
    st.session_state.all_news = []
if 'market_data' not in st.session_state:
    st.session_state.market_data = {}

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

GEOPOLITICAL_RISK_ASSET_MAP = {
    'war': ['GC=F', 'SI=F', 'USD=X', 'JPY=X', 'TLT', 'RTX', 'LMT', 'GD', 'NOC', 'BA', 'ITA', 'OIL', 'CL=F'],
    'conflict': ['GC=F', 'USD=X', 'TLT', 'LMT', 'RTX', 'OIL', 'CL=F'],
    'sanction': ['GC=F', 'USD=X', 'CL=F', 'USO', 'FXI', 'RSX'],
    'invasion': ['GC=F', 'SI=F', 'USD=X', 'RTX', 'LMT', 'GD', 'CL=F', 'USO'],
    'cyber attack': ['CIBR', 'BUG', 'PANW', 'ZS', 'CRWD', 'MSFT'],
    'trade war': ['FXI', 'MCHI', 'GC=F', 'USD=X', 'EEM', 'TLT', 'SPY'],
    'taiwan': ['TSM', 'FXI', 'GC=F', 'USD=X', 'EWT', 'SPY'],
    'north korea': ['GC=F', 'USD=X', 'JPY=X', 'TLT'],
    'iran': ['CL=F', 'USO', 'GC=F', 'USD=X'],
    'middle east': ['CL=F', 'USO', 'GC=F', 'USD=X', 'EIS', 'KSA'],
}

FINANCIAL_RISK_ASSET_MAP = {
    'recession': ['TLT', 'IEF', 'XLU', 'XLP', 'GLD', 'USD=X'],
    'inflation': ['TIP', 'GC=F', '^TNX', 'XLE', 'DBA'],
    'deflation': ['TLT', 'IEF', 'USD=X', 'XLU', 'XLP'],
    'fed rate hike': ['^TNX', 'USD=X', 'TBT', 'XLF', 'KRE', 'JPM', 'GS'],
    'bank failure': ['GLD', 'BTC-USD', 'TLT', 'USD=X', 'XLF'],
    'earnings season': ['SPY', 'QQQ', 'DIA'],
}

MONETARY_EVENT_ASSET_MAP = {
    'fed rate hike': ['^TNX', 'USD=X', 'TBT', 'XLF', 'KRE', 'JPM', 'GS'],
    'fed rate cut': ['TLT', 'IEF', 'SPY', 'QQQ', 'XLK', 'GLD'],
    'ecb rate hike': ['EURUSD=X', 'EUFN', '^TNX', 'FXE', 'BUND'],
    'ecb rate cut': ['EURUSD=X', 'IEV', 'EZU', 'VGK', 'TLT'],
    'quantitative easing': ['GLD', 'BTC-USD', 'QQQ', 'SPY', 'TLT'],
    'quantitative tightening': ['USD=X', '^TNX', 'TBT', 'IEF'],
    'monetary stimulus': ['GLD', 'SPY', 'QQQ', 'BTC-USD', 'TLT'],
    'yield curve inversion': ['TLT', 'IEF', 'USD=X', 'GLD', 'XLP', 'XLU'],
}

def extract_assets_from_event(text):
    detected_assets = set()
    text_lower = text.lower()
    for keyword, assets in GEOPOLITICAL_RISK_ASSET_MAP.items():
        if keyword in text_lower:
            detected_assets.update(assets)
    for keyword, assets in FINANCIAL_RISK_ASSET_MAP.items():
        if keyword in text_lower:
            detected_assets.update(assets)
    for keyword, assets in MONETARY_EVENT_ASSET_MAP.items():
        if keyword in text_lower:
            detected_assets.update(assets)
    return list(detected_assets)

TICKER_PATTERN = r'\b([A-Z]{2,4})\b(?=\s*\(?\d*\)?)'

@st.cache_data
def get_sp500_tickers():
    table = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
    df = table[0]
    return df['Symbol'].tolist()

@st.cache_data(ttl=3600, show_spinner="Fetching latest news...")
def fetch_all_news():
    sp500_tickers = get_sp500_tickers()
    all_news = []
    cutoff_time = datetime.now() - timedelta(hours=24)
    for category in NEWS_CATEGORIES:
        for source, url in NEWS_CATEGORIES[category]['sources'].items():
            feed = feedparser.parse(url)
            for entry in feed.entries[:50]:
                pub_date = datetime(*entry.published_parsed[:6])
                if pub_date >= cutoff_time and any(keyword in entry.title.lower() for keyword in NEWS_CATEGORIES[category]['keywords']):
                    tickers = extract_assets_from_event(entry.title + " " + entry.get('summary', ''))
                    all_news.append({
                        'title': entry.title,
                        'link': entry.link,
                        'published': pub_date.strftime('%Y-%m-%d %H:%M'),
                        'source': source,
                        'tickers': list(set(tickers)),
                        'category': category,
                        'has_market_data': len(tickers) > 0
                    })
    all_news.sort(key=lambda x: x['published'], reverse=True)
    return all_news

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

def analyze_news_sentiment(news_items, market_data):
    sia = SentimentIntensityAnalyzer()
    ticker_sentiments = {}
    for item in news_items:
        if not item['tickers']:
            continue
        sentiment = sia.polarity_scores(item['title'])
        for ticker in item['tickers']:
            if ticker in market_data:
                if ticker not in ticker_sentiments:
                    ticker_sentiments[ticker] = []
                ticker_sentiments[ticker].append(sentiment['compound'])
    for ticker, scores in ticker_sentiments.items():
        market_data[ticker]['news_sentiment'] = sum(scores) / len(scores) if scores else None
    return market_data

# --- AI AGENT LOGIC ---
def ai_trade_advice(news_sentiment, market_change, asset_type=None):
    """
    Returns AI trade advice based on news sentiment, daily price change, and (optional) asset class.
    """
    if news_sentiment is None:
        return "No clear action"
    if news_sentiment > 0.4 and (market_change is None or market_change > -1):
        return "BUY"
    elif news_sentiment < -0.4 and (market_change is None or market_change < 1):
        if asset_type == 'commodity':
            return "HEDGE/BUY SAFE-HAVEN"
        elif asset_type == 'stock':
            return "SELL"
        else:
            return "HEDGE/SELL"
    else:
        return "HOLD"
# --- END AI AGENT LOGIC ---

def format_price(price):
    if isinstance(price, float):
        return f"${price:.2f}"
    return f"${price}"

def format_sentiment(sentiment):
    if sentiment is None:
        return "N/A"
    return f"{sentiment:.2f}"

def process_news():
    with st.spinner("Processing global news and market data..."):
        all_news = fetch_all_news()
        all_tickers = list(set(ticker for item in all_news for ticker in item['tickers']))
        market_data = get_market_data(all_tickers) if all_tickers else {}
        if market_data:
            market_data = analyze_news_sentiment(all_news, market_data)
        st.session_state.all_news = all_news
        st.session_state.market_data = market_data
        st.session_state.processed = True

if not st.session_state.processed:
    process_news()

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

st.header("Global News & Market Impact (Last 24 Hours)")
if not st.session_state.all_news:
    st.warning("No relevant news found in the last 24 hours.")
else:
    displayed_count = 0
    for item in st.session_state.all_news:
        if item['category'] not in news_category:
            continue
        if show_only_market_news and not item['tickers']:
            continue
        with st.expander(f"{item['title']} ({item['source']} - {item['published']})"):
            col1, col2 = st.columns([3, 1])
            with col1:
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
                                - Sentiment: {format_sentiment(data['news_sentiment'])}
                                """,
                                unsafe_allow_html=True
                            )
                            # --- AI Advice Display ---
                            advice = ai_trade_advice(
                                data.get('news_sentiment'),
                                data.get('change'),
                                data.get('type')
                            )
                            st.markdown(f"**AI Advice:** <span style='color:orange'>{advice}</span>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"- {ticker} (data unavailable)")
            displayed_count += 1
    if displayed_count == 0:
        st.warning("No news matches current filters.")

if st.session_state.market_data:
    st.header("Global Market Impact Analysis")
    impact_data = []
    for ticker, data in st.session_state.market_data.items():
        if data['type'] in asset_types and (data['news_sentiment'] is None or data['news_sentiment'] >= min_sent
