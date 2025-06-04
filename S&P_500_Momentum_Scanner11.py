import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta
import threading
import pytz
import numpy as np

# ========== CONFIGURATION ==========
MAX_WORKERS = 8
CACHE_TTL = 3600 * 12  # 12 hours
PRELOAD_SYMBOLS = 50
BATCH_SIZE = 100
TIMEZONE = 'America/New_York'

# ========== S&P 500 STATIC LIST (Fallback) ==========
def get_sp500_tickers():
    return [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "BRK.B", "JPM", "UNH",
        "V", "XOM", "PG", "JNJ", "LLY", "MA", "HD", "MRK", "ABBV", "AVGO",
    ]

def get_tickers_df():
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        SERVICE_ACCOUNT_INFO = st.secrets["GCP_SERVICE_ACCOUNT"]
        creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key("1sNYUiP4Pl8GVYQ1S7Ltc4ETv-ctOA1RVCdYkMb5xjjg").sheet1
        df = pd.DataFrame(sheet.get_all_records()).dropna(subset=["Symbol"]).drop_duplicates("Symbol")
        if df.empty:
            raise Exception("Sheet empty")
        return df
    except Exception:
        # Fallback to static S&P 500 tickers
        static = get_sp500_tickers()
        return pd.DataFrame({"Symbol": static, "Exchange": ["S&P 500"] * len(static)})

# ========== DATA FETCHING ==========
@st.cache_data(ttl=CACHE_TTL)
def safe_fetch_history(symbol, period="6mo", interval="1d"):
    try:
        ticker_obj = yf.Ticker(symbol)
        hist = ticker_obj.history(period=period, interval=interval)
        if isinstance(hist, pd.DataFrame) and not hist.empty:
            return hist
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

# ========== TECHNICAL INDICATORS ==========
def calculate_momentum(hist):
    if hist.empty or len(hist) < 50:
        return None
    close = hist['Close']
    high = hist['High']
    low = hist['Low']
    volume = hist['Volume']

    # EMAs
    ema20 = close.ewm(span=20).mean().iloc[-1]
    ema50 = close.ewm(span=50).mean().iloc[-1]
    ema200 = close.ewm(span=200).mean().iloc[-1]
    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14).mean().iloc[-1]
    avg_loss = loss.ewm(alpha=1/14).mean().iloc[-1]
    rs = avg_gain / avg_loss if avg_loss != 0 else 100
    rsi = 100 - (100 / (1 + rs))
    # MACD
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9).mean()
    macd_hist = macd.iloc[-1] - macd_signal.iloc[-1]
    # Volume
    vol_avg_20 = volume.rolling(20).mean().iloc[-1]
    # ADX
    try:
        tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        plus_dm = high.diff().where(lambda x: (x > 0) & (x > low.diff().abs()), 0)
        minus_dm = (-low.diff()).where(lambda x: (x > 0) & (x > high.diff().abs()), 0)
        plus_di = 100 * (plus_dm.rolling(14).sum() / atr)
        minus_di = 100 * (minus_dm.rolling(14).sum() / atr)
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        adx = dx.rolling(14).mean().iloc[-1] if not dx.isnull().all() else 0
    except:
        adx = 0

    # Momentum Score
    momentum_score = 0
    if close.iloc[-1] > ema20 > ema50 > ema200:
        momentum_score += 30
    elif close.iloc[-1] > ema50 > ema200:
        momentum_score += 20
    elif close.iloc[-1] > ema200:
        momentum_score += 10

    if 60 < rsi < 80:
        momentum_score += 20
    elif 50 < rsi <= 60 or 80 <= rsi < 90:
        momentum_score += 10

    if macd_hist > 0:
        momentum_score += 15

    if volume.iloc[-1] > vol_avg_20 * 1.5:
        momentum_score += 15
    elif volume.iloc[-1] > vol_avg_20 * 1.2:
        momentum_score += 10

    if adx > 30:
        momentum_score += 20
    elif adx > 25:
        momentum_score += 15
    elif adx > 20:
        momentum_score += 10

    momentum_score = min(100, momentum_score)

    return {
        "EMA20": round(ema20, 2),
        "EMA50": round(ema50, 2),
        "EMA200": round(ema200, 2),
        "RSI": round(rsi, 1),
        "MACD_Hist": round(macd_hist, 3),
        "ADX": round(adx, 1),
        "Volume_Ratio": round(volume.iloc[-1]/vol_avg_20, 2),
        "Momentum_Score": momentum_score,
        "Trend": "↑ Strong" if momentum_score >= 80 else
                 "↑ Medium" if momentum_score >= 60 else
                 "↗ Weak" if momentum_score >= 40 else "→ Neutral"
    }

# ========== DMI/ADX Chart ==========
def create_dmi_chart(hist, symbol):
    high = hist['High']
    low = hist['Low']
    close = hist['Close']

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()

    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

    plus_di = 100 * (plus_dm.rolling(14).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr)

    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.rolling(14).mean()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name='Price', line=dict(color='yellow')))
    fig.add_trace(go.Scatter(x=hist.index, y=plus_di, name='+DI', line=dict(color='green')))
    fig.add_trace(go.Scatter(x=hist.index, y=minus_di, name='-DI', line=dict(color='red')))
    fig.add_trace(go.Scatter(x=hist.index, y=adx, name='ADX', line=dict(color='blue', width=2)))
    fig.add_shape(type="line", x0=hist.index[0], y0=25, x1=hist.index[-1], y1=25, line=dict(color="blue", width=1, dash="dot"))
    fig.update_layout(
        title=f"{symbol} DMI/ADX Chart",
        xaxis_title='Date',
        yaxis_title='Price',
        yaxis2=dict(
            title='DMI Values',
            overlaying='y',
            side='right',
            range=[0, max(plus_di.max(), minus_di.max(), adx.max()) * 1.1]
        ),
        hovermode='x unified',
        height=600,    # <-- Updated height
        width=350,     # <-- Updated width
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

# ========== STREAMLIT UI ==========
def setup_page():
    st.set_page_config(
        layout="wide",
        page_title="S&P 500 Momentum Scanner",
        page_icon="📈"
    )
    st.markdown("""
    <style>
        .stProgress > div > div > div > div {background-color: #1f77b4;}
        .metric-container {padding:15px; border-radius:10px; background-color:#f0f2f6; margin-bottom:10px;}
        .stDataFrame {border-radius:10px; box-shadow:0 2px 4px rgba(0,0,0,0.1);}
        .stTabs [data-baseweb="tab-list"] {gap:10px;}
        .stTabs [data-baseweb="tab"] {padding:8px 16px; border-radius:4px 4px 0 0;}
        .stTabs [aria-selected="true"] {background-color:#f0f2f6; font-weight:bold;}
        .stButton>button {
            background-color:#1f77b4; color:white; border-radius:4px; padding:8px 16px;
        }
        .stButton>button:hover {background-color:#1668a7;}
    </style>
    """, unsafe_allow_html=True)

def sidebar_filters(df):
    with st.sidebar:
        st.image("https://via.placeholder.com/150x50?text=S%26P+500+Scanner", width=150)
        st.header("🔎 Filters")
        min_score = st.slider("Minimum Momentum Score", 0, 100, 70, 5)
        trend_options = ["↑ Strong", "↑ Medium", "↗ Weak"]
        selected_trends = st.multiselect("Trend Strength", options=trend_options, default=trend_options)
        price_range = st.slider("Price Range ($)", 0.0, 1000.0, (10.0, 500.0), 5.0)
        st.markdown("---")
        st.markdown(f"**Last Updated:** {datetime.now(pytz.timezone(TIMEZONE)).strftime('%Y-%m-%d %H:%M %Z')}")
    return {
        "min_score": min_score,
        "selected_trends": selected_trends,
        "price_range": price_range,
    }

def display_results(filtered_df):
    if filtered_df.empty:
        st.warning("No stocks match your current filters. Try adjusting your criteria.")
        return
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Stocks Found", len(filtered_df))
    with col2: st.metric("Avg Momentum Score", round(filtered_df["Momentum_Score"].mean(), 1))
    with col3: st.metric("Strong Trends", len(filtered_df[filtered_df["Trend"] == "↑ Strong"]))
    with col4: st.metric("Avg Volume Ratio", round(filtered_df["Volume_Ratio"].mean(), 

