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
    """Get upcoming earnings dates using multiple methods"""
    try:
        # Method 1: get_earnings_dates()
        earnings = ticker_obj.get_earnings_dates()
        if earnings is not None and not earnings.empty:
            future_earnings = earnings[earnings.index > pd.Timestamp.now()]
            if not future_earnings.empty:
                return sorted(future_earnings.index.tolist())
        
        # Method 2: calendar (fallback)
        calendar = ticker_obj.calendar
        if calendar is not None and not calendar.empty and 'Earnings Date' in calendar:
            dates = [pd.to_datetime(date) for date in calendar['Earnings Date'].tolist()]
            future_dates = [date for date in dates if date > pd.Timestamp.now()]
            if future_dates:
                return sorted(future_dates)
                
        # Method 3: earnings_dates (alternative)
        if hasattr(ticker_obj, 'earnings_dates'):
            dates = ticker_obj.earnings_dates
            if dates is not None and not dates.empty:
                future_dates = [date for date in dates if date > pd.Timestamp.now()]
                if future_dates:
                    return sorted(future_dates)
                    
    except Exception as e:
        st.warning(f"Error fetching earnings dates for {ticker_obj.ticker}: {str(e)}")
    return []

# ========== TECHNICAL INDICATORS ==========
def calculate_momentum(hist):
    if hist is None or hist.empty or len(hist) < 20:
        return {
            "EMA20": None, "EMA50": None, "EMA200": None, "RSI": None,
            "MACD_Hist": None, "ADX": None, "Volume_Ratio": None,
            "Momentum_Score": 0, "Trend": "→ Neutral"
        }
    close = hist['Close']
    high = hist['High']
    low = hist['Low']
    volume = hist['Volume']
    
    # Moving Averages
    ema20 = close.ewm(span=20).mean().iloc[-1] if len(close) >= 20 else None
    ema50 = close.ewm(span=50).mean().iloc[-1] if len(close) >= 50 else None
    ema200 = close.ewm(span=200).mean().iloc[-1] if len(close) >= 200 else None
    
    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean().iloc[-1] if len(gain) >= 14 else None
    avg_loss = loss.rolling(14).mean().iloc[-1] if len(loss) >= 14 else None
    if avg_loss and avg_loss != 0:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
    else:
        rsi = None

    # MACD
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9).mean()
    macd_hist = (macd.iloc[-1] - macd_signal.iloc[-1]) if len(macd) > 0 and len(macd_signal) > 0 else None

    # Volume
    vol_avg_20 = volume.rolling(20).mean().iloc[-1] if len(volume) >= 20 else None

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

    # Momentum Score (0-100)
    momentum_score = 0
    try:
        if close.iloc[-1] and ema20 and ema50 and ema200 and close.iloc[-1] > ema20 > ema50 > ema200:
            momentum_score += 30
        if rsi and 60 < rsi < 80:
            momentum_score += 20
        if macd_hist and macd_hist > 0:
            momentum_score += 15
        if vol_avg_20 and volume.iloc[-1] > vol_avg_20 * 1.2:
            momentum_score += 10
        if adx and adx > 25:
            momentum_score += 15
        if plus_di_last and minus_di_last and plus_di_last > minus_di_last:
            momentum_score += 10
    except Exception:
        momentum_score += 0

    return {
        "EMA20": round(ema20, 2) if ema20 is not None else None,
        "EMA50": round(ema50, 2) if ema50 is not None else None,
        "EMA200": round(ema200, 2) if ema200 is not None else None,
        "RSI": round(rsi, 1) if rsi is not None else None,
        "MACD_Hist": round(macd_hist, 3) if macd_hist is not None else None,
        "ADX": round(adx, 1) if adx is not None else None,
        "Volume_Ratio": round(volume.iloc[-1]/vol_avg_20, 2) if vol_avg_20 and vol_avg_20 != 0 else None,
        "Momentum_Score": momentum_score,
        "Trend": "↑ Strong" if momentum_score >= 80 else 
                 "↑ Medium" if momentum_score >= 60 else 
                 "↗ Weak" if momentum_score >= 40 else "→ Neutral"
    }

# ========== TICKER PROCESSING ==========
@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_ticker_data(_ticker, exchange, yf_symbol):
    try:
        ticker_obj = yf.Ticker(yf_symbol)
        try:
            hist = safe_yfinance_fetch(ticker_obj)
            if hist is None or hist.empty or len(hist) < 20:
                return None
            earnings_dates = get_events_data(ticker_obj)
        except Exception as e:
            st.warning(f"Error fetching {_ticker}: {str(e)}")
            return None
        momentum_data = calculate_momentum(hist)
        price = round(hist['Close'].iloc[-1], 2) if len(hist['Close']) else None
        five_d_change = (
            round((hist['Close'].iloc[-1]/hist['Close'].iloc[-5]-1)*100, 1)
            if len(hist['Close']) >= 5 else None
        )
        return {
            "Symbol": _ticker,
            "Exchange": exchange,
            "Price": price,
            "5D_Change": five_d_change,
            **momentum_data,
            "Earnings_Dates": earnings_dates,
            "Last_Updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "YF_Symbol": yf_symbol
        }
    except Exception as e:
        st.warning(f"Error processing {_ticker}: {str(e)}")
        return None

# ========== STREAMLIT UI ==========
st.set_page_config(layout="wide", page_title="Russell 2000 Momentum Scanner")
st.title("🚀 Russell 2000 Momentum Scanner with Earnings Analysis")

# Initialize session state
if 'full_data_loaded' not in st.session_state:
    st.session_state.update({
        'full_data_loaded': False,
        'initial_results': [],
        'last_full_load': None,
        'filtered_results': [],
        'last_loaded_index': PRELOAD_SYMBOLS,
        'min_score': 50,
        'price_range': (5.0, 200.0),
        'earnings_window': "Next 2 weeks",
        'require_events': False
    })

# Load basic data
df = get_google_sheet_data()

# ========== FILTERS ==========
with st.sidebar:
    st.header("Momentum Filters")
    st.session_state.min_score = st.slider(
        "Minimum Momentum Score", 
        0, 100, 
        st.session_state.get('min_score', 50), 5
    )
    trend_options = ["↑ Strong", "↑ Medium", "↗ Weak"]
    selected_trends = st.multiselect(
        "Trend Strength", 
        options=trend_options, 
        default=trend_options
    )
    st.session_state.price_range = st.slider(
        "Price Range ($)", 
        0.0, 500.0, 
        st.session_state.get('price_range', (5.0, 200.0)), 5.0
    )
    exchange_options = df["Exchange"].unique()
    selected_exchanges = st.multiselect(
        "Exchanges", 
        options=exchange_options, 
        default=["NASDAQ", "NYSE"]
    )
    
    st.header("Earnings Date Filters")
    st.session_state.earnings_window = st.selectbox(
        "Earnings Coming Within:",
        ["Any time", "Next week", "Next 2 weeks", "Next month"],
        index=["Any time", "Next week", "Next 2 weeks", "Next month"].index(st.session_state.get("earnings_window", "Next 2 weeks"))
    )
    
    st.session_state.require_events = st.checkbox(
        "Only stocks with upcoming earnings",
        value=st.session_state.get('require_events', False)
    )
    
    if st.button("Reset All Filters"):
        st.session_state.min_score = 50
        st.session_state.price_range = (5.0, 200.0)
        st.session_state.earnings_window = "Next 2 weeks"
        st.session_state.require_events = False
        st.rerun()

# ========== FILTER APPLICATION ==========
def apply_event_filters(stock_data):
    """Apply the earnings date filters to the dataframe"""
    if not st.session_state.require_events:
        return stock_data
    
    today = datetime.now()
    
    if st.session_state.earnings_window == "Any time":
        return stock_data[
            stock_data.apply(lambda row: len(row.get('Earnings_Dates', [])) > 0, axis=1)
        ]
    
    # Convert time window to days
    earnings_days = {
        "Next week": 7,
        "Next 2 weeks": 14,
        "Next month": 30
    }[st.session_state.earnings_window]
    
    # Filter for stocks meeting earnings criteria
    def has_earnings_within(row):
        dates = row.get('Earnings_Dates', [])
        # Defensive: ensure dates are pd.Timestamp or datetime
        for date in dates:
            if not isinstance(date, (pd.Timestamp, datetime)):
                try:
                    date = pd.to_datetime(date)
                except Exception:
                    continue
            if (date - today).days <= earnings_days and (date - today).days >= 0:
                return True
        return False

    filtered = stock_data[
        stock_data.apply(has_earnings_within, axis=1)
    ]
    return filtered

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
                n_futures = len(futures) if len(futures) else 1
                for i, future in enumerate(as_completed(futures)):
                    try:
                        result = future.result()
                        if result:
                            new_results.append(result)
                            st.session_state.initial_results.append(result)
                    except Exception as e:
                        st.warning(f"Error processing future: {str(e)}")
                    if i % 10 == 0:
                        progress = min(100, int((i+1)/n_futures*100))
                        progress_bar.progress(progress)
                        status_text.text(f"Processed {i+1}/{n_futures} symbols")
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
                    n_futures = len(futures) if len(futures) else 1
                    for i, future in enumerate(as_completed(futures)):
                        try:
                            result = future.result()
                            if result:
                                results.append(result)
                        except Exception as e:
                            st.warning(f"Error processing future: {str(e)}")
                        if i % 10 == 0:
                            progress = min(100, int((i+1)/n_futures*100))
                            progress_bar.progress(progress)
                            status_text.text(f"Processed {i+1}/{n_futures} symbols")
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
    
    # Apply momentum filters
    filtered = filtered[
        (filtered["Momentum_Score"] >= st.session_state.min_score) &
        (filtered["Trend"].isin(selected_trends)) &
        (filtered["Price"].between(*st.session_state.price_range)) &
        (filtered["Exchange"].isin(selected_exchanges))
    ].copy()

    # Add "Upcoming Earnings Date" column - show the next earnings date if available
    def extract_next_earnings(dates):
        if dates and len(dates) > 0:
            # Get all future dates
            future_dates = [date for date in dates if (isinstance(date, (pd.Timestamp, datetime)) and date > datetime.now()) or (not isinstance(date, (pd.Timestamp, datetime)) and pd.to_datetime(date) > datetime.now())]
            if future_dates:
                next_date = min(future_dates)
                days_until = (next_date - datetime.now()).days
                return f"{next_date.strftime('%Y-%m-%d')} (in {days_until} days)"
        return "No upcoming earnings"
    
    filtered["Upcoming Earnings Date"] = filtered["Earnings_Dates"].apply(extract_next_earnings)
    
    # Apply event filters
    filtered = apply_event_filters(filtered)
    
    filtered = filtered.sort_values("Momentum_Score", ascending=False)
    st.session_state.filtered_results = filtered
    
    # Summary Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Stocks Found", len(filtered))
    avg_score = round(filtered["Momentum_Score"].mean(), 1) if not filtered.empty else 0
    col2.metric("Avg Momentum Score", avg_score)
    strong_trends = len(filtered[filtered["Trend"] == "↑ Strong"]) if not filtered.empty else 0
    col3.metric("Strong Trends", strong_trends)
    
    if not filtered.empty:
        display_df = filtered.copy()
        # Results Table
        st.dataframe(
            display_df[[
                "Symbol", "Exchange", "Price", "5D_Change", 
                "Momentum_Score", "Trend", "Upcoming Earnings Date", "Last_Updated"
            ]],
            use_container_width=True,
            height=600,
            column_config={
                "Price": st.column_config.NumberColumn(format="$%.2f"),
                "5D_Change": st.column_config.NumberColumn(format="%.1f%%"),
                "Momentum_Score": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100),
                "Upcoming Earnings Date": st.column_config.TextColumn()
            }
        )
    else:
        st.warning("No stocks match your current filters. Try adjusting your criteria.")
        with st.expander("Filter Suggestions"):
            st.markdown(f"""
            - **Lower the Minimum Momentum Score** (currently {st.session_state.min_score})
            - **Widen the Price Range** (currently ${st.session_state.price_range[0]} - ${st.session_state.price_range[1]})
            - **Include more Trend Strength options**
            - **Relax earnings date requirements**
            - **Try different Exchange selections**
            """)

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
                
                tab1, tab2 = st.tabs(["Price Chart", "Momentum Indicators"])
                
                with tab1:
                    ticker = yf.Ticker(symbol_data["YF_Symbol"])
                    hist = safe_yfinance_fetch(ticker, "6mo")
                    if hist is None or hist.empty:
                        st.warning("No historical data available for this symbol.")
                    else:
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
                        
                        # Add earnings markers
                        if symbol_data["Earnings_Dates"]:
                            for date in symbol_data["Earnings_Dates"]:
                                fig.add_vline(x=date, line_color="red", line_dash="dash",
                                            annotation_text="Earnings", annotation_position="top left")
                        
                        fig.update_layout(
                            title=f"{selected_symbol} Price with EMAs and Earnings",
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
                        st.metric("MACD Histogram", round(symbol_data["MACD_Hist"], 3) if symbol_data["MACD_Hist"] is not None else "N/A")
                        st.metric("Volume vs Avg", f"{symbol_data['Volume_Ratio']:.2f}x" if symbol_data["Volume_Ratio"] is not None else "N/A")
                        st.metric("ADX (Trend Strength)", symbol_data["ADX"] if symbol_data["ADX"] is not None else "N/A")
                    st.progress(symbol_data["Momentum_Score"]/100, text="Momentum Strength")
                    
                    # Display upcoming earnings
                    st.subheader("Upcoming Earnings")
                    if symbol_data["Earnings_Dates"]:
                        for date in symbol_data["Earnings_Dates"]:
                            if not isinstance(date, (pd.Timestamp, datetime)):
                                try:
                                    date = pd.to_datetime(date)
                                except Exception:
                                    continue
                            st.write(f"📅 Earnings: {date.strftime('%Y-%m-%d')} (in {(date - datetime.now()).days} days)")
                    else:
                        st.write("No upcoming earnings found")
                    
            except Exception as e:
                st.error(f"Error loading {selected_symbol}: {str(e)}")
else:
    st.warning("No stocks available for detailed analysis. Please load data first.")

# ========== SYSTEM CONTROLS ==========
with st.expander("System Controls"):
    if st.button("Clear Cache & Reload"):
        st.cache_data.clear()
        st.session_state.clear()
        st.rerun()
    st.write(f"Last full load: {st.session_state.last_full_load}")
    st.write(f"Total symbols loaded: {len(st.session_state.initial_results)}")
    st.write(f"Next batch starts at index: {st.session_state.last_loaded_index}")
