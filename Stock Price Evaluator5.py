import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from io import BytesIO
import time
from typing import List, Tuple, Optional, Dict

# Configure page settings
st.set_page_config(
    page_title="Global Stock Evaluator",
    page_icon="🌐",
    layout="wide"
)

# Constants with Yahoo Finance-compatible exchange suffixes
YAHOO_EXCHANGE_MAP = {
    # Europe
    'DE': '.DE',   # XETRA (Germany)
    'MI': '.MI',   # Milan
    'L': '.L',     # London
    'ST': '.ST',   # Stockholm
    'PA': '.PA',   # Paris
    'AS': '.AS',   # Amsterdam
    'BR': '.BR',   # Brussels
    'MC': '.MC',   # Madrid
    'SW': '.SW',   # Switzerland
    'CO': '.CO',   # Copenhagen
    'OL': '.OL',   # Oslo
    'HE': '.HE',   # Helsinki
    'VI': '.VI',   # Vienna
    
    # Americas
    'TO': '.TO',   # Toronto
    'V': '.V',     # TSX Venture
    'MX': '.MX',   # Mexico
    
    # Asia/Pacific
    'T': '.T',     # Tokyo
    'HK': '.HK',   # Hong Kong
    'SI': '.SI',   # Singapore
    'KS': '.KS',   # Korea
    'TW': '.TW',   # Taiwan
    'AX': '.AX',   # Australia
    'NZ': '.NZ',   # New Zealand
    
    # Special cases
    'US': '',      # No suffix for US stocks
    'NA': ''       # No suffix (fallback)
}

SECTOR_DISCOUNT_RATES = {
    "Technology": 10.5,
    "Healthcare": 9.0,
    "Financial Services": 9.5,
    "Industrial": 9.0,
    "European": 8.5,
    "UK": 8.0,
    "Scandinavian": 8.0,
    "Asian": 10.0
}

DEFAULT_INFLATION = 0.025
MAX_TICKERS = 50
TIMEOUT_SECONDS = 10

def convert_to_yahoo_format(symbol: str, exchange: str) -> str:
    """Convert Symbol+Exchange to proper Yahoo Finance format"""
    # Clean inputs
    symbol = str(symbol).strip().upper()
    exchange = str(exchange).strip().upper()
    
    # Remove any existing suffix from symbol
    base_symbol = symbol.split('.')[0]
    
    # Apply Yahoo Finance suffix mapping
    suffix = YAHOO_EXCHANGE_MAP.get(exchange, f'.{exchange}')
    return f"{base_symbol}{suffix}"

def validate_tickers(tickers: List[str]) -> Tuple[List[str], List[str]]:
    """Validate tickers according to Yahoo Finance requirements"""
    valid = []
    invalid = []
    
    for t in tickers:
        t = str(t).strip().upper()
        
        # Check for already properly formatted tickers (e.g., SAAB-B.ST)
        if '.' in t:
            parts = t.split('.')
            if len(parts) == 2 and 1 <= len(parts[0]) <= 8 and 1 <= len(parts[1]) <= 2:
                valid.append(t)
                continue
        
        # Check for simple tickers (will be formatted later)
        if 1 <= len(t) <= 8 and any(c.isalpha() for c in t):
            valid.append(t)
        else:
            invalid.append(t)
    
    return valid[:MAX_TICKERS], invalid

@st.cache_data(show_spinner="Fetching global stock data...", ttl=3600)
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
    """Fetch data with international stock support"""
    try:
        stock = yf.Ticker(ticker)
        
        # Get historical data with international market support
        hist = stock.history(period=period, timeout=TIMEOUT_SECONDS)
        if hist.empty:
            st.warning(f"No data found for {ticker} - may be delisted or wrong exchange")
            return None, None
        
        # Get info with fallbacks for international stocks
        info = stock.info
        current_price = info.get('currentPrice') or info.get('regularMarketPrice') or hist['Close'].iloc[-1]
        
        # Determine sector with international fallback
        sector = info.get('sector', 'Unknown')
        if '.' in ticker:
            exchange_suffix = ticker.split('.')[1]
            if exchange_suffix in ['DE', 'MI', 'PA', 'ST']:
                sector = sector if sector != 'Unknown' else 'European'
            elif exchange_suffix == 'L':
                sector = sector if sector != 'Unknown' else 'UK'
            elif exchange_suffix in ['SW', 'OL', 'CO', 'HE']:
                sector = sector if sector != 'Unknown' else 'Scandinavian'
            elif exchange_suffix in ['T', 'HK', 'KS']:
                sector = sector if sector != 'Unknown' else 'Asian'
        
        # Get discount rate
        if discount_method == "Use industry default":
            nominal_rate = SECTOR_DISCOUNT_RATES.get(sector, 10.0) / 100
            suggested_rate = SECTOR_DISCOUNT_RATES.get(sector, 10.0)
        else:
            nominal_rate = manual_rate / 100
            suggested_rate = manual_rate

        # Get cash flows with international fallback
        try:
            cashflow = stock.cashflow
            fcf = cashflow.loc['Free Cash Flow'].iloc[0] if (cashflow is not None and 'Free Cash Flow' in cashflow.index) else np.nan
        except:
            fcf = np.nan
        
        data = {
            "Ticker": ticker,
            "Sector": sector,
            "Discount Rate": suggested_rate,
            "Current Price": current_price,
            "FCF (ttm)": fcf,
            "Revenue Growth": info.get('revenueGrowth', np.nan),
            "Inflation Adjusted": "Yes" if adjust_inflation else "No"
        }
        
        # Calculate valuation if we have valid data
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
    st.title("🌍 Global Stock Evaluator")
    st.markdown("""
    **Analyze international stocks using Yahoo Finance-compatible ticker formats**  
    Upload an Excel file with 'Symbol' and 'Exchange' columns for accurate valuation.
    """)
    
    with st.expander("ℹ️ Ticker Format Guide"):
        st.markdown("""
        ### Proper Yahoo Finance Ticker Formats:
        - **US Stocks**: AAPL, MSFT (no suffix needed)
        - **German Stocks**: SAP.DE, RHM.DE
        - **UK Stocks**: BA.L, HSBA.L
        - **Swedish Stocks**: SAAB-B.ST, VOLV-B.ST
        - **Italian Stocks**: LDO.MI, ENEL.MI
        
        ### File Format Requirements:
        - Either single column of formatted tickers (e.g., `SAAB-B.ST`)
        - OR two columns labeled 'Symbol' and 'Exchange' (e.g., Symbol=`SAAB-B`, Exchange=`ST`)
        """)
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        uploaded_file = st.file_uploader(
            "Upload Excel File", 
            type=["xlsx"],
            help="Supports formatted tickers or Symbol+Exchange columns"
        )
        
        st.markdown("---")
        st.subheader("Valuation Settings")
        discount_method = st.radio(
            "Discount Rate Method",
            ["Use industry default", "Manual override"],
            index=0
        )
        
        if discount_method == "Manual override":
            discount_rate = st.slider("Discount Rate (%)", 5.0, 20.0, 10.0, 0.5)
        
        growth_period = st.slider("Growth Period (years)", 1, 10, 5)
        terminal_growth = st.slider("Terminal Growth Rate (%)", 0.0, 5.0, 2.5, 0.1)
        
        if st.button("🔄 Analyze Stocks", use_container_width=True):
            st.cache_data.clear()
    
    # Main analysis flow
    if uploaded_file is not None:
        try:
            excel_data = pd.read_excel(uploaded_file)
            
            # Handle different file formats
            if all(col in excel_data.columns for col in ["Symbol", "Exchange"]):
                tickers = [
                    convert_to_yahoo_format(s, e) 
                    for s, e in zip(excel_data["Symbol"], excel_data["Exchange"])
                    if pd.notna(s)
                ]
            elif "Ticker" in excel_data.columns:
                tickers = [str(t).strip() for t in excel_data["Ticker"].dropna()]
            else:  # Fallback to first column
                tickers = [str(t).strip() for t in excel_data.iloc[:, 0].dropna()]
            
            # Validate and process tickers
            valid_tickers, invalid_tickers = validate_tickers(tickers)
            
            if not valid_tickers:
                st.error("""
                No valid tickers found. Please ensure:
                1. For two-column files: Columns are labeled 'Symbol' and 'Exchange'
                2. For single-column files: Use Yahoo Finance formats (e.g., SAAB-B.ST)
                """)
                return
            
            if invalid_tickers:
                st.warning(f"Invalid tickers skipped: {', '.join(invalid_tickers[:10])}{'...' if len(invalid_tickers) > 10 else ''}")
            
            st.success(f"Processing {len(valid_tickers)} valid tickers")
            
            # Process tickers with progress bar
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
                time.sleep(0.5)  # Rate limiting
            
            # Display results
            if results:
                df = pd.DataFrame(results)
                st.subheader("📊 Valuation Results")
                
                # Color formatting
                def color_margin(val):
                    color = 'green' if val > 0 else 'red'
                    return f'color: {color}'
                
                st.dataframe(
                    df.style.format({
                        "Current Price": "${:.2f}",
                        "FCF (ttm)": "${:,.0f}",
                        "Intrinsic Value": "${:.2f}",
                        "Margin of Safety": "{:.1%}",
                        "Discount Rate": "{:.1f}%"
                    }).applymap(color_margin, subset=["Margin of Safety"]),
                    height=600
                )
                
                # Download button
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                st.download_button(
                    "💾 Download Results",
                    data=output.getvalue(),
                    file_name="global_stock_valuation.xlsx",
                    mime="application/vnd.ms-excel"
                )
        
        except Exception as e:
            st.error(f"File processing error: {str(e)}")

    # Sample file section
    st.markdown("---")
    st.subheader("📁 Sample Files")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**European Stocks**")
        sample_eu = pd.DataFrame({
            "Symbol": ["RHM", "LDO", "BA", "SAAB-B", "SAP"],
            "Exchange": ["DE", "MI", "L", "ST", "DE"]
        })
        st.dataframe(sample_eu, hide_index=True)
        st.download_button(
            "⬇️ Download European Sample",
            data=sample_eu.to_csv(index=False).encode('utf-8'),
            file_name="european_stocks_sample.csv",
            mime="text/csv"
        )
    
    with col2:
        st.markdown("**Formatted Tickers**")
        sample_formatted = pd.DataFrame({
            "Ticker": ["RHM.DE", "LDO.MI", "BA.L", "SAAB-B.ST", "SAP.DE"]
        })
        st.dataframe(sample_formatted, hide_index=True)
        st.download_button(
            "⬇️ Download Formatted Sample",
            data=sample_formatted.to_csv(index=False).encode('utf-8'),
            file_name="formatted_tickers_sample.csv",
            mime="text/csv"
        )

if __name__ == "__main__":
    main()
