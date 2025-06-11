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
MAX_TICKERS = 50
TIMEOUT_SECONDS = 10

def convert_to_yahoo_format(symbol: str, exchange: str) -> str:
    """Convert Symbol+Exchange to proper Yahoo Finance format"""
    # Clean inputs
    symbol = str(symbol).strip().upper()
    exchange = str(exchange).strip()
    
    # Remove any existing suffix from symbol
    base_symbol = symbol.split('.')[0]
    
    # Get Yahoo exchange code
    yahoo_code = YAHOO_EXCHANGE_MAP.get(exchange, '')
    if yahoo_code:
        return f"{base_symbol}.{yahoo_code}"
    return base_symbol

def validate_tickers(tickers: List[str]) -> Tuple[List[str], List[str]]:
    """Validate CAC 40 tickers"""
    valid = []
    invalid = []
    
    for t in tickers:
        t = str(t).strip().upper()
        
        # Check for properly formatted tickers (e.g., AC.PA)
        if '.' in t:
            parts = t.split('.')
            if len(parts) == 2 and 1 <= len(parts[0]) <= 8 and 1 <= len(parts[1]) <= 2:
                valid.append(t)
                continue
        
        # Check for simple tickers
        if 1 <= len(t) <= 8 and any(c.isalpha() for c in t):
            valid.append(t)
        else:
            invalid.append(t)
    
    return valid[:MAX_TICKERS], invalid

@st.cache_data(show_spinner="Fetching CAC 40 data...", ttl=3600)
def get_stock_data(
    ticker: str,
    period: str,
    discount_method: str,
    manual_rate: Optional[float],
    growth_period: int,
    terminal_growth: float,
    adjust_inflation: bool,
    inflation: float
) -> Tuple[Optional[Dict], Optional[pd.DataFrame]]:
    """Fetch data with CAC 40 support"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period, timeout=TIMEOUT_SECONDS)
        
        if hist.empty:
            st.warning(f"No data found for {ticker}")
            return None, None
        
        info = stock.info
        current_price = info.get('currentPrice') or info.get('regularMarketPrice') or hist['Close'].iloc[-1]
        
        # Sector mapping for CAC 40 companies
        sector = info.get('sector', 'European')
        
        # Get discount rate
        if discount_method == "Use industry default":
            nominal_rate = SECTOR_DISCOUNT_RATES.get(sector, 9.0) / 100
            suggested_rate = SECTOR_DISCOUNT_RATES.get(sector, 9.0)
        else:
            nominal_rate = manual_rate / 100
            suggested_rate = manual_rate

        # Get cash flows
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
    **Analyze CAC 40 stocks using proper Yahoo Finance ticker formats**  
    Upload your Excel file with 'Symbol' and 'Exchange' columns.
    """)
    
    with st.expander("ℹ️ CAC 40 Ticker Format Guide"):
        st.markdown("""
        ### Proper Yahoo Finance Formats for CAC 40:
        - **Air Liquide**: `AI.PA`
        - **LVMH**: `MC.PA`
        - **TotalEnergies**: `TTE.PA`
        - **Sanofi**: `SAN.PA`
        
        ### File Requirements:
        - Must contain 'Symbol' and 'Exchange' columns
        - Exchange should be 'Euronext Paris' for CAC 40 stocks
        """)
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        uploaded_file = st.file_uploader(
            "Upload CAC 40 Excel File", 
            type=["xlsx"],
            help="Should contain 'Symbol' and 'Exchange' columns"
        )
        
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
        
        if st.button("🔄 Analyze CAC 40 Stocks", use_container_width=True):
            st.cache_data.clear()
    
    # Main analysis flow
    if uploaded_file is not None:
        try:
            excel_data = pd.read_excel(uploaded_file)
            
            # Check for required columns
            if not all(col in excel_data.columns for col in ["Symbol", "Exchange"]):
                st.error("""
                Invalid file format. Required columns:
                - 'Symbol' (e.g., AI.PA)
                - 'Exchange' (e.g., Euronext Paris)
                """)
                return
            
            # Convert to Yahoo Finance format
            tickers = [
                convert_to_yahoo_format(s, e) 
                for s, e in zip(excel_data["Symbol"], excel_data["Exchange"])
                if pd.notna(s)
            ]
            
            # Validate tickers
            valid_tickers, invalid_tickers = validate_tickers(tickers)
            
            if not valid_tickers:
                st.error("No valid CAC 40 tickers found. Please check your file format.")
                return
            
            st.success(f"Processing {len(valid_tickers)} CAC 40 stocks")
            
            # Process tickers with progress
            progress_bar = st.progress(0)
            results = []
            
            for i, ticker in enumerate(valid_tickers):
                progress_bar.progress((i + 1) / len(valid_tickers))
                data, _ = get_stock_data(
                    ticker, "1y", discount_method,
                    discount_rate if discount_method == "Manual override" else None,
                    growth_period, terminal_growth,
                    True, DEFAULT_INFLATION
                )
                if data:
                    results.append(data)
                time.sleep(0.5)
            
            # Display results
            if results:
                df = pd.DataFrame(results)
                st.subheader("📊 CAC 40 Valuation Results")
                
                # Formatting
                def color_margin(val):
                    color = 'green' if val > 0 else 'red'
                    return f'color: {color}'
                
                st.dataframe(
                    df.style.format({
                        "Current Price": "€{:.2f}",
                        "FCF (ttm)": "€{:,.0f}",
                        "Intrinsic Value": "€{:.2f}",
                        "Margin of Safety": "{:.1%}",
                        "Discount Rate": "{:.1f}%"
                    }).applymap(color_margin, subset=["Margin of Safety"]),
                    height=600,
                    column_config={
                        "Company": st.column_config.TextColumn(width="large"),
                        "Ticker": st.column_config.TextColumn(width="small")
                    }
                )
                
                # Download
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                st.download_button(
                    "💾 Download CAC 40 Analysis",
                    data=output.getvalue(),
                    file_name="cac40_valuation.xlsx",
                    mime="application/vnd.ms-excel"
                )
        
        except Exception as e:
            st.error(f"Error processing CAC 40 file: {str(e)}")

if __name__ == "__main__":
    main()
