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
Tracking the most important financial, monetary and geopolitical news from the last 24 hours with market impact analysis.
""")

# Session state
if 'processed' not in st.session_state:
    st.session_state.processed = False
if 'all_news' not in st.session_state:
    st.session_state.all_news = []
if 'market_data' not in st.session_state:
    st.session_state.market_data = {}

# News categories and sources
NEWS_CATEGORIES = {
    'financial': {
        'keywords': [
            # ... same as original
        ],
        'sources': {
            # ... same as original
        }
    },
    'geopolitical': {
        'keywords': [
            # ... same as original
        ],
        'sources': {
            # ... same as original
        }
    }
}

# --- BEGIN: Expanded Asset/Event Mapping ---

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
    # ... add other mappings as desired
}

FINANCIAL_RISK_ASSET_MAP = {
    'recession': ['TLT', 'IEF', 'XLU', 'XLP', 'GLD', 'USD=X'],
    'inflation': ['TIP', 'GC=F', '^TNX', 'XLE', 'DBA'],
    'deflation': ['TLT', 'IEF', 'USD=X', 'XLU', 'XLP'],
    'fed rate hike': ['^TNX', 'USD=X', 'TBT', 'XLF', 'KRE', 'JPM', 'GS'],
    'bank failure': ['GLD', 'BTC-USD', 'TLT', 'USD=X', 'XLF'],
    'earnings season': ['SPY', 'QQQ', 'DIA'],
    # ... add other mappings as desired
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
    # ... add other mappings as desired
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

# --- END: Expanded Asset/Event Mapping ---

TICKER_PATTERN = r'\\b([A-Z]{2,4})\\b(?=\\s*\\(?\\d*\\)?)'

@st.cache_data
def get_sp500_tickers():
    table = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
    df = table[0]
    return df['Symbol'].tolist()

GEOPOLITICAL_ASSETS = {
    'OIL': 'CL=F',
    'GOLD': 'GC=F',
    'SILVER': 'SI=F',
    'NATURAL GAS': 'NG=F',
    'WHEAT': 'KE=F',
    'CORN': 'ZC=F',
    'USD': 'DX-Y.NYB',
    'BITCOIN': 'BTC-USD',
    'TREASURIES': '^TNX'
}

def is_relevant_news(text, category):
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in NEWS_CATEGORIES[category]['keywords'])

def extract_tickers(text, known_tickers):
    potential_tickers = re.findall(TICKER_PATTERN, text)
    valid_tickers = []
    for ticker in potential_tickers:
        if ticker in known_tickers:
            valid_tickers.append(ticker)
    # Company name mapping (keep from your original)
    company_names = {
        'apple': 'AAPL', 'microsoft': 'MSFT', 'amazon': 'AMZN', 'google': 'GOOGL', 'meta': 'META',
        'tesla': 'TSLA', 'nvidia': 'NVDA', 'exxon': 'XOM', 'chevron': 'CVX', 'lockheed': 'LMT',
        'boeing': 'BA', 'raytheon': 'RTX'
    }
    text_lower = text.lower()
    for name, ticker in company_names.items():
        if name in text_lower and ticker not in valid_tickers:
            valid_tickers.append(ticker)
    return list(set(valid_tickers))

@st.cache_data(ttl=3600, show_spinner="Fetching latest news...")
def fetch_all_news():
    sp500_tickers = get_sp500_tickers()
    all_news = []
    cutoff_time = datetime.now() - timedelta(hours=24)
    # Financial news
    for source, url in NEWS_CATEGORIES['financial']['sources'].items():
        feed = feedparser.parse(url)
        for entry in feed.entries[:50]:
            pub_date = datetime(*entry.published_parsed[:6])
            if pub_date >= cutoff_time and is_relevant_news(entry.title, 'financial'):
                # Combine both event-based and ticker extraction!
                tickers = extract_tickers(entry.title + " " + entry.get('summary', ''), sp500_tickers)
                tickers += extract_assets_from_event(entry.title + " " + entry.get('summary', ''))
                all_news.append({
                    'title': entry.title,
                    'link': entry.link,
                    'published': pub_date.strftime('%Y-%m-%d %H:%M'),
                    'source': source,
                    'tickers': list(set(tickers)),
                    'category': 'financial',
                    'has_market_data': len(tickers) > 0
                })
    # Geopolitical news
    for source, url in NEWS_CATEGORIES['geopolitical']['sources'].items():
        feed = feedparser.parse(url)
        for entry in feed.entries[:50]:
            pub_date = datetime(*entry.published_parsed[:6])
            if pub_date >= cutoff_time and is_relevant_news(entry.title, 'geopolitical'):
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

# --- Remainder of your script remains the same, including get_market_data, analyze_news_sentiment, Streamlit display logic, etc. ---

