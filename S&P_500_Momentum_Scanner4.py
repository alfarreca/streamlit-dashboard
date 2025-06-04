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
import numpy as np

# ========== CONFIGURATION ==========
MAX_WORKERS = 8
REQUEST_DELAY = (0.5, 2.0)
CACHE_TTL = 3600 * 12  # 12 hours
PRELOAD_SYMBOLS = 100
BATCH_SIZE = 300
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
    """Fetch historical data with retry logic and random delay"""
    time.sleep(random.uniform(*REQUEST_DELAY))
    return ticker.history(period=period)

# ========== DATA FETCHING ==========
@st.cache_data(ttl=CACHE_TTL)
def get_google_sheet_data():
    """Fetch stock symbols from Google Sheets"""
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

# === DI CROSSOVER SECTION ===
def calculate_di_crossovers(hist, period=14):
    """Calculate +DI, -DI, and crossovers for the given OHLCV DataFrame."""
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

    # Crossover detection
    bullish_crossover = (plus_di > minus_di) & (plus_di.shift(1) <= minus_di.shift(1))
    bearish_crossover = (minus_di > plus_di) & (minus_di.shift(1) <= plus_di.shift(1))
    return plus_di, minus_di, bullish_crossover, bearish_crossover

def calculate_momentum(hist):
    """Calculate technical indicators and momentum score (0-100)"""
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

    # RSI (14-period)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14).mean().iloc[-1]
    avg_loss = loss.ewm(alpha=1/14).mean().iloc[-1]
    rs = avg_gain / avg_loss if avg_loss != 0 else 100
    rsi = 100 - (100 / (1 + rs))

    # MACD (12, 26, 9)
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9).mean()
    macd_hist = macd.iloc[-1] - macd_signal.iloc[-1]

    # Volume Analysis
    vol_avg_20 = volume.rolling(20).mean().iloc[-1]

    # ADX (Trend Strength)
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

    # === DI CROSSOVER SECTION ===
    plus_di_c, minus_di_c, bullish_cross, bearish_cross = calculate_di_crossovers(hist)
    # Grab the most recent (last available) crossover values
    last_bullish = bool(bullish_cross.iloc[-1])
    last_bearish = bool(bearish_cross.iloc[-1])

    # Momentum Score Calculation (0-100)
    momentum_score = 0

    # 1. Price above EMAs (30 points max)
    if close.iloc[-1] > ema20 > ema50 > ema200:
        momentum_score += 30
    elif close.iloc[-1] > ema50 > ema200:
        momentum_score += 20
    elif close.iloc[-1] > ema200:
        momentum_score += 10

    # 2. RSI Conditions (20 points max)
    if 60 < rsi < 80:
        momentum_score += 20
    elif 50 < rsi <= 60 or 80 <= rsi < 90:
        momentum_score += 10

    # 3. MACD (15 points)
    if macd_hist > 0:
        momentum_score += 15

    # 4. Volume Spike (15 points max)
    if volume.iloc[-1] > vol_avg_20 * 1.5:
        momentum_score += 15
    elif volume.iloc[-1] > vol_avg_20 * 1.2:
        momentum_score += 10

    # 5. ADX Trend Strength (20 points max)
    if adx > 30:
        momentum_score += 20
    elif adx > 25:
        momentum_score += 15
    elif adx > 20:
        momentum_score += 10

    # Cap at 100
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
        # === DI CROSSOVER SECTION ===
        "Bullish_Crossover": last_bullish,
        "Bearish_Crossover": last_bearish,
        "plus_di_last": round(plus_di_c.iloc[-1], 1) if not np.isnan(plus_di_c.iloc[-1]) else None,
        "minus_di_last": round(minus_di_c.iloc[-1], 1) if not np.isnan(minus_di_c.iloc[-1]) else None,
    }

# ========== TICKER PROCESSING ==========
@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_ticker_data(_ticker, exchange, yf_symbol):
    """Fetch and process data for a single ticker"""
    try:
        ticker_obj = yf.Ticker(yf_symbol)
        hist = safe_yfinance_fetch(ticker_obj)
        if hist.empty or len(hist) < 50:
            return None

        momentum_data = calculate_momentum(hist)
        if not momentum_data:
            return None

        # Calculate price changes
        current_price = hist['Close'].iloc[-1]
        five_day_change = ((current_price/hist['Close'].iloc[-5]-1)*100) if len(hist) >= 5 else None
        twenty_day_change = ((current_price/hist['Close'].iloc[-20]-1)*100) if len(hist) >= 20 else None

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
# ... (all your existing code remains unchanged up to display_symbol_details)

def display_results(filtered_df):
    """Display the filtered results in a professional table"""
    if filtered_df.empty:
        st.warning("No stocks match your current filters. Try adjusting your criteria.")
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Stocks Found", len(filtered_df))
    with col2:
        st.metric("Avg Momentum Score", round(filtered_df["Momentum_Score"].mean(), 1))
    with col3:
        st.metric("Strong Trends", len(filtered_df[filtered_df["Trend"] == "↑ Strong"]))
    with col4:
        st.metric("Avg Volume Ratio", round(filtered_df["Volume_Ratio"].mean(), 2))

    # === DI CROSSOVER SECTION: show crossover columns in summary
    st.dataframe(
        filtered_df[[
            "Symbol", "Exchange", "Price", "5D_Change", "20D_Change",
            "Momentum_Score", "Trend", "RSI", "MACD_Hist",
            "Volume_Ratio", "ADX", "Bullish_Crossover", "Bearish_Crossover", "Last_Updated"
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
            "Trend": st.column_config.TextColumn(width="small"),
            "Bullish_Crossover": st.column_config.CheckboxColumn(),
            "Bearish_Crossover": st.column_config.CheckboxColumn()
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
            tab1, tab2, tab3, tab4 = st.tabs(["Price Chart", "Technical Indicators", "DI Crossovers", "Fundamentals"])

            with tab1:
                ticker = yf.Ticker(symbol_data["YF_Symbol"])
                hist = safe_yfinance_fetch(ticker, "6mo")
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
                st.progress(symbol_data["Momentum_Score"]/100, text="Momentum Strength")
                st.progress(symbol_data["RSI"]/100, text="RSI")
                st.progress(min(symbol_data["ADX"]/50, 1.0), text="ADX Trend Strength")

            # === DI CROSSOVER SECTION: chart with crossovers for selected symbol
            with tab3:
                ticker = yf.Ticker(symbol_data["YF_Symbol"])
                hist = safe_yfinance_fetch(ticker, "6mo")
                plus_di, minus_di, bull_cross, bear_cross = calculate_di_crossovers(hist)
                st.write("Recent +DI/-DI Crossovers:")
                cross_df = pd.DataFrame({
                    "Date": hist.index,
                    "+DI": plus_di,
                    "-DI": minus_di,
                    "Bullish_Crossover": bull_cross,
                    "Bearish_Crossover": bear_cross
                }).set_index("Date")
                st.dataframe(cross_df.tail(20)[["+DI", "-DI", "Bullish_Crossover", "Bearish_Crossover"]])

                import matplotlib.pyplot as plt
                fig, ax = plt.subplots()
                plus_di.plot(ax=ax, label="+DI", color='green')
                minus_di.plot(ax=ax, label="-DI", color='red')
                ax.scatter(
                    cross_df.index[cross_df["Bullish_Crossover"]],
                    plus_di[cross_df["Bullish_Crossover"]],
                    marker='^', color='blue', label='Bullish Crossover'
                )
                ax.scatter(
                    cross_df.index[cross_df["Bearish_Crossover"]],
                    minus_di[cross_df["Bearish_Crossover"]],
                    marker='v', color='black', label='Bearish Crossover'
                )
                ax.legend()
                ax.set_title(f"{selected_symbol} +DI/-DI and Crossovers")
                st.pyplot(fig)

            with tab4:
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

# The rest of your code (setup_page, filters, batch loading, main, etc.) remains unchanged.

if __name__ == "__main__":
    main()
