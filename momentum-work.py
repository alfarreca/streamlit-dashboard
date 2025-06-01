import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime, timedelta
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_exponential

# ========== CONFIGURATION ==========
MAX_WORKERS = 6
REQUEST_DELAY = (0.5, 2.0)
CACHE_TTL = 3600 * 12
PRELOAD_SYMBOLS = 50
MAX_RETRIES = 3
BATCH_SIZE = 300
EVENT_DAYS_WINDOW = 14  # Days before/after event to consider

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
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    SERVICE_ACCOUNT_INFO = st.secrets["GCP_SERVICE_ACCOUNT"]
    creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key("1TT5xMOWU8MkYTOb5X5jrQ08BQ20cRVogfC77cSCeToQ").sheet1
    df = pd.DataFrame(sheet.get_all_records()).dropna(subset=["Symbol", "Exchange"]).drop_duplicates("Symbol")
    return df

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

# ========== EVENT ANALYSIS ==========
def get_events_data(ticker_obj):
    events = {
        'earnings_dates': [],
        'dividends': [],
        'splits': [],
        'news': []
    }
    
    try:
        # Earnings Calendar
        calendar = ticker_obj.calendar
        if not calendar.empty:
            events['earnings_dates'] = calendar['Earnings Date'].tolist()
            
        # Dividends
        dividends = ticker_obj.dividends
        if not dividends.empty:
            events['dividends'] = dividends.tail(3).reset_index().values.tolist()
            
        # Splits
        splits = ticker_obj.splits
        if not splits.empty:
            events['splits'] = splits.tail(3).reset_index().values.tolist()
            
        # News
        news = ticker_obj.news
        if news:
            events['news'] = [{
                'title': item.get('title', ''),
                'date': pd.to_datetime(item.get('providerPublishTime', 0), unit='s'),
                'link': item.get('link', '')
            } for item in news[:3]]  # Get top 3 news items
            
    except Exception as e:
        st.warning(f"Error fetching events data: {str(e)}")
    
    return events

def calculate_event_impact(events, current_date):
    impact_score = 0
    upcoming_events = []
    
    # Earnings impact
    for earnings_date in events.get('earnings_dates', []):
        days_diff = (earnings_date - current_date).days
        if -EVENT_DAYS_WINDOW <= days_diff <= EVENT_DAYS_WINDOW:
            proximity_factor = 1 - abs(days_diff)/EVENT_DAYS_WINDOW
            impact_score += 15 * proximity_factor  # Max 15 points
            upcoming_events.append(f"Earnings in {days_diff} days")
    
    # News impact
    recent_news = [n for n in events.get('news', []) 
                  if (current_date - n['date']).days <= 7]
    impact_score += min(10, len(recent_news) * 3)  # Max 10 points for news
    
    # Dividends impact
    if events.get('dividends'):
        last_div_date = max([d[0] for d in events['dividends']])
        days_since_div = (current_date - last_div_date).days
        if days_since_div <= 5:
            impact_score += 5  # 5 points for recent dividend
    
    return {
        'event_impact_score': min(30, impact_score),  # Cap at 30 points
        'upcoming_events': upcoming_events,
        'has_recent_news': len(recent_news) > 0,
        'recent_news': recent_news
    }

# ========== TECHNICAL INDICATORS ==========
def calculate_momentum(hist, events_data=None):
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
    avg_gain = gain.rolling(14).mean().iloc[-1]
    avg_loss = loss.rolling(14).mean().iloc[-1]
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
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    up_move = high.diff()
    down_move = low.diff().abs()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    plus_di = 100 * (plus_dm.rolling(14).sum() / atr)
    minus_di = 100 * (minus_dm.rolling(14).sum() / atr)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.rolling(14).mean().iloc[-1] if not dx.isnull().all() else 0
    plus_di_last = plus_di.iloc[-1] if not plus_di.isnull().all() else 0
    minus_di_last = minus_di.iloc[-1] if not minus_di.isnull().all() else 0

    # Base Momentum Score (0-70)
    momentum_score = 0
    if close.iloc[-1] > ema20 > ema50 > ema200:
        momentum_score += 30
    if 60 < rsi < 80:
        momentum_score += 20
    if macd_hist > 0:
        momentum_score += 15
    if volume.iloc[-1] > vol_avg_20 * 1.2:
        momentum_score += 10
    if adx > 25:
        momentum_score += 15
    if plus_di_last > minus_di_last:
        momentum_score += 10
        
    # Add event impact if available (0-30)
    if events_data:
        event_impact = calculate_event_impact(events_data, hist.index[-1])
        momentum_score += event_impact['event_impact_score']
        momentum_score = min(100, momentum_score)  # Cap at 100
        
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
            "Event_Impact": event_impact['event_impact_score'],
            "Upcoming_Events": event_impact['upcoming_events'],
            "Has_Recent_News": event_impact['has_recent_news'],
            "Recent_News": event_impact['recent_news']
        }
    else:
        return {
            "EMA20": round(ema20, 2),
            "EMA50": round(ema50, 2),
            "EMA200": round(ema200, 2),
            "RSI": round(rsi, 1),
            "MACD_Hist": round(macd_hist, 3),
            "ADX": round(adx, 1),
            "Volume_Ratio": round(volume.iloc[-1]/vol_avg_20, 2),
            "Momentum_Score": momentum_score,
            "Trend": "↑ Strong" if momentum_score >= 70 else 
                     "↑ Medium" if momentum_score >= 50 else 
                     "↗ Weak" if momentum_score >= 30 else "→ Neutral",
            "Event_Impact": 0,
            "Upcoming_Events": [],
            "Has_Recent_News": False,
            "Recent_News": []
        }

# ========== TICKER PROCESSING ==========
@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_ticker_data(_ticker, exchange, yf_symbol):
    try:
        ticker_obj = yf.Ticker(yf_symbol)
        try:
            hist = safe_yfinance_fetch(ticker_obj)
            events_data = get_events_data(ticker_obj)
        except Exception as e:
            st.warning(f"Error fetching {_ticker}: {str(e)}")
            return None
        if hist.empty or len(hist) < 20:
            return None

        momentum_data = calculate_momentum(hist, events_data)
        return {
            "Symbol": _ticker,
            "Exchange": exchange,
            "Price": round(hist['Close'].iloc[-1], 2),
            "5D_Change": round((hist['Close'].iloc[-1]/hist['Close'].iloc[-5]-1)*100, 1) if len(hist) >= 5 else None,
            **momentum_data,
            "Last_Updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "YF_Symbol": yf_symbol
        }
    except Exception as e:
        st.warning(f"Error processing {_ticker}: {str(e)}")
        return None

# ========== STREAMLIT UI ==========
st.set_page_config(layout="wide", page_title="Russell 2000 Momentum Scanner")
st.title("🚀 Russell 2000 Momentum Scanner with Event Analysis")

# Initialize session state
if 'full_data_loaded' not in st.session_state:
    st.session_state.update({
        'full_data_loaded': False,
        'initial_results': [],
        'last_full_load': None,
        'filtered_results': [],
        'last_loaded_index': PRELOAD_SYMBOLS,
        'show_event_stocks_only': False
    })

# Load basic data
df = get_google_sheet_data()

# ========== FILTERS ==========
with st.sidebar:
    st.header("Momentum Filters")
    min_score = st.slider("Minimum Momentum Score", 0, 100, 70, 5)
    trend_options = ["↑ Strong", "↑ Medium", "↗ Weak"]
    selected_trends = st.multiselect("Trend Strength", options=trend_options, default=trend_options)
    price_range = st.slider("Price Range ($)", 0.0, 500.0, (10.0, 200.0), 5.0)
    exchange_options = df["Exchange"].unique()
    selected_exchanges = st.multiselect("Exchanges", options=exchange_options, default=["NASDAQ", "NYSE"])
    
    st.header("Event Filters")
    st.session_state.show_event_stocks_only = st.checkbox(
        "Only stocks with upcoming events", 
        value=st.session_state.show_event_stocks_only
    )
    min_event_impact = st.slider("Minimum Event Impact", 0, 30, 10, 1)

# ========== DATA PROCESSING ==========
if not st.session_state.initial_results:
    with st.spinner(f'Loading initial {PRELOAD_SYMBOLS} symbols...'):
        subset = df[df["Exchange"].isin(selected_exchanges)].head(PRELOAD_SYMBOLS)
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(get_ticker_data, row["Symbol"], row["Exchange"], 
                      map_to_yfinance_symbol(row["Symbol"], row["Exchange"])) 
                      for row in subset.to_dict('records')]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    st.session_state.initial_results.append(result)

# ========== BATCH LOADING BUTTONS ==========
col1, col2 = st.columns(2)
with col1:
    if st.button('Load Next 300 Tickers') and not st.session_state.full_data_loaded:
        with st.spinner('Loading next 300 symbols...'):
            start_idx = st.session_state.last_loaded_index
            end_idx = start_idx + BATCH_SIZE
            subset = df[df["Exchange"].isin(selected_exchanges)].iloc[start_idx:end_idx]
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            new_results = []
            
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = [executor.submit(get_ticker_data, row["Symbol"], row["Exchange"], 
                          map_to_yfinance_symbol(row["Symbol"], row["Exchange"])) 
                          for row in subset.to_dict('records')]
                for i, future in enumerate(as_completed(futures)):
                    try:
                        result = future.result()
                        if result:
                            new_results.append(result)
                            st.session_state.initial_results.append(result)
                    except Exception as e:
                        st.warning(f"Error processing future: {str(e)}")
                    if i % 10 == 0:
                        progress = min(100, int((i+1)/len(futures)*100))
                        progress_bar.progress(progress)
                        status_text.text(f"Processed {i+1}/{len(futures)} symbols")
                        time.sleep(0.1)
            
            st.session_state.last_loaded_index = end_idx
            progress_bar.empty()
            status_text.empty()
            st.success(f"Loaded {len(new_results)} additional symbols")
            st.rerun()

with col2:
    if st.button('Load Full Dataset (500+ Symbols)'):
        if (st.session_state.last_full_load and 
            (datetime.now() - st.session_state.last_full_load) < timedelta(hours=1)):
            st.warning("Please wait 1 hour between full loads to avoid rate limits")
        else:
            with st.spinner('Loading full dataset (5-10 minutes)...'):
                progress_bar = st.progress(0)
                status_text = st.empty()
                results = []
                filtered_df = df[df["Exchange"].isin(selected_exchanges)]
                with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    futures = {executor.submit(get_ticker_data, row["Symbol"], row["Exchange"], 
                              map_to_yfinance_symbol(row["Symbol"], row["Exchange"])): idx 
                              for idx, row in enumerate(filtered_df.to_dict('records'))}
                    for i, future in enumerate(as_completed(futures)):
                        try:
                            result = future.result()
                            if result:
                                results.append(result)
                        except Exception as e:
                            st.warning(f"Error processing future: {str(e)}")
                        if i % 10 == 0:
                            progress = min(100, int((i+1)/len(futures)*100))
                            progress_bar.progress(progress)
                            status_text.text(f"Processed {i+1}/{len(futures)} symbols")
                            time.sleep(0.1)
                st.session_state.initial_results = results
                st.session_state.full_results = results
                st.session_state.full_data_loaded = True
                st.session_state.last_full_load = datetime.now()
                st.session_state.last_loaded_index = len(df)
                progress_bar.empty()
                status_text.empty()
                st.success(f"Loaded {len(results)} symbols")

# ========== DISPLAY RESULTS ==========
if st.session_state.initial_results:
    filtered = pd.DataFrame(st.session_state.initial_results)
    
    # Apply filters
    filtered = filtered[
        (filtered["Momentum_Score"] >= min_score) &
        (filtered["Trend"].isin(selected_trends)) &
        (filtered["Price"].between(*price_range)) &
        (filtered["Exchange"].isin(selected_exchanges)) &
        (filtered["Event_Impact"] >= min_event_impact)
    ]
    
    # Apply event filter if enabled
    if st.session_state.show_event_stocks_only:
        filtered = filtered[filtered["Upcoming_Events"].apply(len) > 0]
    
    filtered = filtered.sort_values("Momentum_Score", ascending=False)
    st.session_state.filtered_results = filtered
    
    # Summary Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Stocks Found", len(filtered))
    col2.metric("Avg Momentum Score", round(filtered["Momentum_Score"].mean(), 1))
    col3.metric("Strong Trends", len(filtered[filtered["Trend"] == "↑ Strong"]))
    col4.metric("High Event Impact", len(filtered[filtered["Event_Impact"] >= 20]))
    
    # Results Table
    st.dataframe(
        filtered[[
            "Symbol", "Exchange", "Price", "5D_Change", 
            "Momentum_Score", "Trend", "Event_Impact", "RSI", 
            "MACD_Hist", "Volume_Ratio", "Upcoming_Events", "Last_Updated"
        ]],
        use_container_width=True,
        height=600,
        column_config={
            "Price": st.column_config.NumberColumn(format="$%.2f"),
            "5D_Change": st.column_config.NumberColumn(format="%.1f%%"),
            "Volume_Ratio": st.column_config.NumberColumn(format="%.2fx"),
            "Momentum_Score": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100),
            "Event_Impact": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=30),
            "Upcoming_Events": st.column_config.ListColumn(width="medium")
        }
    )

# ========== DETAILED CHART VIEW ==========
st.divider()
st.subheader("📈 Detailed Analysis")

if not st.session_state.filtered_results.empty:
    selected_symbol = st.selectbox(
        "Select symbol for detailed chart:", 
        options=st.session_state.filtered_results["Symbol"]
    )

    if selected_symbol:
        with st.spinner(f'Loading {selected_symbol} analysis...'):
            try:
                symbol_data = st.session_state.filtered_results[
                    st.session_state.filtered_results["Symbol"] == selected_symbol
                ].iloc[0]
                
                tab1, tab2, tab3 = st.tabs(["Price Chart", "Momentum Indicators", "Event Analysis"])
                
                with tab1:
                    ticker = yf.Ticker(symbol_data["YF_Symbol"])
                    hist = safe_yfinance_fetch(ticker, "6mo")
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=hist.index, y=hist['Close'], 
                        name='Price', line=dict(color='#1f77b4', width=2)
                    ))
                    fig.add_trace(go.Scatter(
                        x=hist.index, y=hist['Close'].ewm(span=20).mean(),
                        name='20 EMA', line=dict(color='orange', width=1)
                    ))
                    fig.add_trace(go.Scatter(
                        x=hist.index, y=hist['Close'].ewm(span=50).mean(),
                        name='50 EMA', line=dict(color='red', width=1)
                    ))
                    fig.add_trace(go.Scatter(
                        x=hist.index, y=hist['Close'].ewm(span=200).mean(),
                        name='200 EMA', line=dict(color='purple', width=1)
                    ))
                    
                    # Add event markers
                    events = get_events_data(ticker)
                    if events.get('earnings_dates'):
                        for date in events['earnings_dates']:
                            fig.add_vline(x=date, line_color="red", line_dash="dash",
                                        annotation_text="Earnings", annotation_position="top left")
                    if events.get('dividends'):
                        for date, _ in events['dividends']:
                            fig.add_vline(x=date, line_color="green", line_dash="dot",
                                        annotation_text="Dividend", annotation_position="bottom right")
                    
                    fig.update_layout(
                        title=f"{selected_symbol} Price with EMAs and Events",
                        height=500,
                        showlegend=True
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                with tab2:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Momentum Score", symbol_data["Momentum_Score"])
                        st.metric("Trend Strength", symbol_data["Trend"])
                        st.metric("RSI", symbol_data["RSI"])
                    with col2:
                        st.metric("MACD Histogram", round(symbol_data["MACD_Hist"], 3))
                        st.metric("Volume vs Avg", f"{symbol_data['Volume_Ratio']:.2f}x")
                        st.metric("ADX (Trend Strength)", symbol_data["ADX"])
                    st.progress(symbol_data["Momentum_Score"]/100, text="Momentum Strength")
                
                with tab3:
                    st.subheader("Upcoming Events")
                    if symbol_data["Upcoming_Events"]:
                        for event in symbol_data["Upcoming_Events"]:
                            st.write(f"- {event}")
                    else:
                        st.write("No upcoming events found in the next 14 days")
                    
                    st.subheader("Recent News")
                    if symbol_data["Recent_News"]:
                        for news in symbol_data["Recent_News"]:
                            st.write(f"**{news['date'].strftime('%Y-%m-%d')}**")
                            st.write(news['title'])
                            if news.get('link'):
                                st.markdown(f"[Read more]({news['link']})")
                            st.divider()
                    else:
                        st.write("No recent news available")
                    
                    st.subheader("Event Impact Analysis")
                    st.metric("Event Impact Score", symbol_data["Event_Impact"])
                    st.progress(symbol_data["Event_Impact"]/30, text="Event Impact Contribution")
                    
            except Exception as e:
                st.error(f"Error loading {selected_symbol}: {str(e)}")

# ========== SYSTEM CONTROLS ==========
with st.expander("System Controls"):
    if st.button("Clear Cache & Reload"):
        st.cache_data.clear()
        st.session_state.clear()
        st.rerun()
    st.write(f"Last full load: {st.session_state.last_full_load}")
    st.write(f"Total symbols loaded: {len(st.session_state.initial_results)}")
    st.write(f"Next batch starts at index: {st.session_state.last_loaded_index}")
