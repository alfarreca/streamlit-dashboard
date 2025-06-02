# Add this to your imports
from typing import Optional, Dict, Any
import json

# Add EODHD configuration
EODHD_BASE_URL = "https://eodhistoricaldata.com/api"
EODHD_CACHE_TTL = 3600  # 1 hour cache for EODHD data

# Replace the get_ticker_data function with this version
@st.cache_data(ttl=EODHD_CACHE_TTL)
def get_ticker_data(_ticker: str, exchange: str, yf_symbol: str, attempt: int = 0) -> (Optional[Dict[str, Any]], Optional[str]):
    try:
        rate_limiter.check_rate_limit()
        
        # Use EODHD for ETFs, Yahoo Finance for others
        if exchange.upper() in ["NYSE", "NASDAQ", "BATS"] and _ticker in ETF_SYMBOLS:
            return get_eodhd_data(_ticker, yf_symbol)
        else:
            return get_yfinance_data(_ticker, exchange, yf_symbol, attempt)
            
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"{_ticker}: {error_msg}")
        return None, error_msg

def get_eodhd_data(symbol: str, yf_symbol: str) -> (Optional[Dict[str, Any]], Optional[str]):
    """Fetch ETF data from EODHD API"""
    try:
        api_key = st.secrets["eodhd"]["api_key"]
        endpoint = f"{EODHD_BASE_URL}/real-time/{yf_symbol}"
        params = {
            'api_token': api_key,
            'fmt': 'json',
            'filter': 'last_close,high,low,change_p,change,volume'
        }
        
        # Add rate limiting
        rate_limiter.check_rate_limit()
        time.sleep(random.uniform(*REQUEST_DELAY))
        
        response = requests.get(endpoint, params=params)
        response.raise_for_status()
        data = response.json()
        
        if isinstance(data, dict) and 'code' in data:
            error_msg = f"EODHD API Error: {data.get('message', 'Unknown error')}"
            logger.error(f"{symbol}: {error_msg}")
            return None, error_msg
        
        # Get historical data for MA calculations
        hist_endpoint = f"{EODHD_BASE_URL}/eod/{yf_symbol}"
        hist_params = {
            'api_token': api_key,
            'fmt': 'json',
            'period': 'd',
            'order': 'd',
            'from': (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
        }
        
        hist_response = requests.get(hist_endpoint, params=hist_params)
        hist_response.raise_for_status()
        hist_data = hist_response.json()
        
        if not isinstance(hist_data, list) or len(hist_data) < 20:
            error_msg = "Insufficient historical data from EODHD"
            logger.warning(f"{symbol}: {error_msg}")
            return None, error_msg
        
        # Process historical data
        hist_df = pd.DataFrame(hist_data)
        hist_df['date'] = pd.to_datetime(hist_df['date'])
        hist_df.set_index('date', inplace=True)
        hist_df['close'] = pd.to_numeric(hist_df['close'])
        
        # Calculate metrics
        last_price = data['last_close']
        ma10 = hist_df['close'].rolling(window=10).mean().iloc[-1]
        ma20 = hist_df['close'].rolling(window=20).mean().iloc[-1]
        change_pct = data.get('change_p', 0)
        volume = data.get('volume', 0)
        volume_ma10 = hist_df['volume'].rolling(window=10).mean().iloc[-1]
        
        # Create chart
        chart = create_eodhd_chart(symbol, hist_df)
        if chart is None:
            error_msg = "Failed to create chart from EODHD data"
            return None, error_msg
            
        rate_limiter.add_request()
        
        return {
            "Symbol": symbol,
            "Exchange": "ETF",
            "Price": safe_round(last_price, 2),
            "5D Change %": safe_round(change_pct, 2),  # Using daily change as proxy
            "MA10": safe_round(ma10, 2),
            "MA20": safe_round(ma20, 2),
            "Divergence": safe_round(((last_price - ma10) / ma10 * 100), 2),
            "% vs MA10": f"{safe_round(((last_price - ma10) / ma10 * 100), 2)}%",
            "Volume": int(volume),
            "Vol MA10": int(volume_ma10),
            "Signal": "🟢 Buy" if (last_price > ma10 and ma10 > ma20) else "🔴 Sell" if (last_price < ma10 and ma10 < ma20) else "🟡 Neutral",
            "Crossover": calculate_crossover(hist_df['close']),
            "P/E Ratio": None,  # Not available from EODHD real-time
            "Dividend Yield": None,  # Would need separate endpoint
            "Dividend Payout Ratio (%)": None,
            "Free Cash Flow (LC m)": None,
            "Market Cap (m)": None,
            "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "YF Symbol": yf_symbol,
            "Chart": chart,
            "Data Quality": "🟢 Good"  # EODHD provides fresh data
        }, None
        
    except Exception as e:
        error_msg = f"EODHD API Error: {str(e)}"
        logger.error(f"{symbol}: {error_msg}")
        return None, error_msg

def create_eodhd_chart(symbol: str, hist_data: pd.DataFrame) -> Optional[go.Figure]:
    """Create Plotly chart from EODHD historical data"""
    try:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hist_data.index,
            y=hist_data['close'],
            name='Price',
            line=dict(color='#1f77b4')
        ))
        fig.add_trace(go.Scatter(
            x=hist_data.index,
            y=hist_data['close'].rolling(window=10).mean(),
            name='MA10',
            line=dict(color='orange', width=1)
        ))
        fig.add_trace(go.Scatter(
            x=hist_data.index,
            y=hist_data['close'].rolling(window=20).mean(),
            name='MA20',
            line=dict(color='red', width=1)
        ))
        fig.add_trace(go.Bar(
            x=hist_data.index,
            y=hist_data['volume'],
            name='Volume',
            marker_color='rgba(100, 100, 100, 0.3)',
            yaxis='y2'
        ))
        fig.update_layout(
            title=f'{symbol} Price Chart (EODHD Data)',
            xaxis_title='Date',
            yaxis_title='Price',
            yaxis2=dict(title='Volume', overlaying='y', side='right', showgrid=False),
            hovermode='x unified',
            height=400,
            margin=dict(l=50, r=50, b=50, t=50, pad=4),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        return fig
    except Exception as e:
        logger.error(f"Error creating EODHD chart for {symbol}: {str(e)}")
        return None

# Add this to your configuration section
ETF_SYMBOLS = {
    "SLV": "iShares Silver Trust",
    "PSLV": "Sprott Physical Silver Trust",
    "SIL": "Global X Silver Miners ETF",
    "GDX": "VanEck Gold Miners ETF"
}
