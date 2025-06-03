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
import pytz

# ========== CONFIGURATION ==========
MAX_WORKERS = 8  # Increased for better performance
REQUEST_DELAY = (0.5, 2.0)
CACHE_TTL = 3600 * 12  # 12 hours cache
PRELOAD_SYMBOLS = 100  # Increased initial load
MAX_RETRIES = 3
BATCH_SIZE = 300
TIMEZONE = 'America/New_York'  # Added timezone support

# ========== SETUP ==========
yf.set_tz_cache_location("cache")

# ========== RETRY MECHANISM ==========
@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
def safe_yfinance_fetch(ticker, period="3mo"):
    """Fetch historical data with retry logic and random delay"""
    time.sleep(random.uniform(*REQUEST_DELAY))
    return ticker.history(period=period)

# ========== DATA FETCHING ==========
@st.cache_data(ttl=CACHE_TTL)
def get_google_sheet_data():
    """Fetch stock symbols from Google Sheets with error handling"""
    try:
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
        SERVICE_ACCOUNT_INFO = st.secrets["GCP_SERVICE_ACCOUNT"]
        creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key("1sNYUiP4Pl8GVYQ1S7Ltc4ETv-ctOA1RVCdYkMb5xjjg").sheet1
        df = pd.DataFrame(sheet.get_all_records()).dropna(subset=["Symbol", "Exchange"]).drop_duplicates("Symbol")
        return df
    except Exception as e:
        st.error(f"Failed to load Google Sheet data: {str(e)}")
        return pd.DataFrame(columns=["Symbol", "Exchange"])

def exchange_suffix(ex: str) -> str:
    """Map exchange codes to Yahoo Finance suffixes"""
    suffix_map = {
        "ETR": "DE", "EPA": "PA", "LON": "L", "BIT": "MI", "STO": "ST",
        "SWX": "SW", "TSE": "TO", "ASX": "AX", "HKG": "HK"
    }
    return suffix_map.get(ex.upper(), "")

def map_to_yfinance_symbol(symbol: str, exchange: str) -> str:
    """Convert symbol to Yahoo Finance format"""
    if exchange.upper() in ["NYSE", "NASDAQ"]:
        return symbol
    suffix = exchange_suffix(exchange)
    return f"{symbol}.{suffix}" if suffix else symbol

# ========== TECHNICAL INDICATORS ==========
def calculate_momentum(hist):
    """Calculate technical indicators and momentum score"""
    if hist.empty or len(hist) < 50:  # Require at least 50 data points
        return None
        
    close = hist['Close']
    high = hist['High']
    low = hist['Low']
    volume = hist['Volume']
    
    # Moving Averages
    ema20 = close.ewm(span=20).mean().iloc[-1]
    ema50 = close.ewm(span=50).mean().iloc[-1]
    ema200 = close.ewm(span=200).mean().iloc[-1]
    
    # RSI with smoothing
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
    
    # Volume analysis
    vol_avg_20 = volume.rolling(20).mean().iloc[-1]
    
    # ADX calculation with error handling
    try:
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
    except:
        adx = 0
        plus_di_last = 0
        minus_di_last = 0

    # Enhanced Momentum Score (0-100)
    momentum_score = 0
    
    # Price above EMAs (30 points)
    if close.iloc[-1] > ema20 > ema50 > ema200:
        momentum_score += 30
    elif close.iloc[-1] > ema50 > ema200:
        momentum_score += 20
    elif close.iloc[-1] > ema200:
        momentum_score += 10
        
    # RSI conditions (20 points)
    if 60 < rsi < 80:
        momentum_score += 20
    elif 50 < rsi <= 60 or 80 <= rsi < 90:
        momentum_score += 10
        
    # MACD (15 points)
    if macd_hist > 0:
        momentum_score += 15
        
    # Volume spike (10 points)
    if volume.iloc[-1] > vol_avg_20 * 1.5:
        momentum_score += 15
    elif volume.iloc[-1] > vol_avg_20 * 1.2:
        momentum_score += 10
        
    # Trend strength (20 points)
    if adx > 30:
        momentum_score += 20
    elif adx > 25:
        momentum_score += 15
    elif adx > 20:
        momentum_score += 10
        
    # Directional movement (10 points)
    if plus_di_last > minus_di_last:
        momentum_score += 10
            
    return {
        "EMA20": round(ema20, 2),
        "EMA50": round(ema50, 2),
        "EMA200": round(ema200, 2),
        "RSI": round(rsi, 1),
        "MACD_Hist": round(macd_hist, 3),
        "ADX": round(adx, 1),
        "Volume_Ratio": round(volume.iloc[-1]/vol_avg_20, 2),
        "Momentum_Score": min(100, momentum_score),  # Cap at 100
        "Trend": "↑ Strong" if momentum_score >= 80 else 
                 "↑ Medium" if momentum_score >= 60 else 
                 "↗ Weak" if momentum_score >= 40 else "→ Neutral"
    }

# ========== TICKER PROCESSING ==========
@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_ticker_data(_ticker, exchange, yf_symbol):
    """Fetch and process data for a single ticker"""
    try:
        ticker_obj = yf.Ticker(yf_symbol)
        try:
            hist = safe_yfinance_fetch(ticker_obj)
        except Exception as e:
            st.warning(f"Error fetching {_ticker}: {str(e)}")
            return None
            
        if hist.empty or len(hist) < 50:
            return None

        momentum_data = calculate_momentum(hist)
        if not momentum_data:
            return None
            
        # Calculate additional metrics
        current_price = hist['Close'].iloc[-1]
        five_day_change = ((current_price/hist['Close'].iloc[-5]-1)*100 if len(hist) >= 5 else None
        twenty_day_change = ((current_price/hist['Close'].iloc[-20]-1)*100 if len(hist) >= 20 else None)
        
        return {
            "Symbol": _ticker,
            "Exchange": exchange,
            "Price": round(current_price, 2),
            "5D_Change": round(five_day_change, 1) if five_day_change else None,
            "20D_Change": round(twenty_day_change, 1) if twenty_day_change else None,
            **momentum_data,
            "Last_Updated": datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d %H:%M"),
            "YF_Symbol": yf_symbol
        }
    except Exception as e:
        st.warning(f"Error processing {_ticker}: {str(e)}")
        return None

# ========== STREAMLIT UI ==========
def setup_page():
    """Configure page layout and styles"""
    st.set_page_config(
        layout="wide", 
        page_title="Russell 2000 Momentum Scanner",
        page_icon="📈"
    )
    
    # Custom CSS
    st.markdown("""
    <style>
        .stProgress > div > div > div > div {
            background-color: #1f77b4;
        }
        .metric-container {
            padding: 15px;
            border-radius: 10px;
            background-color: #f0f2f6;
            margin-bottom: 10px;
        }
        .stDataFrame {
            border-radius: 10px;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 8px 16px;
            border-radius: 4px 4px 0 0;
        }
        .stTabs [aria-selected="true"] {
            background-color: #f0f2f6;
        }
    </style>
    """, unsafe_allow_html=True)

def initialize_session_state():
    """Initialize or reset session state variables"""
    if 'full_data_loaded' not in st.session_state:
        st.session_state.update({
            'full_data_loaded': False,
            'initial_results': [],
            'last_full_load': None,
            'filtered_results': pd.DataFrame(),
            'last_loaded_index': PRELOAD_SYMBOLS,
            'selected_symbol': None
        })

def create_sidebar_filters(df):
    """Create the filter controls in the sidebar"""
    with st.sidebar:
        st.image("https://via.placeholder.com/150x50?text=Momentum+Scanner", width=150)
        st.header("🔍 Filters")
        
        # Basic filters
        min_score = st.slider("Minimum Momentum Score", 0, 100, 70, 5,
                             help="Filter stocks by their momentum score (0-100)")
        
        trend_options = ["↑ Strong", "↑ Medium", "↗ Weak"]
        selected_trends = st.multiselect("Trend Strength", options=trend_options, default=trend_options,
                                       help="Filter by trend strength category")
        
        price_range = st.slider("Price Range ($)", 0.0, 500.0, (10.0, 200.0), 5.0,
                               help="Filter by stock price range")
        
        # Exchange filter
        exchange_options = df["Exchange"].unique()
        selected_exchanges = st.multiselect("Exchanges", options=exchange_options, default=["NASDAQ", "NYSE"],
                                          help="Filter by stock exchange")
        
        # Advanced filters
        with st.expander("Advanced Filters"):
            adx_threshold = st.slider("Minimum ADX (Trend Strength)", 10, 50, 25, 1,
                                    help="Average Directional Index - higher values indicate stronger trends")
            
            rsi_range = st.slider("RSI Range", 0, 100, (30, 80),
                                 help="Relative Strength Index range (typically 30-70)")
            
            volume_ratio = st.slider("Minimum Volume Ratio", 0.5, 3.0, 1.2, 0.1,
                                   help="Current volume vs 20-day average volume ratio")
        
        st.markdown("---")
        st.markdown("**Data Last Updated:**")
        st.caption(datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d %H:%M %Z"))
        
    return {
        "min_score": min_score,
        "selected_trends": selected_trends,
        "price_range": price_range,
        "selected_exchanges": selected_exchanges,
        "adx_threshold": adx_threshold,
        "rsi_range": rsi_range,
        "volume_ratio": volume_ratio
    }

def load_data_batch(df, start_idx, end_idx, progress_callback=None):
    """Load a batch of ticker data"""
    subset = df[df["Exchange"].isin(st.session_state.filters["selected_exchanges"])].iloc[start_idx:end_idx]
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
            
            if progress_callback and i % 10 == 0:
                progress_callback(i+1, len(futures))
    
    return new_results

def display_results(filtered_df):
    """Display the filtered results"""
    if filtered_df.empty:
        st.warning("No stocks match your current filters. Try adjusting your criteria.")
        return
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Stocks Found", len(filtered_df))
    with col2:
        st.metric("Avg Momentum Score", round(filtered_df["Momentum_Score"].mean(), 1))
    with col3:
        st.metric("Strong Trends", len(filtered_df[filtered_df["Trend"] == "↑ Strong"]))
    with col4:
        st.metric("Avg Volume Ratio", round(filtered_df["Volume_Ratio"].mean(), 2))
    
    # Main dataframe display
    st.dataframe(
        filtered_df[[
            "Symbol", "Exchange", "Price", "5D_Change", "20D_Change",
            "Momentum_Score", "Trend", "RSI", "MACD_Hist", 
            "Volume_Ratio", "ADX", "Last_Updated"
        ]].sort_values("Momentum_Score", ascending=False),
        use_container_width=True,
        height=600,
        column_config={
            "Symbol": st.column_config.TextColumn(width="small"),
            "Exchange": st.column_config.TextColumn(width="small"),
            "Price": st.column_config.NumberColumn(format="$%.2f", width="small"),
            "5D_Change": st.column_config.NumberColumn(format="%.1f%%", width="small"),
            "20D_Change": st.column_config.NumberColumn(format="%.1f%%", width="small"),
            "Volume_Ratio": st.column_config.NumberColumn(format="%.2fx", width="small"),
            "Momentum_Score": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100),
            "RSI": st.column_config.NumberColumn(format="%.1f"),
            "MACD_Hist": st.column_config.NumberColumn(format="%.3f"),
            "ADX": st.column_config.NumberColumn(format="%.1f"),
            "Trend": st.column_config.TextColumn(width="small")
        },
        hide_index=True
    )

def display_symbol_details(selected_symbol):
    """Display detailed analysis for a selected symbol"""
    if not selected_symbol:
        return
        
    with st.spinner(f'Loading {selected_symbol} analysis...'):
        try:
            symbol_data = st.session_state.filtered_results[
                st.session_state.filtered_results["Symbol"] == selected_symbol
            ].iloc[0]
            
            st.subheader(f"📊 {selected_symbol} Detailed Analysis")
            tab1, tab2, tab3 = st.tabs(["Price Chart", "Technical Indicators", "Fundamentals"])
            
            with tab1:
                ticker = yf.Ticker(symbol_data["YF_Symbol"])
                hist = safe_yfinance_fetch(ticker, "6mo")
                
                # Price chart with EMAs
                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=hist.index,
                    open=hist['Open'],
                    high=hist['High'],
                    low=hist['Low'],
                    close=hist['Close'],
                    name='OHLC'
                ))
                fig.add_trace(go.Scatter(
                    x=hist.index, y=hist['Close'].ewm(span=20).mean(),
                    name='20 EMA', line=dict(color='orange', width=2)
                ))
                fig.add_trace(go.Scatter(
                    x=hist.index, y=hist['Close'].ewm(span=50).mean(),
                    name='50 EMA', line=dict(color='red', width=2)
                ))
                fig.add_trace(go.Scatter(
                    x=hist.index, y=hist['Close'].ewm(span=200).mean(),
                    name='200 EMA', line=dict(color='purple', width=2)
                ))
                fig.update_layout(
                    title=f"{selected_symbol} Price Chart",
                    height=500,
                    showlegend=True,
                    xaxis_rangeslider_visible=False
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with tab2:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Current Price", f"${symbol_data['Price']:,.2f}")
                    st.metric("5-Day Change", f"{symbol_data['5D_Change']:.1f}%")
                    st.metric("20-Day Change", f"{symbol_data['20D_Change']:.1f}%")
                
                with col2:
                    st.metric("Momentum Score", symbol_data["Momentum_Score"])
                    st.metric("Trend Strength", symbol_data["Trend"])
                    st.metric("ADX", symbol_data["ADX"])
                
                with col3:
                    st.metric("RSI", symbol_data["RSI"])
                    st.metric("MACD Histogram", f"{symbol_data['MACD_Hist']:.3f}")
                    st.metric("Volume Ratio", f"{symbol_data['Volume_Ratio']:.2f}x")
                
                # Progress bars
                st.progress(symbol_data["Momentum_Score"]/100, text="Momentum Strength")
                st.progress(min(100, symbol_data["RSI"]), text="RSI")
                st.progress(min(100, symbol_data["ADX"]/50*100), text="ADX Trend Strength")
            
            with tab3:
                try:
                    info = ticker.info
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.metric("Market Cap", f"${info.get('marketCap', 'N/A')/1e9:,.2f}B" if info.get('marketCap') else "N/A")
                        st.metric("P/E Ratio", info.get('trailingPE', 'N/A'))
                        st.metric("EPS", info.get('trailingEps', 'N/A'))
                        st.metric("Dividend Yield", f"{info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else "0%")
                    
                    with col2:
                        st.metric("52 Week High", f"${info.get('fiftyTwoWeekHigh', 'N/A'):,.2f}")
                        st.metric("52 Week Low", f"${info.get('fiftyTwoWeekLow', 'N/A'):,.2f}")
                        st.metric("Beta", info.get('beta', 'N/A'))
                        st.metric("Average Volume", f"{info.get('averageVolume', 'N/A'):,.0f}")
                except:
                    st.warning("Could not load fundamental data for this stock")
            
        except Exception as e:
            st.error(f"Error loading {selected_symbol}: {str(e)}")

def main():
    """Main application function"""
    setup_page()
    st.title("🚀 Russell 2000 Momentum Scanner")
    st.markdown("""
    Identify high-momentum stocks in the Russell 2000 index using technical indicators.
    Filter stocks by momentum score, trend strength, and other technical factors.
    """)
    
    # Initialize session state and load data
    initialize_session_state()
    df = get_google_sheet_data()
    
    # Create filters and store in session state
    st.session_state.filters = create_sidebar_filters(df)
    
    # Initial data load
    if not st.session_state.initial_results:
        with st.spinner(f'Loading initial {PRELOAD_SYMBOLS} symbols...'):
            def progress_callback(current, total):
                st.write(f"Processed {current}/{total} symbols")
                
            new_results = load_data_batch(
                df, 
                0, 
                PRELOAD_SYMBOLS,
                progress_callback
            )
            st.success(f"Loaded {len(new_results)} initial symbols")
    
    # Batch loading buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button('Load Next 300 Tickers', help="Load the next batch of 300 tickers") and not st.session_state.full_data_loaded:
            with st.spinner('Loading next 300 symbols...'):
                start_idx = st.session_state.last_loaded_index
                end_idx = start_idx + BATCH_SIZE
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                def update_progress(current, total):
                    progress = min(100, int((current)/total*100))
                    progress_bar.progress(progress)
                    status_text.text(f"Processed {current}/{total} symbols")
                
                new_results = load_data_batch(df, start_idx, end_idx, update_progress)
                st.session_state.last_loaded_index = end_idx
                
                progress_bar.empty()
                status_text.empty()
                st.success(f"Loaded {len(new_results)} additional symbols")
                st.rerun()

    with col2:
        if st.button('Load Full Dataset', help="Load all available tickers (may take several minutes)"):
            if (st.session_state.last_full_load and 
                (datetime.now() - st.session_state.last_full_load) < timedelta(hours=1)):
                st.warning("Please wait 1 hour between full loads to avoid rate limits")
            else:
                with st.spinner('Loading full dataset (5-10 minutes)...'):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    def update_progress(current, total):
                        progress = min(100, int((current)/total*100))
                        progress_bar.progress(progress)
                        status_text.text(f"Processed {current}/{total} symbols")
                    
                    filtered_df = df[df["Exchange"].isin(st.session_state.filters["selected_exchanges"])]
                    new_results = load_data_batch(filtered_df, 0, len(filtered_df), update_progress)
                    
                    st.session_state.initial_results = new_results
                    st.session_state.full_data_loaded = True
                    st.session_state.last_full_load = datetime.now()
                    st.session_state.last_loaded_index = len(df)
                    
                    progress_bar.empty()
                    status_text.empty()
                    st.success(f"Loaded {len(new_results)} symbols")
    
    # Filter results
    if st.session_state.initial_results:
        filtered = pd.DataFrame(st.session_state.initial_results)
        filters = st.session_state.filters
        
        filtered = filtered[
            (filtered["Momentum_Score"] >= filters["min_score"]) &
            (filtered["Trend"].isin(filters["selected_trends"])) &
            (filtered["Price"].between(*filters["price_range"])) &
            (filtered["Exchange"].isin(filters["selected_exchanges"])) &
            (filtered["ADX"] >= filters["adx_threshold"]) &
            (filtered["RSI"].between(*filters["rsi_range"])) &
            (filtered["Volume_Ratio"] >= filters["volume_ratio"])
        ].sort_values("Momentum_Score", ascending=False)
        
        st.session_state.filtered_results = filtered
        
        # Display results
        display_results(filtered)
        
        # Symbol selector
        if not filtered.empty:
            st.session_state.selected_symbol = st.selectbox(
                "Select symbol for detailed analysis:", 
                options=filtered["Symbol"],
                index=0
            )
            
            # Detailed analysis
            st.divider()
            display_symbol_details(st.session_state.selected_symbol)
    
    # System controls
    with st.expander("System Information"):
        st.write(f"**Last full load:** {st.session_state.last_full_load}")
        st.write(f"**Total symbols loaded:** {len(st.session_state.initial_results)}")
        st.write(f"**Next batch starts at index:** {st.session_state.last_loaded_index}")
        st.write(f"**Cache expiration:** {CACHE_TTL/3600:.1f} hours")
        
        if st.button("Clear Cache & Reload", help="Clear all cached data and reload the application"):
            st.cache_data.clear()
            st.session_state.clear()
            st.rerun()

if __name__ == "__main__":
    main()
