import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime

# Google Sheets Authentication
@st.cache_data
def get_google_sheet_data():
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    SERVICE_ACCOUNT_INFO = st.secrets["GCP_SERVICE_ACCOUNT"]
    creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key("1sNYUiP4Pl8GVYQ1S7Ltc4ETv-ctOA1RVCdYkMb5xjjg").sheet1
    df = pd.DataFrame(sheet.get_all_records()).dropna(subset=["Symbol", "Exchange"]).drop_duplicates("Symbol")
    return df

# Exchange suffix mapping
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

def calculate_crossover(close_series):
    try:
        ma10 = close_series.rolling(window=10).mean()
        ma20 = close_series.rolling(window=20).mean()
        
        # Get the last 6 values (current + previous 5)
        ma10_values = ma10.iloc[-6:].values
        ma20_values = ma20.iloc[-6:].values
        
        # Current relationship
        current_relation = "MA10 > MA20" if ma10_values[-1] > ma20_values[-1] else "MA10 ≤ MA20"
        
        # Initialize crossover status
        crossover_status = "No Crossover"
        
        # Check for Golden Cross (MA10 crosses above MA20)
        if (ma10_values[-2] <= ma20_values[-2]) and (ma10_values[-1] > ma20_values[-1]):
            crossover_status = "🟢 Golden Cross (Bullish)"
        
        # Check for Death Cross (MA10 crosses below MA20)
        elif (ma10_values[-2] >= ma20_values[-2]) and (ma10_values[-1] < ma20_values[-1]):
            crossover_status = "🔴 Death Cross (Bearish)"
        
        # Check for recent crossovers within last 5 days
        else:
            for i in range(1, 6):
                if (ma10_values[-i-1] <= ma20_values[-i-1]) and (ma10_values[-1] > ma20_values[-1]):
                    crossover_status = "🟡 Recent Golden Cross"
                    break
                elif (ma10_values[-i-1] >= ma20_values[-i-1]) and (ma10_values[-1] < ma20_values[-1]):
                    crossover_status = "🟠 Recent Death Cross"
                    break
        
        return f"{current_relation} | {crossover_status}"
    except Exception as e:
        return f"Error: {str(e)}"

def create_price_chart(symbol, history_data):
    fig = go.Figure()
    
    # Add price line
    fig.add_trace(go.Scatter(
        x=history_data.index,
        y=history_data['Close'],
        name='Price',
        line=dict(color='#1f77b4')
    ))
    
    # Add moving averages
    fig.add_trace(go.Scatter(
        x=history_data.index,
        y=history_data['Close'].rolling(window=10).mean(),
        name='MA10',
        line=dict(color='orange', width=1)
    ))
    
    fig.add_trace(go.Scatter(
        x=history_data.index,
        y=history_data['Close'].rolling(window=20).mean(),
        name='MA20',
        line=dict(color='red', width=1)
    ))
    
    # Add volume as bar chart
    fig.add_trace(go.Bar(
        x=history_data.index,
        y=history_data['Volume'],
        name='Volume',
        marker_color='rgba(100, 100, 100, 0.3)',
        yaxis='y2'
    ))
    
    # Update layout
    fig.update_layout(
        title=f'{symbol} Price Chart',
        xaxis_title='Date',
        yaxis_title='Price',
        yaxis2=dict(
            title='Volume',
            overlaying='y',
            side='right',
            showgrid=False
        ),
        hovermode='x unified',
        height=400,
        margin=dict(l=50, r=50, b=50, t=50, pad=4),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig

@st.cache_data(ttl=3600)
def get_ticker_data(_ticker, exchange, yf_symbol):
    try:
        ticker_obj = yf.Ticker(yf_symbol)
        hist = ticker_obj.history(period="6mo")
        if hist.empty or len(hist) < 20:
            return None, None

        close = hist["Close"]
        volume = hist["Volume"]

        last_price = close.iloc[-1]
        ma10 = close.rolling(window=10).mean().iloc[-1]
        ma20 = close.rolling(window=20).mean().iloc[-1]
        prev_price = close.iloc[-2]
        prev_ma10 = close.rolling(window=10).mean().iloc[-2]
        volume_ma10 = volume.rolling(window=10).mean().iloc[-1]

        # NEW: Calculate 5-day price change
        if len(close) >= 5:
            price_5d_ago = close.iloc[-5]
            change_5d = ((last_price - price_5d_ago) / price_5d_ago) * 100
        else:
            change_5d = None

        divergence = round((last_price - ma10) / ma10 * 100, 2)
        signal = "🟢 Buy" if (last_price > ma10 and ma10 > ma20) else "🔴 Sell" if (last_price < ma10 and ma10 < ma20) else "🟡 Neutral"
        crossover = calculate_crossover(close)

        ticker_info = ticker_obj.info
        
        # Dividend Yield (divided by 100)
        dividend_yield = ticker_info.get("dividendYield", 0) / 100
        
        dividend_payout_ratio = ticker_info.get("payoutRatio", 0) * 100
        free_cash_flow = ticker_info.get("freeCashflow", None)
        pe_ratio = ticker_info.get("trailingPE", None)

        # Create chart
        chart = create_price_chart(_ticker, hist)

        return {
            "Symbol": _ticker,
            "Exchange": exchange,
            "Price": round(last_price, 2),
            "5D Change %": round(change_5d, 2) if change_5d is not None else None,  # NEW COLUMN
            "MA10": round(ma10, 2),
            "MA20": round(ma20, 2),
            "Divergence": divergence,
            "% vs MA10": f"{divergence}%",
            "Volume": int(volume.iloc[-1]),
            "Vol MA10": int(volume_ma10),
            "Signal": signal,
            "Crossover": crossover,
            "P/E Ratio": round(pe_ratio, 2) if pe_ratio else None,
            "Dividend Yield": round(dividend_yield, 4),
            "Dividend Payout Ratio (%)": round(dividend_payout_ratio, 2),
            "Free Cash Flow (LC m)": round(free_cash_flow / 1e6, 2) if free_cash_flow else None,
            "Last Updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "YF Symbol": yf_symbol,
            "Chart": chart
        }, hist

    except Exception as e:
        st.error(f"Error processing {_ticker}: {str(e)}")
        return None, None

# Streamlit UI Configuration
st.set_page_config(layout="wide")
st.title("📊 Stock Watchlist Dashboard")

# Load data
df = get_google_sheet_data()

# Filters
col1, col2, col3 = st.columns(3)
with col1:
    selected_exchange = st.multiselect(
        "Filter by Exchange", 
        options=df["Exchange"].unique(), 
        default=df["Exchange"].unique()
    )
with col2:
    signal_filter = st.multiselect(
        "Filter by Signal",
        options=["🟢 Buy", "🔴 Sell", "🟡 Neutral"],
        default=["🟢 Buy", "🔴 Sell", "🟡 Neutral"]
    )
with col3:
    crossover_filter = st.multiselect(
        "Filter by Crossover",
        options=["Golden Cross", "Death Cross", "Recent Golden Cross", "Recent Death Cross"],
        default=["Golden Cross", "Death Cross"]
    )

# Process data
results = []
progress_bar = st.progress(0)
status_text = st.empty()

for i, (_, row) in enumerate(df.iterrows()):
    symbol, exchange = row["Symbol"], row["Exchange"]
    if selected_exchange and exchange not in selected_exchange:
        continue
        
    yf_symbol = map_to_yfinance_symbol(symbol, exchange)
    progress_bar.progress((i + 1) / len(df))
    status_text.text(f"Processing {i+1}/{len(df)}: {symbol} ({exchange})")
    
    ticker_data, history_data = get_ticker_data(symbol, exchange, yf_symbol)
    if ticker_data:
        results.append(ticker_data)

progress_bar.empty()
status_text.empty()

if results:
    results_df = pd.DataFrame(results)
    
    # Apply filters
    results_df = results_df[
        results_df["Signal"].isin(signal_filter) &
        results_df["Crossover"].str.contains("|".join(crossover_filter), case=False, na=False)
    ]
    
    # Sort options (added 5D Change to sort options)
    sort_options = {
        "5D Change (High to Low)": ("5D Change %", False),
        "Divergence (High to Low)": ("Divergence", False),
        "Price (High to Low)": ("Price", False),
        "P/E Ratio (Low to High)": ("P/E Ratio", True),
        "Dividend Yield (High to Low)": ("Dividend Yield", False)
    }
    
    sort_col, _, _ = st.columns(3)
    with sort_col:
        sort_option = st.selectbox("Sort by", options=list(sort_options.keys()))
    
    sort_column, ascending = sort_options[sort_option]
    results_df = results_df.sort_values(
        by=sort_column, 
        ascending=ascending,
        na_position='last'
    )
    
    # Display results
    display_columns = [col for col in results_df.columns if col not in ["Chart", "YF Symbol", "Divergence"]]
    st.dataframe(
        results_df[display_columns],
        use_container_width=True,
        height=700,
        column_config={
            "Price": st.column_config.NumberColumn(format="$%.2f"),
            "5D Change %": st.column_config.NumberColumn(format="%.2f%%"),  # NEW COLUMN
            "Dividend Yield": st.column_config.NumberColumn(format="%.4f"),
            "P/E Ratio": st.column_config.NumberColumn(format="%.2f"),
            "Dividend Payout Ratio (%)": st.column_config.NumberColumn(format="%.2f%%"),
            "Free Cash Flow (LC m)": st.column_config.NumberColumn(format="$%.2f")
        }
    )
    
    # Display charts for selected stocks
    selected_symbols = st.multiselect(
        "Select stocks to view charts:",
        options=results_df["Symbol"].unique()
    )
    
    for symbol in selected_symbols:
        ticker_data = next((item for item in results if item["Symbol"] == symbol), None)
        if ticker_data and "Chart" in ticker_data:
            st.plotly_chart(ticker_data["Chart"], use_container_width=True)
    
    # Download button
    st.download_button(
        label="Download Data as CSV",
        data=results_df.drop(columns=["Chart"]).to_csv(index=False),
        file_name="stock_metrics.csv",
        mime="text/csv"
    )
else:
    st.warning("No data available for the selected filters.")

