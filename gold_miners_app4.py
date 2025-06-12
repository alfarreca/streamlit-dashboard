import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from concurrent.futures import ThreadPoolExecutor
import time
from datetime import datetime

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

def setup_app():
    st.set_page_config(
        page_title="Gold Miners Fundamental Analysis",
        page_icon="💰",
        layout="wide"
    )

def fetch_data_concurrently(func, items):
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(func, items))
    return results

@st.cache_data(ttl=60*30)
def get_fundamentals(ticker):
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
    stock = yf.Ticker(ticker)
    hist = stock.history(period="1y")
    return hist[['Close']]

@st.cache_data(ttl=60*30)
def sentiment_analysis(ticker):
    try:
        news = yf.Ticker(ticker).news or []
    except Exception:
        return 0
    sentiment_score = 0
    for n in news:
        title = n.get('title', '').lower()
        if any(w in title for w in ['beat', 'growth', 'record', 'expands', 'profit', 'higher']):
            sentiment_score += 1
        elif any(w in title for w in ['miss', 'loss', 'lawsuit', 'cut', 'lower', 'decline']):
            sentiment_score -= 1
    return sentiment_score

def main():
    setup_app()
    st.title("💰 Gold Miners Enhanced Analysis")

    # Get current gold price
    gold_data = yf.Ticker("GC=F").history(period="5d")
    gold_price = gold_data['Close'][-1] if not gold_data.empty else None
    if gold_price:
        st.success(f"Gold Price: ${gold_price:,.2f}")

    # Sidebar user controls
    with st.sidebar:
        discount_rate = st.slider("NAV Discount Rate (%)", 1, 10, 5, step=1)/100
        uploaded_file = st.file_uploader("Upload tickers (Excel with Symbol/Exchange columns)", type=["xlsx"])
        if uploaded_file:
            df = pd.read_excel(uploaded_file)
            if 'Symbol' in df.columns and 'Exchange' in df.columns:
                tickers = {f"{row.Symbol} ({row.Exchange})": row.Symbol for _, row in df.iterrows()}
            else:
                st.error("File must have Symbol and Exchange columns. Using defaults.")
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
        # Parse ticker symbol before any space or parenthesis
        ticker = key.split()[0]
        return (
            ticker,
            get_fundamentals(ticker),
            get_mining_metrics(ticker),
            calculate_nav(ticker, gold_price, discount_rate),
            sentiment_analysis(ticker)
        )
    data = fetch_data_concurrently(fetch_for_ticker, selected_miners)

    all_data = []
    for ticker, fundamentals, mining_metrics, nav, sentiment in data:
        if fundamentals is None:
            fundamentals = {}
        d = {**fundamentals, **mining_metrics}
        d.update({
            "NAV": nav,
            "Sentiment Score": sentiment,
            "Ticker": ticker
        })
        all_data.append(d)

    df = pd.DataFrame(all_data).set_index('Ticker')

    # Debug output for sentiment scores
    st.write("Raw Sentiment Scores:", df[['Sentiment Score']])
    df['Sentiment Score'] = df['Sentiment Score'].fillna(0)

    # Add NAV deviation for alerting
    if 'Market Cap' in df.columns and 'NAV' in df.columns:
        df['NAV Deviation (%)'] = ((df['Market Cap'] - df['NAV']) / df['NAV']) * 100

    # Show Data Table
    st.dataframe(df.style.format({
        'Market Cap': '${:,.0f}', 'P/E': '{:.1f}', 'P/B': '{:.2f}', 'Debt/Equity': '{:.2f}',
        'Free Cash Flow': '${:,.0f}', 'EPS Growth': '{:.2%}', 'Analyst Target': '${:.2f}',
        'NAV': '${:,.0f}', 'Sentiment Score': '{:+d}', 'Reserves (moz)': '{:.1f}',
        'NAV Deviation (%)': '{:+.1f}%'
    }), height=350)

    # Historical Valuation Chart
    st.subheader("Historical Price")
    selected_ticker = st.selectbox("Select Ticker for Historical Chart", df.index)
    hist_data = get_historical_valuation(selected_ticker)
    if not hist_data.empty:
        st.plotly_chart(px.line(hist_data, title=f"Historical Price for {selected_ticker}"), use_container_width=True)

    # Sentiment bar chart
    st.subheader("Sentiment Scores")
    st.bar_chart(df['Sentiment Score'].sort_values())

    # NAV deviation alerts
    if 'NAV Deviation (%)' in df.columns:
        alert_df = df[df['NAV Deviation (%)'].abs() > 20]
        if not alert_df.empty:
            st.warning("Significant NAV deviations detected (>|20%|):")
            st.dataframe(alert_df[['NAV Deviation (%)']])

if __name__ == "__main__":
    main()
