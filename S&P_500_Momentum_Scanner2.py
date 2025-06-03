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
        five_day_change = ((current_price/hist['Close'].iloc[-5]-1)*100) if len(hist) >= 5 else None
        twenty_day_change = ((current_price/hist['Close'].iloc[-20]-1)*100) if len(hist) >= 20 else None
        
        return {
            "Symbol": _ticker,
            "Exchange": exchange,
            "Price": round(current_price, 2),
            "5D_Change": round(five_day_change, 1) if five_day_change is not None else None,
            "20D_Change": round(twenty_day_change, 1) if twenty_day_change is not None else None,
            **momentum_data,
            "Last_Updated": datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d %H:%M"),
            "YF_Symbol": yf_symbol
        }
    except Exception as e:
        st.warning(f"Error processing {_ticker}: {str(e)}")
        return None

# ... rest of your script remains unchanged ...
