import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from stocknews import StockNews
from ta import add_all_ta_features
import warnings
warnings.filterwarnings('ignore')

# Utility: Always clean tickers (removes quotes, whitespace, ensures uppercase)
def clean_tickers(ticker_list):
    return (
        pd.Series(ticker_list)
        .dropna()
        .astype(str)
        .str.upper()
        .str.replace(r'^"|"$', '', regex=True)
        .str.strip()
        .unique()
        .tolist()
    )

# App configuration
st.set_page_config(
    page_title="Swing Trading Scanner Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants
SCAN_UNIVERSE = [
    '"AAPL"', '"MSFT"', '"GOOG"', '"AMZN"', '"META"', '"TSLA"', '"NVDA"', '"PYPL"', '"ADBE"', '"NFLX"',
    '"JPM"', '"BAC"', '"WFC"', '"GS"', '"XOM"', '"CVX"', '"COP"', '"PFE"', '"MRK"', '"JNJ"',
    '"WMT"', '"TGT"', '"HD"', '"LOW"', '"COST"', '"DIS"', '"NKE"', '"MCD"', '"SBUX"', '"BA"'
]
TIME_FRAMES = ['1d', '1wk']

# Excel upload at the top of the app
uploaded_file = st.file_uploader(
    "Upload an Excel file (.xlsx) with a column named 'Ticker' or 'Symbol'", 
    type=["xlsx"]
)

excel_ticker_list = None

if uploaded_file is not None:
    df_excel = pd.read_excel(uploaded_file)
    ticker_col = None
    for col in df_excel.columns:
        if col.lower() in ['ticker', 'symbol']:
            ticker_col = col
            break
    if ticker_col:
        excel_ticker_list = df_excel[ticker_col].tolist()
        st.success(f"Loaded {len(excel_ticker_list)} tickers from Excel: {ticker_col}")
    else:
        st.error("Could not find a 'Ticker' or 'Symbol' column in your uploaded file.")

# Use the cleaned tickers for both Excel and default universe
if excel_ticker_list:
    st.session_state.watchlist = clean_tickers(excel_ticker_list)
elif 'watchlist' not in st.session_state:
    st.session_state.watchlist = clean_tickers(SCAN_UNIVERSE[:10])
if 'scanned_results' not in st.session_state:
    st.session_state.scanned_results = pd.DataFrame()

# Utility functions
def get_stock_data(ticker, period='6mo', interval='1d'):
    data = yf.download(ticker, period=period, interval=interval)
    if not data.empty:
        data = add_all_ta_features(data, open="Open", high="High", low="Low", close="Close", volume="Volume")
    return data

def calculate_opportunity_score(data):
    if data.empty:
        return 0
    rsi = data['momentum_rsi'].iloc[-1]
    macd_diff = data['trend_macd_diff'].iloc[-1]
    bb_percent = data['volatility_bbp'].iloc[-1]
    volume_change = data['volume_volume_adi'].pct_change().iloc[-1]
    stoch = data['momentum_stoch'].iloc[-1]
    price_52w_high = data['Close'].iloc[-1] / data['Close'].rolling(252).max().iloc[-1]
    rsi_score = 100 - abs(rsi - 50)
    macd_score = 50 + (macd_diff * 1000)
    bb_score = 100 - abs(bb_percent - 0.5) * 200
    volume_score = min(100, max(0, volume_change * 1000 + 50))
    stoch_score = 100 - abs(stoch - 50)
    high_score = price_52w_high * 100
    composite = (rsi_score * 0.2 + macd_score * 0.25 + bb_score * 0.15 + 
                volume_score * 0.1 + stoch_score * 0.1 + high_score * 0.2)
    return round(composite, 1)

def generate_strategy(data):
    strategy = {
        'entry_rules': [],
        'exit_rules': [],
        'stop_loss': None,
        'take_profit': None
    }
    if data.empty:
        return strategy
    current_rsi = data['momentum_rsi'].iloc[-1]
    current_macd = data['trend_macd_diff'].iloc[-1]
    current_bb = data['volatility_bbp'].iloc[-1]
    current_close = data['Close'].iloc[-1]
    if current_rsi < 35:
        strategy['entry_rules'].append(f"RSI ({current_rsi:.1f}) < 35 (Oversold)")
    elif current_rsi > 65:
        strategy['entry_rules'].append(f"RSI ({current_rsi:.1f}) > 65 (Overbought)")
    if current_macd > 0:
        strategy['entry_rules'].append("MACD Histogram positive")
    else:
        strategy['entry_rules'].append("MACD Histogram negative")
    if current_bb < 0.2:
        strategy['entry_rules'].append("Price near lower Bollinger Band")
    elif current_bb > 0.8:
        strategy['entry_rules'].append("Price near upper Bollinger Band")
    if current_rsi < 30 or current_rsi > 70:
        strategy['exit_rules'].append(f"RSI crosses {40 if current_rsi<30 else 60}")
    strategy['exit_rules'].append("MACD crosses signal line opposite direction")
    atr = data['volatility_atr'].iloc[-1]
    strategy['stop_loss'] = f"{current_close - atr * 1.5:.2f} (1.5x ATR)"
    strategy['take_profit'] = f"{current_close + atr * 3:.2f} (3x ATR)"
    return strategy

def scan_universe(universe, period='6mo'):
    results = []
    with st.spinner(f"Scanning {len(universe)} stocks..."):
        progress_bar = st.progress(0)
        for i, ticker in enumerate(universe):
            try:
                data = get_stock_data(ticker, period)
                if not data.empty:
                    score = calculate_opportunity_score(data)
                    strategy = generate_strategy(data)
                    results.append({
                        'Ticker': ticker,
                        'Score': score,
                        'Price': data['Close'].iloc[-1],
                        'Change %': (data['Close'].iloc[-1] / data['Close'].iloc[-2] - 1) * 100,
                        'Volume': data['Volume'].iloc[-1],
                        'RSI': data['momentum_rsi'].iloc[-1],
                        'MACD': data['trend_macd_diff'].iloc[-1],
                        'BB %': data['volatility_bbp'].iloc[-1] * 100,
                        'Strategy': strategy
                    })
            except Exception as e:
                continue
            progress_bar.progress((i + 1) / len(universe))
    df_results = pd.DataFrame(results)
    if not df_results.empty and 'Score' in df_results.columns:
        return df_results.sort_values('Score', ascending=False)
    else:
        return pd.DataFrame(columns=[
            'Ticker', 'Score', 'Price', 'Change %', 'Volume', 'RSI', 'MACD', 'BB %', 'Strategy'
        ])

# Sidebar config
st.sidebar.title("Swing Trading Scanner Pro")
st.sidebar.subheader("Configuration")
with st.sidebar.expander("Scan Settings", expanded=True):
    scan_type = st.selectbox("Scan Type", [
        "Momentum Opportunities", 
        "Mean Reversion", 
        "Breakouts", 
        "All Opportunities"
    ])
    time_frame = st.selectbox("Time Frame", TIME_FRAMES)
    min_score = st.slider("Minimum Quality Score", 0, 100, 70)
    max_results = st.slider("Max Results", 5, 50, 15)

# Show ticker list and let user review (from Excel or default)
st.sidebar.markdown("#### Current Universe")
st.sidebar.write(st.session_state.watchlist)

st.title("Swing Trading Opportunity Scanner")

if st.sidebar.button("Run Scan", type="primary"):
    st.session_state.scanned_results = scan_universe(st.session_state.watchlist)

if not st.session_state.scanned_results.empty:
    st.subheader(f"Top {max_results} Swing Trading Opportunities")
    filtered_results = st.session_state.scanned_results[st.session_state.scanned_results['Score'] >= min_score]
    filtered_results = filtered_results.head(max_results)
    st.dataframe(
        filtered_results[['Ticker', 'Score', 'Price', 'Change %', 'RSI', 'MACD', 'BB %']].style
            .background_gradient(subset=['Score'], cmap='RdYlGn')
            .format({
                'Change %': '{:.2f}%',
                'RSI': '{:.1f}',
                'MACD': '{:.4f}',
                'BB %': '{:.1f}%'
            }),
        use_container_width=True
    )
    selected_ticker = st.selectbox(
        "Select ticker for detailed analysis",
        filtered_results['Ticker']
    )
    if selected_ticker:
        selected_data = get_stock_data(selected_ticker)
        selected_result = filtered_results[filtered_results['Ticker'] == selected_ticker].iloc[0]
        strategy = selected_result['Strategy']
        st.subheader(f"Recommended Strategy for {selected_ticker}")
        cols = st.columns([1, 1, 1])
        with cols[0]:
            st.markdown("**Entry Rules**")
            for rule in strategy['entry_rules']:
                st.markdown(f"- {rule}")
        with cols[1]:
            st.markdown("**Exit Rules**")
            for rule in strategy['exit_rules']:
                st.markdown(f"- {rule}")
        with cols[2]:
            st.markdown("**Risk Management**")
            st.markdown(f"- Stop Loss: {strategy['stop_loss']}")
            st.markdown(f"- Take Profit: {strategy['take_profit']}")
        st.subheader("Technical Analysis")
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=selected_data.index,
            open=selected_data['Open'],
            high=selected_data['High'],
            low=selected_data['Low'],
            close=selected_data['Close'],
            name='Price',
            increasing_line_color='green',
            decreasing_line_color='red'
        ))
        fig.add_trace(go.Scatter(
            x=selected_data.index,
            y=selected_data['volatility_bbh'],
            name='BB Upper',
            line=dict(color='rgba(128, 0, 128, 0.5)', width=1)
        ))
        fig.add_trace(go.Scatter(
            x=selected_data.index,
            y=selected_data['volatility_bbl'],
            name='BB Lower',
            line=dict(color='rgba(128, 0, 128, 0.5)', width=1),
            fill='tonexty'
        ))
        fig.update_layout(
            height=500,
            xaxis_rangeslider_visible=False,
            title=f"{selected_ticker} Price with Bollinger Bands"
        )
        st.plotly_chart(fig, use_container_width=True)
        cols = st.columns(2)
        with cols[0]:
            rsi_fig = go.Figure()
            rsi_fig.add_trace(go.Scatter(
                x=selected_data.index,
                y=selected_data['momentum_rsi'],
                name='RSI',
                line=dict(color='blue', width=2)
            ))
            rsi_fig.add_hline(y=30, line_dash="dash", line_color="green")
            rsi_fig.add_hline(y=70, line_dash="dash", line_color="red")
            rsi_fig.update_layout(height=300, title="RSI (14)")
            st.plotly_chart(rsi_fig, use_container_width=True)
        with cols[1]:
            macd_fig = go.Figure()
            macd_fig.add_trace(go.Scatter(
                x=selected_data.index,
                y=selected_data['trend_macd'],
                name='MACD',
                line=dict(color='blue', width=2)
            ))
            macd_fig.add_trace(go.Scatter(
                x=selected_data.index,
                y=selected_data['trend_macd_signal'],
                name='Signal',
                line=dict(color='orange', width=2)
            ))
            macd_fig.add_trace(go.Bar(
                x=selected_data.index,
                y=selected_data['trend_macd_diff'],
                name='Histogram',
                marker_color=np.where(selected_data['trend_macd_diff'] > 0, 'green', 'red')
            ))
            macd_fig.update_layout(height=300, title="MACD")
            st.plotly_chart(macd_fig, use_container_width=True)
        st.subheader(f"Latest News for {selected_ticker}")
        try:
            sn = StockNews(selected_ticker, save_news=False)
            df_news = sn.read_rss()
            for i in range(min(3, len(df_news))):
                st.markdown(f"""
                <div style="
                    background: white;
                    border-radius: 8px;
                    padding: 15px;
                    margin-bottom: 15px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                ">
                    <h4 style="margin-top: 0; color: #2c3e50;">{df_news.iloc[i]['title']}</h4>
                    <p style="color: #666; font-size: 14px;">{df_news.iloc[i]['summary']}</p>
                    <a href="{df_news.iloc[i]['link']}" target="_blank" style="
                        color: #3498db;
                        text-decoration: none;
                        font-size: 14px;
                    ">Read more</a>
                    <div style="
                        font-size: 12px;
                        color: #999;
                        margin-top: 8px;
                    ">{df_news.iloc[i]['date']} | {df_news.iloc[i]['source']}</div>
                </div>
                """, unsafe_allow_html=True)
        except Exception as e:
            st.warning(f"Could not fetch news: {e}")
elif st.session_state.scanned_results.shape[0] == 0:
    st.warning("Scan completed but no opportunities found. Try expanding your universe or lowering minimum score.")
else:
    st.info("Click 'Run Scan' to find swing trading opportunities")
