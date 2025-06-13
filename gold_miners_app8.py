import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from datetime import datetime
import feedparser
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import warnings

# Suppress Streamlit warnings about ScriptRunContext
warnings.filterwarnings("ignore", message="missing ScriptRunContext")

# --- Mining metrics database and default miners ---
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

def fetch_data_concurrently(func, items):
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(func, items))
    return results

@st.cache_data(ttl=60*30)
def get_fundamentals(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        return {
            'Market Cap': info.get('marketCap'),
            'P/E': info.get('trailingPE'),
            'P/B': info.get('priceToBook'),
            'Debt/Equity': info.get('debtToEquity'),
            'Free Cash Flow': info.get('freeCashflow'),
            'EPS Growth': info.get('earningsGrowth'),
            'Analyst Target': info.get('targetMeanPrice')
        }
    except Exception as e:
        st.warning(f"Error fetching fundamentals for {ticker}: {str(e)}")
        return {}

def calculate_nav(ticker, gold_price, discount_rate):
    metrics = get_mining_metrics(ticker)
    if not metrics or not metrics.get('Reserves (moz)') or gold_price is None:
        return None
    reserves_oz = metrics['Reserves (moz)'] * 1e6
    aisc = metrics.get('AISC ($/oz)', 0)
    nav = (reserves_oz * (gold_price - aisc)) / (1 + discount_rate)
    return nav

def get_mining_metrics(ticker):
    return MINING_METRICS_DB.get(ticker, {
        'Production (koz)': None,
        'AISC ($/oz)': None,
        'Reserves (moz)': None,
        'Mines': None,
        'Production Growth (%)': None
    })

@st.cache_data(ttl=60*15)
def get_historical_valuation(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        return hist[['Close']]
    except Exception as e:
        st.warning(f"Error fetching historical data for {ticker}: {str(e)}")
        return pd.DataFrame()

# --- News fetching (Google News + yfinance fallback) ---
@st.cache_data(ttl=600)
def get_news_google(company_name):
    try:
        query = company_name.replace(" ", "+")
        url = f"https://news.google.com/rss/search?q={query}"
        feed = feedparser.parse(url)
        news_list = []
        for entry in feed.entries[:3]:
            news_list.append({
                'title': entry.title,
                'link': entry.link,
                'publisher': entry.get('source', {}).get('title', 'Google News'),
                'date': entry.published if 'published' in entry else ''
            })
        return news_list
    except Exception:
        return []

@st.cache_data(ttl=600)
def get_news_yfinance(ticker):
    try:
        stock = yf.Ticker(ticker)
        news = stock.news or []
        return [{
            'title': item.get('title', 'No title available'),
            'link': item.get('link', '#'),
            'publisher': item.get('publisher', 'Yahoo Finance'),
            'date': datetime.fromtimestamp(item.get('providerPublishTime', datetime.now().timestamp())).strftime('%b %d, %Y')
        } for item in news[:3]]
    except Exception:
        return []

# --- Advanced Sentiment (headline-level VADER) ---
def get_advanced_sentiment(company_name, ticker):
    # Try Google News headlines first, fallback to yfinance news
    news = get_news_google(company_name)
    source = "Google News"
    if not news:
        news = get_news_yfinance(ticker)
        source = "Yahoo Finance"
    if not news:
        return 0.0, source, []
    analyzer = SentimentIntensityAnalyzer()
    scores = []
    for n in news:
        vs = analyzer.polarity_scores(n['title'])
        scores.append(vs['compound'])
    avg_score = np.mean(scores) if scores else 0.0
    return avg_score, source, news

def main():
    st.set_page_config(page_title="Gold Miners Enhanced Analysis", page_icon="💰", layout="wide")
    st.title("💰 Gold Miners Enhanced Analysis")

    # Get current gold price
    try:
        gold_data = yf.Ticker("GC=F").history(period="5d")
        gold_price = gold_data['Close'].iloc[-1] if not gold_data.empty else None
        if gold_price:
            st.success(f"Gold Price: ${gold_price:,.2f}")
    except Exception as e:
        st.error(f"Failed to fetch gold price: {str(e)}")
        gold_price = None

    # Sidebar user controls
    with st.sidebar:
        discount_rate = st.slider("NAV Discount Rate (%)", 1, 10, 5, step=1)/100
        uploaded_file = st.file_uploader("Upload tickers (Excel with Symbol/Exchange columns)", type=["xlsx"])
        if uploaded_file:
            try:
                df = pd.read_excel(uploaded_file)
                if 'Symbol' in df.columns and 'Exchange' in df.columns:
                    tickers = {f"{row.Symbol} ({row.Exchange})": row.Symbol for _, row in df.iterrows()}
                else:
                    st.error("File must have Symbol and Exchange columns. Using defaults.")
                    tickers = DEFAULT_MINERS
            except Exception as e:
                st.error(f"Error reading file: {str(e)}. Using default miners.")
                tickers = DEFAULT_MINERS
        else:
            tickers = DEFAULT_MINERS
        selected_miners = st.multiselect("Select Companies", list(tickers.keys()), default=list(tickers.keys())[:2])

    if not selected_miners:
        st.warning("Please select at least one company.")
        return

    st.header("Company Analysis")
    # --- Updated ticker parsing and data fetching ---
    def fetch_for_ticker(key):
        company_name = key.split(" (")[0]
        ticker = tickers[key]
        fundamentals = get_fundamentals(ticker)
        mining_metrics = get_mining_metrics(ticker)
        nav = calculate_nav(ticker, gold_price, discount_rate)
        sentiment_score, sentiment_source, news_headlines = get_advanced_sentiment(company_name, ticker)
        return (
            ticker,
            company_name,
            fundamentals,
            mining_metrics,
            nav,
            sentiment_score,
            sentiment_source,
            news_headlines
        )
    
    data = fetch_data_concurrently(fetch_for_ticker, selected_miners)

    all_data = []
    sentiment_news = {}
    for ticker, company_name, fundamentals, mining_metrics, nav, sentiment, sentiment_source, news_headlines in data:
        if fundamentals is None:
            fundamentals = {}
        d = {**fundamentals, **mining_metrics}
        d.update({
            "NAV": nav,
            "Sentiment Score": sentiment,
            "Ticker": ticker,
            "Company Name": company_name,
            "Sentiment Source": sentiment_source
        })
        all_data.append(d)
        sentiment_news[company_name] = (sentiment_source, news_headlines)

    df = pd.DataFrame(all_data).set_index('Ticker')

    # Debug output for sentiment scores
    st.write("Advanced Sentiment Scores (VADER):", df[['Sentiment Score', 'Sentiment Source']])
    df['Sentiment Score'] = df['Sentiment Score'].fillna(0)

    # Add NAV deviation for alerting
    if 'Market Cap' in df.columns and 'NAV' in df.columns:
        df['NAV Deviation (%)'] = ((df['Market Cap'] - df['NAV']) / df['NAV']) * 100

    # Robust numeric formatting to avoid TypeError
    num_cols = [
        'Market Cap', 'P/E', 'P/B', 'Debt/Equity', 'Free Cash Flow', 'EPS Growth',
        'Analyst Target', 'NAV', 'Reserves (moz)', 'NAV Deviation (%)'
    ]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    st.dataframe(df.style.format({
        'Market Cap': '${:,.0f}', 'P/E': '{:.1f}', 'P/B': '{:.2f}', 'Debt/Equity': '{:.2f}',
        'Free Cash Flow': '${:,.0f}', 'EPS Growth': '{:.2%}', 'Analyst Target': '${:.2f}',
        'NAV': '${:,.0f}', 'Sentiment Score': '{:+.2f}', 'Reserves (moz)': '{:.1f}',
        'NAV Deviation (%)': '{:+.1f}%'
    }), height=350)

    # Historical Valuation Chart
    st.subheader("Historical Price")
    selected_ticker = st.selectbox("Select Ticker for Historical Chart", df.index)
    hist_data = get_historical_valuation(selected_ticker)
    if not hist_data.empty:
        st.plotly_chart(px.line(hist_data, title=f"Historical Price for {selected_ticker}"), use_container_width=True)
    else:
        st.warning(f"No historical data available for {selected_ticker}")

    # Sentiment bar chart
    st.subheader("Sentiment Scores (VADER Compound)")
    st.bar_chart(df['Sentiment Score'].sort_values())

    # Show news headlines with sentiment source for each selected company
    st.subheader("Recent News & Sentiment Headlines")
    for company_name in df['Company Name']:
        st.markdown(f"**{company_name}** <span style='font-size:small;color:gray;'>(via {sentiment_news[company_name][0]})</span>", unsafe_allow_html=True)
        headlines = sentiment_news[company_name][1]
        if not headlines:
            st.info("No recent news found on Google News or Yahoo Finance.")
        else:
            for item in headlines:
                st.markdown(f"""
                <div class="metric-card">
                    <p><strong><a href="{item['link']}" target="_blank">{item['title']}</a></strong></p>
                    <small>{item.get('publisher','')} • {item.get('date','')}</small>
                </div>
                """, unsafe_allow_html=True)

    # NAV deviation alerts
    if 'NAV Deviation (%)' in df.columns:
        alert_df = df[df['NAV Deviation (%)'].abs() > 20]
        if not alert_df.empty:
            st.warning("Significant NAV deviations detected (>|20%|):")
            st.dataframe(alert_df[['NAV Deviation (%)']])

if __name__ == "__main__":
    main()
