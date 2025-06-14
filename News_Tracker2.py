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
Tracking the most important financial, monetary and geopolitical news from the last 24 hours with market impact analysis.
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
    for source, url in NEWS_CATEGORIES['financial']['sources'].items():
        feed = feedparser.parse(url)
        for entry in feed.entries[:50]:
            pub_date = datetime(*entry.published_parsed[:6])
            if pub_date >= cutoff_time and any(keyword in entry.title.lower() for keyword in NEWS_CATEGORIES['financial']['keywords']):
                tickers = extract_assets_from_event(entry.title + " " + entry.get('summary', ''))
                all_news.append({
                    'title': entry.title,
                    'link': entry.link,
                    'published': pub_date.strftime('%Y-%m-%d %H:%M'),
                    'source': source,
                    'tickers': list(set(tickers)),
                    'category': 'financial',
                    'has_market_data': len(tickers) > 0
                })
    for source, url in NEWS_CATEGORIES['geopolitical']['sources'].items():
        feed = feedparser.parse(url)
        for entry in feed.entries[:50]:
            pub_date = datetime(*entry.published_parsed[:6])
            if pub_date >= cutoff_time and any(keyword in entry.title.lower() for keyword in NEWS_CATEGORIES['geopolitical']['keywords']):
                tickers = extract_assets_from_event(entry.title + " " + entry.get('summary', ''))
                all_news.append({
                    'title': entry.title,
                    'link': entry.link,
                    'published': pub_date.strftime('%Y-%m-%d %H:%M'),
                    'source': source,
                    'tickers': list(set(tickers)),
                    'category': 'geopolitical',
                    'has_market_data': len(tickers) > 0
                })
    all_news.sort(key=lambda x: x['published'], reverse=True)
    return all_news

# ...rest of your app (market data, sentiment, Streamlit UI, etc.) remains unchanged
