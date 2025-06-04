import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# --- Google Sheet ticker fetch ---
GOOGLE_SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1sNYUiP4Pl8GVYQ1S7Ltc4ETv-ctOA1RVCdYkMb5xjjg2/export?format=csv"

@st.cache_data(show_spinner=False)
def get_tickers_from_google_sheet():
    try:
        df = pd.read_csv(GOOGLE_SHEET_CSV_URL)
        # Adjust 'Symbol' if your column header is different
        col = 'Symbol' if 'Symbol' in df.columns else df.columns[0]
        tickers = df[col].dropna().unique().tolist()
        return tickers
    except Exception as e:
        st.error(f"Error loading ticker list: {e}")
        return []

# --- yfinance data fetch (cached, _ticker_obj is not hashed) ---
@st.cache_data(show_spinner=False)
def safe_yfinance_fetch(_ticker_obj, period="6mo", interval="1d"):
    try:
        hist = _ticker_obj.history(period=period, interval=interval)
        if isinstance(hist, pd.DataFrame) and not hist.empty:
            return hist
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

# --- DMI/ADX chart ---
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
    fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name='Price', line=dict(color='#1f77b4'), yaxis='y1'))
    fig.add_trace(go.Scatter(x=hist.index, y=plus_di, name='+DI', line=dict(color='green'), yaxis='y2'))
    fig.add_trace(go.Scatter(x=hist.index, y=minus_di, name='-DI', line=dict(color='red'), yaxis='y2'))
    fig.add_trace(go.Scatter(x=hist.index, y=adx, name='ADX', line=dict(color='blue', width=2), yaxis='y2'))
    fig.add_shape(type="line", x0=hist.index[0], y0=25, x1=hist.index[-1], y1=25, line=dict(color="blue", width=1, dash="dot"), yref="y2")
    fig.update_layout(
        title=f'{symbol} Price with DMI Indicators',
        xaxis_title='Date',
        yaxis_title='Price',
        yaxis2=dict(
            title='DMI Values',
            overlaying='y',
            side='right',
            range=[0, max(plus_di.max(), minus_di.max(), adx.max()) * 1.1]
        ),
        hovermode='x unified',
        height=400,
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

# --- Price & Volume chart ---
def create_price_chart(hist, symbol):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=hist.index,
        open=hist['Open'],
        high=hist['High'],
        low=hist['Low'],
        close=hist['Close'],
        name='Candlestick'
    ))
    fig.add_trace(go.Bar(
        x=hist.index,
        y=hist['Volume'],
        name='Volume',
        yaxis='y2',
        marker=dict(color='#e1e1e1', opacity=0.3)
    ))
    fig.update_layout(
        title=f"{symbol} Price & Volume",
        xaxis_title='Date',
        yaxis_title='Price',
        yaxis2=dict(title='Volume', overlaying='y', side='right', showgrid=False),
        hovermode='x unified',
        height=400,
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

# --- Symbol Details Display ---
def display_symbol_details(selected_symbol):
    if not selected_symbol:
        st.info("Please select a symbol.")
        return
    with st.spinner(f'Loading {selected_symbol} analysis...'):
        try:
            st.subheader(f"{selected_symbol} Detailed Analysis")
            tab1, tab2 = st.tabs(["Price Chart", "DMI Indicators"])

            ticker_obj = yf.Ticker(selected_symbol)

            with tab1:
                hist = safe_yfinance_fetch(ticker_obj)
                if not hist.empty:
                    st.plotly_chart(create_price_chart(hist, selected_symbol), use_container_width=True)
                else:
                    st.warning("Could not load price history for chart")

            with tab2:
                hist = safe_yfinance_fetch(ticker_obj)
                if not hist.empty:
                    st.plotly_chart(create_dmi_chart(hist, selected_symbol), use_container_width=True)
                    with st.expander("DMI Indicators Interpretation"):
                        st.markdown("""
                        - **+DI (Green)**: Measures upward movement strength  
                        - **-DI (Red)**: Measures downward movement strength  
                        - **ADX (Blue)**: Measures trend strength (values > 25 suggest strong trend)  
                        - **Bullish Signal**: +DI crosses above -DI  
                        - **Bearish Signal**: -DI crosses above +DI
                        """)
                else:
                    st.warning("Could not load price history for DMI chart")
        except Exception as e:
            st.error(f"Error loading {selected_symbol}: {str(e)}")

# --- Main App ---
def main():
    st.title("S&P 500 Momentum Scanner")
    st.sidebar.header("Select Stock Symbol")
    symbols = get_tickers_from_google_sheet()
    if not symbols:
        st.error("No symbols loaded from Google Sheet.")
        return
    selected = st.sidebar.selectbox("Symbol", symbols)
    display_symbol_details(selected)

if __name__ == "__main__":
    main()
