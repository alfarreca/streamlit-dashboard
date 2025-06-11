import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from io import BytesIO
import time
from typing import List, Tuple, Optional, Dict

# Configure page settings
st.set_page_config(
    page_title="CAC 40 Stock Evaluator",
    page_icon="🇫🇷",
    layout="wide"
)

# Constants with Yahoo Finance exchange mapping
YAHOO_EXCHANGE_MAP = {
    'Euronext Paris': 'PA',
    'Euronext Amsterdam': 'AS',
    'XETRA': 'DE',
    'London Stock Exchange': 'L',
    'Borsa Italiana': 'MI',
    'NASDAQ': '',
    'NYSE': ''
}

SECTOR_DISCOUNT_RATES = {
    "Financial Services": 9.5,
    "Energy": 9.0,
    "Consumer Cyclical": 10.0,
    "Industrials": 9.0,
    "Healthcare": 8.5,
    "Technology": 10.5,
    "European": 8.0
}

DEFAULT_INFLATION = 0.025
TIMEOUT_SECONDS = 10

def calculate_dcf(fcf: float, growth_rate: float, discount_rate: float,
                 growth_period: int, terminal_growth: float,
                 inflation_rate: float = 0.0) -> float:
    """Calculate intrinsic value using DCF model"""
    if discount_rate <= terminal_growth:
        st.warning("Discount rate must be greater than terminal growth rate")
        return np.nan
    
    if inflation_rate > 0:
        real_discount = max(0.01, discount_rate - inflation_rate)
        real_growth = max(0.0, growth_rate - inflation_rate)
        real_terminal = max(0.0, terminal_growth - inflation_rate)
    else:
        real_discount = discount_rate
        real_growth = growth_rate
        real_terminal = terminal_growth
    
    present_value = 0.0
    for year in range(1, growth_period + 1):
        future_fcf = fcf * (1 + real_growth) ** year
        present_value += future_fcf / ((1 + real_discount) ** year)
    
    terminal_fcf = fcf * (1 + real_growth) ** growth_period
    terminal_value = (terminal_fcf * (1 + real_terminal)) / (real_discount - real_terminal)
    return present_value + (terminal_value / ((1 + real_discount) ** growth_period))

def convert_to_yahoo_format(symbol: str, exchange: str) -> str:
    """Convert Symbol+Exchange to proper Yahoo Finance format"""
    symbol = str(symbol).strip().upper()
    exchange = str(exchange).strip()
    
    base_symbol = symbol.split('.')[0]
    yahoo_code = YAHOO_EXCHANGE_MAP.get(exchange, '')
    return f"{base_symbol}.{yahoo_code}" if yahoo_code else base_symbol

def validate_ticker(ticker: str) -> bool:
    """Validate single CAC 40 ticker"""
    t = str(ticker).strip().upper()
    
    if '.' in t:
        parts = t.split('.')
        return len(parts) == 2 and 1 <= len(parts[0]) <= 8 and 1 <= len(parts[1]) <= 2
    
    return 1 <= len(t) <= 8 and any(c.isalpha() for c in t)

@st.cache_data(show_spinner="Fetching stock data...", ttl=3600)
def get_stock_data(ticker: str, period: str, discount_method: str,
                  manual_rate: Optional[float], growth_period: int,
                  terminal_growth: float, adjust_inflation: bool,
                  inflation: float) -> Tuple[Optional[Dict], Optional[pd.DataFrame]]:
    """Fetch data for single stock"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period, timeout=TIMEOUT_SECONDS)
        
        if hist.empty:
            st.warning(f"No data found for {ticker}")
            return None, None
        
        info = stock.info
        current_price = info.get('currentPrice') or info.get('regularMarketPrice') or hist['Close'].iloc[-1]
        sector = info.get('sector', 'European')
        
        if discount_method == "Use industry default":
            nominal_rate = SECTOR_DISCOUNT_RATES.get(sector, 9.0) / 100
            suggested_rate = SECTOR_DISCOUNT_RATES.get(sector, 9.0)
        else:
            nominal_rate = manual_rate / 100
            suggested_rate = manual_rate

        try:
            cashflow = stock.cashflow
            fcf = cashflow.loc['Free Cash Flow'].iloc[0] if (cashflow is not None and 'Free Cash Flow' in cashflow.index) else np.nan
        except:
            fcf = np.nan
        
        data = {
            "Ticker": ticker,
            "Company": info.get('shortName', ticker),
            "Sector": sector,
            "Discount Rate": suggested_rate,
            "Current Price": current_price,
            "FCF (ttm)": fcf,
            "Revenue Growth": info.get('revenueGrowth', np.nan),
            "Inflation Adjusted": "Yes" if adjust_inflation else "No"
        }
        
        if not np.isnan(fcf) and fcf > 0:
            growth_rate = info.get('revenueGrowth', 0.05)
            intrinsic_value = calculate_dcf(
                fcf, 
                growth_rate if not np.isnan(growth_rate) else 0.05,
                nominal_rate, 
                growth_period, 
                terminal_growth/100,
                inflation if adjust_inflation else 0.0
            )
            
            shares = info.get('sharesOutstanding', np.nan)
            if not np.isnan(shares) and shares > 0:
                data["Intrinsic Value"] = intrinsic_value / shares
                if not np.isnan(data["Current Price"]) and not np.isnan(data["Intrinsic Value"]):
                    data["Margin of Safety"] = ((data["Intrinsic Value"] - data["Current Price"]) / data["Intrinsic Value"])
        
        return data, hist
    
    except Exception as e:
        st.error(f"Error processing {ticker}: {str(e)}")
        return None, None

def main():
    st.title("🇫🇷 CAC 40 Stock Evaluator")
    st.markdown("""
    **Analyze CAC 40 stocks one at a time**  
    Upload your Excel file with 'Symbol' and 'Exchange' columns, then select a ticker to analyze.
    """)
    
    # Initialize session state for ticker list and results
    if 'ticker_list' not in st.session_state:
        st.session_state.ticker_list = []
    if 'current_ticker' not in st.session_state:
        st.session_state.current_ticker = None
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = []
    
    with st.sidebar:
        st.header("⚙️ Configuration")
        uploaded_file = st.file_uploader(
            "Upload CAC 40 Excel File", 
            type=["xlsx"],
            help="Should contain 'Symbol' and 'Exchange' columns"
        )
        
        if uploaded_file is not None:
            try:
                excel_data = pd.read_excel(uploaded_file)
                
                if not all(col in excel_data.columns for col in ["Symbol", "Exchange"]):
                    st.error("File must contain 'Symbol' and 'Exchange' columns")
                else:
                    # Process the file and store tickers in session state
                    tickers = [
                        convert_to_yahoo_format(s, e) 
                        for s, e in zip(excel_data["Symbol"], excel_data["Exchange"])
                        if pd.notna(s)
                    ]
                    valid_tickers = [t for t in tickers if validate_ticker(t)]
                    
                    if valid_tickers:
                        st.session_state.ticker_list = valid_tickers
                        st.success(f"Loaded {len(valid_tickers)} valid tickers")
                    else:
                        st.error("No valid tickers found in the file")
            
            except Exception as e:
                st.error(f"Error reading file: {str(e)}")
        
        st.markdown("---")
        st.subheader("Select Ticker to Analyze")
        
        if st.session_state.ticker_list:
            st.session_state.current_ticker = st.selectbox(
                "Choose a ticker",
                st.session_state.ticker_list,
                index=0
            )
        else:
            st.info("Upload a file to see available tickers")
        
        st.markdown("---")
        st.subheader("Valuation Settings")
        discount_method = st.radio(
            "Discount Rate Method",
            ["Use industry default", "Manual override"],
            index=0
        )
        
        if discount_method == "Manual override":
            discount_rate = st.slider("Discount Rate (%)", 5.0, 20.0, 9.0, 0.5)
        
        growth_period = st.slider("Growth Period (years)", 1, 10, 5)
        terminal_growth = st.slider("Terminal Growth Rate (%)", 0.0, 5.0, 2.0, 0.1)
        
        if st.button("🔍 Analyze Selected Ticker", disabled=not st.session_state.ticker_list):
            with st.spinner(f"Analyzing {st.session_state.current_ticker}..."):
                data, hist = get_stock_data(
                    st.session_state.current_ticker, "1y", discount_method,
                    discount_rate if discount_method == "Manual override" else None,
                    growth_period, terminal_growth,
                    True, DEFAULT_INFLATION
                )
                
                if data:
                    st.session_state.analysis_results.append(data)
                    st.success(f"Analysis complete for {st.session_state.current_ticker}")
    
    # Main display area
    if st.session_state.current_ticker and st.session_state.analysis_results:
        latest_result = st.session_state.analysis_results[-1]
        df = pd.DataFrame([latest_result])
        
        st.subheader(f"📊 Analysis for {latest_result['Ticker']} - {latest_result['Company']}")
        
        # Create columns for better layout
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.metric("Current Price", f"€{latest_result['Current Price']:.2f}")
            st.metric("Intrinsic Value", f"€{latest_result.get('Intrinsic Value', 'N/A'):.2f}")
            
            if 'Margin of Safety' in latest_result:
                safety_color = 'green' if latest_result['Margin of Safety'] > 0 else 'red'
                st.metric(
                    "Margin of Safety", 
                    f"{latest_result['Margin of Safety']:.1%}",
                    delta_color="off",
                    help="Positive margin means the stock may be undervalued"
                )
        
        with col2:
            st.dataframe(
                df.style.format({
                    "Current Price": "€{:.2f}",
                    "FCF (ttm)": "€{:,.0f}",
                    "Intrinsic Value": "€{:.2f}",
                    "Margin of Safety": "{:.1%}",
                    "Discount Rate": "{:.1f}%",
                    "Revenue Growth": "{:.1%}"
                }).applymap(
                    lambda x: 'color: green' if isinstance(x, (float, int)) and x > 0 else 
                    ('color: red' if isinstance(x, (float, int)) and x < 0 else ''),
                    subset=["Margin of Safety", "Revenue Growth"]
                ),
                hide_index=True,
                use_container_width=True
            )
        
        # Historical price chart
        if hist is not None and not hist.empty:
            st.subheader("📈 Price History (1 Year)")
            st.line_chart(hist['Close'])
        
        # Download button for current analysis
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Valuation')
            if hist is not None:
                hist.to_excel(writer, sheet_name='Price_History')
        st.download_button(
            "💾 Download Current Analysis",
            data=output.getvalue(),
            file_name=f"{latest_result['Ticker']}_analysis.xlsx",
            mime="application/vnd.ms-excel"
        )
    
    # Display all analyzed tickers
    if len(st.session_state.analysis_results) > 0:
        st.subheader("📋 Analysis History")
        history_df = pd.DataFrame(st.session_state.analysis_results)
        st.dataframe(
            history_df[['Ticker', 'Company', 'Current Price', 'Intrinsic Value', 'Margin of Safety']]
            .style.format({
                "Current Price": "€{:.2f}",
                "Intrinsic Value": "€{:.2f}",
                "Margin of Safety": "{:.1%}"
            }),
            hide_index=True,
            use_container_width=True
        )

if __name__ == "__main__":
    main()
