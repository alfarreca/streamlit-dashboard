import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_exponential
import pytz
import numpy as np

# ========== CONFIGURATION ==========
MAX_WORKERS = 8
REQUEST_DELAY = (0.5, 2.0)
CACHE_TTL = 3600 * 12  # 12 hours
MAX_RETRIES = 3
TIMEZONE = 'America/New_York'

# ========== SETUP ==========
yf.set_tz_cache_location("cache")

# ========== RETRY MECHANISM ==========
@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
def safe_yfinance_fetch(ticker, period="3mo"):
    time.sleep(random.uniform(*REQUEST_DELAY))
    return ticker.history(period=period)

# ========== DATA FETCHING ==========
@st.cache_data(ttl=CACHE_TTL)
def get_google_sheet_data():
    try:
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        SERVICE_ACCOUNT_INFO = st.secrets["GCP_SERVICE_ACCOUNT"]
        creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key("1sNYUiP4Pl8GVYQ1S7Ltc4ETv-ctOA1RVCdYkMb5xjjg").sheet1
        df = pd.DataFrame(sheet.get_all_records()).dropna(subset=["Symbol", "Exchange"]).drop_duplicates("Symbol")
        # Clean up Exchange column to ensure consistent filtering
        df["Exchange"] = df["Exchange"].astype(str).str.strip().str.upper()
        return df
    except Exception as e:
        st.error(f"Failed to load Google Sheet data: {str(e)}")
        return pd.DataFrame(columns=["Symbol", "Exchange"])

def exchange_suffix(ex: str) -> str:
    suffix_map = {
        "ETR": "DE", "EPA": "PA", "LON": "L", "BIT": "MI", "STO": "ST",
        "SWX": "SW", "TSE": "TO", "ASX": "AX", "HKG": "HK"
    }
    return suffix_map.get(ex.upper(), "")

def map_to_yfinance_symbol(symbol: str, exchange: str) -> str:
    if exchange.upper() in ["NYSE", "NASDAQ"]:
        return symbol
    suffix = exchange_suffix(exchange)
    return f"{symbol}.{suffix}" if suffix else symbol

# ========== TECHNICAL INDICATORS ==========
def calculate_di_crossovers(hist, period=14):
    high = hist['High']
    low = hist['Low']
    close = hist['Close']

    plus_dm = high.diff()
    minus_dm = -low.diff()

    plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0)
    minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0)

    tr1 = high - low
    tr2 = np.abs(high - close.shift())
    tr3 = np.abs(low - close.shift())
    tr = np.maximum.reduce([tr1, tr2, tr3])

    atr = pd.Series(tr).rolling(window=period, min_periods=period).mean()
    plus_di = 100 * pd.Series(plus_dm).rolling(window=period, min_periods=period).mean() / atr
    minus_di = 100 * pd.Series(minus_dm).rolling(window=period, min_periods=period).mean() / atr

    bullish_crossover = (plus_di > minus_di) & (plus_di.shift(1) <= minus_di.shift(1))
    bearish_crossover = (minus_di > plus_di) & (minus_di.shift(1) <= plus_di.shift(1))
    return plus_di, minus_di, bullish_crossover, bearish_crossover

def calculate_momentum(hist):
    if hist.empty or len(hist) < 50:
        return None

    close = hist['Close']
    high = hist['High']
    low = hist['Low']
    volume = hist['Volume']

    # Moving Averages
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

    # Volume Analysis
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

    plus_di_c, minus_di_c, bullish_cross, bearish_cross = calculate_di_crossovers(hist)
    last_bullish = bool(bullish_cross.iloc[-1])
    last_bearish = bool(bearish_cross.iloc[-1])

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
                 "↗ Weak" if momentum_score >= 40 else "→ Neutral",
        "Bullish_Crossover": last_bullish,
        "Bearish_Crossover": last_bearish,
        "plus_di_last": round(plus_di_c.iloc[-1], 1) if not np.isnan(plus_di_c.iloc[-1]) else None,
        "minus_di_last": round(minus_di_c.iloc[-1], 1) if not np.isnan(minus_di_c.iloc[-1]) else None,
    }

# ========== CHART FUNCTIONS ==========
def create_price_chart(hist, symbol):
    fig = go.Figure()
    
    # Price line
    fig.add_trace(go.Scatter(
        x=hist.index, 
        y=hist['Close'],
        name='Price',
        line=dict(color='#1f77b4')
    ))
    
    # Moving averages
    fig.add_trace(go.Scatter(
        x=hist.index,
        y=hist['Close'].ewm(span=20).mean(),
        name='EMA20',
        line=dict(color='orange', width=1)
    ))
    
    fig.add_trace(go.Scatter(
        x=hist.index,
        y=hist['Close'].ewm(span=50).mean(),
        name='EMA50',
        line=dict(color='green', width=1)
    ))
    
    fig.add_trace(go.Scatter(
        x=hist.index,
        y=hist['Close'].ewm(span=200).mean(),
        name='EMA200',
        line=dict(color='red', width=1)
    ))
    
    fig.update_layout(
        title=f'{symbol} Price Chart',
        xaxis_title='Date',
        yaxis_title='Price',
        hovermode='x unified',
        height=400,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    return fig

def create_sparkline(hist):
    if len(hist) < 5:
        return None
    
    fig = go.Figure(go.Scatter(
        x=hist.index,
        y=hist['Close'],
        line=dict(color='#1f77b4', width=1)
    ))
    
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=30,
        width=100,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    
    return fig

def create_momentum_distribution_chart(df):
    fig = go.Figure()
    
    fig.add_trace(go.Histogram(
        x=df['Momentum_Score'],
        nbinsx=20,
        marker_color='#1f77b4',
        opacity=0.7
    ))
    
    fig.update_layout(
        title='Momentum Score Distribution',
        xaxis_title='Momentum Score',
        yaxis_title='Count',
        bargap=0.1,
        height=300,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    return fig

# ========== TICKER PROCESSING ==========
@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_ticker_data(_ticker, exchange, yf_symbol):
    try:
        ticker_obj = yf.Ticker(yf_symbol)
        hist = safe_yfinance_fetch(ticker_obj)
        if hist.empty or len(hist) < 50:
            return None
        momentum_data = calculate_momentum(hist)
        if not momentum_data:
            return None
        current_price = hist['Close'].iloc[-1]
        five_day_change = ((current_price/hist['Close'].iloc[-5]-1)*100) if len(hist) >= 5 else None
        twenty_day_change = ((current_price/hist['Close'].iloc[-20]-1)*100) if len(hist) >= 20 else None
        
        # Create sparkline for the dataframe
        sparkline = create_sparkline(hist)
        
        return {
            "Symbol": _ticker,
            "Exchange": exchange,
            "Price": round(current_price, 2),
            "5D_Change": round(five_day_change, 1) if five_day_change else None,
            "20D_Change": round(twenty_day_change, 1) if twenty_day_change else None,
            **momentum_data,
            "Last_Updated": datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d %H:%M"),
            "YF_Symbol": yf_symbol,
            "Sparkline": sparkline
        }
    except Exception as e:
        st.warning(f"Error processing {_ticker}: {str(e)}")
        return None

# ========== STREAMLIT UI ==========
def display_results(filtered_df):
    if filtered_df.empty:
        st.warning("No stocks match your current filters. Try adjusting your criteria.")
        st.write("Raw loaded data (first 5 rows):")
        st.write(st.session_state.get("raw_results_df", pd.DataFrame()).head())
        st.write("Unique Exchanges in loaded data:", 
                 st.session_state.get("raw_results_df", pd.DataFrame()).get("Exchange", pd.Series()).unique())
        return
    
    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Stocks Found", len(filtered_df))
    with col2:
        st.metric("Avg Momentum Score", round(filtered_df["Momentum_Score"].mean(), 1))
    with col3:
        st.metric("Strong Trends", len(filtered_df[filtered_df["Trend"] == "↑ Strong"]))
    with col4:
        st.metric("Avg Volume Ratio", round(filtered_df["Volume_Ratio"].mean(), 2))
    
    # Momentum distribution chart
    st.plotly_chart(create_momentum_distribution_chart(filtered_df), use_container_width=True)
    
    # Prepare dataframe with sparklines
    display_df = filtered_df[[
        "Symbol", "Exchange", "Price", "5D_Change", "20D_Change",
        "Momentum_Score", "Trend", "RSI", "MACD_Hist",
        "Volume_Ratio", "ADX", "Bullish_Crossover", "Bearish_Crossover", "Last_Updated"
    ]].sort_values("Momentum_Score", ascending=False)
    
    # Display dataframe
    st.dataframe(
        display_df,
        use_container_width=True,
        height=600,
    )

def display_symbol_details(selected_symbol):
    if not selected_symbol:
        return
    with st.spinner(f'Loading {selected_symbol} analysis...'):
        try:
            symbol_data = st.session_state.filtered_results[
                st.session_state.filtered_results["Symbol"] == selected_symbol
            ].iloc[0]
            
            st.subheader(f"{selected_symbol} Detailed Analysis")
            
            # Create tabs for different views
            tab1, tab2 = st.tabs(["Price Chart", "Details"])
            
            with tab1:
                # Get historical data for the chart
                ticker_obj = yf.Ticker(symbol_data["YF_Symbol"])
                hist = safe_yfinance_fetch(ticker_obj)
                
                if not hist.empty:
                    st.plotly_chart(create_price_chart(hist, selected_symbol), use_container_width=True)
                else:
                    st.warning("Could not load price history for chart")
            
            with tab2:
                st.json(symbol_data.to_dict())
                
        except Exception as e:
            st.error(f"Error loading {selected_symbol}: {str(e)}")

def main():
    st.set_page_config(page_title="S&P 500 Momentum Scanner", layout="wide")
    st.title("S&P 500 Momentum Scanner")

    df = get_google_sheet_data()
    if df.empty:
        st.warning("No data loaded from Google Sheets.")
        return

    df["YF_Symbol"] = df.apply(
        lambda row: map_to_yfinance_symbol(row["Symbol"], row["Exchange"]), axis=1
    )

    exchanges = sorted(df["Exchange"].unique().tolist())
    selected_exchange = st.sidebar.selectbox("Exchange", ["All"] + exchanges)
    min_score = st.sidebar.slider("Min Momentum Score", 0, 100, 50)

    ticker_data = []
    progress = st.progress(0, text="Fetching ticker data...")
    total = len(df)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(get_ticker_data, row["Symbol"], row["Exchange"], row["YF_Symbol"])
            for idx, row in df.iterrows()
        ]
        for i, f in enumerate(as_completed(futures)):
            data = f.result()
            if data:
                ticker_data.append(data)
            progress.progress((i + 1) / total, text=f"Processed {i+1}/{total} tickers")
    progress.empty()

    results_df = pd.DataFrame(ticker_data)
    st.session_state["raw_results_df"] = results_df.copy()

    if not results_df.empty:
        results_df = results_df.reset_index(drop=True)
        if selected_exchange != "All":
            filtered = results_df[
                (results_df["Momentum_Score"] >= min_score) &
                (results_df["Exchange"] == selected_exchange)
            ].copy()
        else:
            filtered = results_df[results_df["Momentum_Score"] >= min_score].copy()
    else:
        filtered = pd.DataFrame()

    st.session_state.filtered_results = filtered

    display_results(filtered)

    if not filtered.empty:
        selected = st.selectbox("Select a symbol for details", filtered["Symbol"])
        display_symbol_details(selected)

if __name__ == "__main__":
    main()
