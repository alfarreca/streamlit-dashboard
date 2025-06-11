import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
import numpy as np
import matplotlib.dates as mdates
import time
from typing import List, Tuple, Optional, Dict, Union

# Configure page settings
st.set_page_config(
    page_title="Fundamental Stock Evaluator",
    page_icon="📈",
    layout="wide"
)

# Constants
SECTOR_DISCOUNT_RATES = {
    "Technology": 10.5,
    "Healthcare": 9.0,
    "Consumer Defensive": 8.0,
    "Financial Services": 9.5,
    "Utilities": 7.0,
    "Communication Services": 9.0,
    "Energy": 9.5,
    "Industrials": 9.0,
    "Real Estate": 8.5,
    "Basic Materials": 10.0
}

DEFAULT_INFLATION = 0.025  # 2.5%
MAX_TICKERS = 50  # Limit for free tier usage
TIMEOUT_SECONDS = 10  # Timeout for API calls

def get_inflation_rate() -> float:
    """Return current inflation rate with validation"""
    return max(0.0, min(DEFAULT_INFLATION, 0.1))  # Clamp between 0-10%

def validate_tickers(tickers: List[str]) -> Tuple[List[str], List[str]]:
    """Validate and clean ticker symbols"""
    valid = []
    invalid = []
    
    for t in tickers:
        t = str(t).strip().upper()
        if 1 <= len(t) <= 5 and t.isalpha():
            valid.append(t)
        else:
            invalid.append(t)
    
    return valid[:MAX_TICKERS], invalid

def calculate_dcf(
    fcf: float,
    growth_rate: float,
    discount_rate: float,
    growth_period: int,
    terminal_growth: float,
    inflation_rate: float = 0.0
) -> float:
    """Calculate intrinsic value using DCF model with validation"""
    if discount_rate <= terminal_growth:
        st.warning("Discount rate must be greater than terminal growth rate")
        return np.nan
    
    if inflation_rate > 0:
        real_discount = max(0.01, discount_rate - inflation_rate)  # Ensure positive
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

@st.cache_data(show_spinner="Fetching stock data...", ttl=3600)
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
    """Fetch and process stock data with enhanced error handling"""
    try:
        stock = yf.Ticker(ticker)
        
        # Get historical data with timeout
        try:
            hist = stock.history(period=period, timeout=TIMEOUT_SECONDS)
            if hist.empty:
                st.warning(f"No historical data found for {ticker}")
                return None, None
        except Exception as e:
            st.warning(f"Couldn't fetch history for {ticker}: {str(e)}")
            return None, None
        
        # Get company info
        try:
            info = stock.info
            if not info:
                st.warning(f"No info available for {ticker}")
                return None, None
        except Exception as e:
            st.warning(f"Couldn't fetch info for {ticker}: {str(e)}")
            return None, None
        
        sector = info.get('sector', 'Technology')
        
        # Determine discount rate
        if discount_method == "Use industry default":
            nominal_rate = SECTOR_DISCOUNT_RATES.get(sector, 10.0) / 100
            suggested_rate = SECTOR_DISCOUNT_RATES.get(sector, 10.0)
        else:
            nominal_rate = manual_rate / 100
            suggested_rate = manual_rate

        # Get cash flow data
        try:
            cashflow = stock.cashflow
            fcf = cashflow.loc['Free Cash Flow'].iloc[0] if (cashflow is not None and 'Free Cash Flow' in cashflow.index) else np.nan
        except Exception as e:
            st.warning(f"Couldn't fetch cash flow for {ticker}: {str(e)}")
            fcf = np.nan
        
        data = {
            "Ticker": ticker,
            "Sector": sector,
            "Discount Rate": suggested_rate,
            "Current Price": info.get('currentPrice', info.get('regularMarketPrice', np.nan)),
            "FCF (ttm)": fcf,
            "Revenue Growth": info.get('revenueGrowth', np.nan),
            "Inflation Adjusted": "Yes" if adjust_inflation else "No"
        }
        
        # Calculate intrinsic value if we have valid data
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
        st.error(f"Unexpected error processing {ticker}: {str(e)}")
        return None, None

@st.cache_data(show_spinner="Scanning tickers...", ttl=3600)
def scan_tickers(
    tickers: List[str],
    period: str,
    discount_method: str,
    manual_rate: Optional[float],
    growth_period: int,
    terminal_growth: float,
    adjust_inflation: bool,
    inflation: float
) -> Tuple[List[Dict], List[str]]:
    """Process multiple tickers with progress tracking"""
    results = []
    failed = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, ticker in enumerate(tickers):
        status_text.text(f"Processing {i+1}/{len(tickers)}: {ticker}")
        progress_bar.progress((i + 1) / len(tickers))
        
        data, hist = get_stock_data(
            ticker, period, discount_method, manual_rate,
            growth_period, terminal_growth, adjust_inflation, inflation
        )
        
        if data:
            results.append(data)
        else:
            failed.append(ticker)
        
        time.sleep(0.5)  # Rate limiting
    
    progress_bar.empty()
    status_text.empty()
    
    return results, failed

def display_results(results: List[Dict]) -> None:
    """Display analysis results with enhanced visualization"""
    if not results:
        st.warning("No valid results to display")
        return
    
    df = pd.DataFrame(results)
    df = df.replace({None: np.nan})
    
    st.subheader("📊 Valuation Analysis")
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Stocks Analyzed", len(df))
    with col2:
        undervalued = df[df['Margin of Safety'] > 0]
        st.metric("Undervalued Stocks", len(undervalued))
    with col3:
        avg_margin = df['Margin of Safety'].mean() * 100
        st.metric("Avg Margin of Safety", f"{avg_margin:.1f}%")
    
    # Main results table
    st.dataframe(
        df.style.format({
            "Current Price": "${:.2f}",
            "FCF (ttm)": "${:,.0f}",
            "Revenue Growth": "{:.1%}",
            "Discount Rate": "{:.1f}%",
            "Intrinsic Value": "${:.2f}",
            "Margin of Safety": "{:.1%}"
        }).applymap(
            lambda x: 'color: green' if isinstance(x, str) and 'Yes' in x 
            else ('color: red' if isinstance(x, float) and x < 0 
                 else ('color: green' if isinstance(x, float) and x > 0 
                     else '')),
        subset=["Margin of Safety", "Inflation Adjusted"]
    ),
        height=600,
        use_container_width=True
    )
    
    # Download button
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Valuation')
        
        # Add summary sheet
        summary = pd.DataFrame({
            'Metric': ['Total Stocks', 'Undervalued Stocks', 'Average Margin of Safety'],
            'Value': [len(df), len(undervalued), f"{avg_margin:.1f}%"]
        })
        summary.to_excel(writer, index=False, sheet_name='Summary')
    
    st.download_button(
        "💾 Download Full Analysis",
        data=output.getvalue(),
        file_name="stock_valuation_analysis.xlsx",
        mime="application/vnd.ms-excel",
        help="Download complete analysis with summary sheet"
    )

def main() -> None:
    """Main application function"""
    st.title("📈 Fundamental Stock Evaluator")
    st.markdown("""
    **Stocks are priced according to the value of their future cash flows.**  
    Upload an Excel file with stock tickers to analyze valuation based on cash flow fundamentals.
    """)
    
    # Help section
    with st.expander("ℹ️ How to use this tool"):
        st.markdown("""
        1. **Prepare your data**: Create an Excel file with stock tickers in the first column
        2. **Upload**: Use the file uploader in the sidebar
        3. **Configure**: Set your valuation parameters
        4. **Analyze**: View results and download if needed
        
        **Notes**:
        - All financial data is sourced from Yahoo Finance
        - Free tier is limited to {MAX_TICKERS} tickers per analysis
        - Results are cached for 1 hour
        """)
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        uploaded_file = st.file_uploader(
            "Upload Excel File (xlsx)", 
            type=["xlsx"],
            help="First column should contain stock tickers"
        )
        
        st.markdown("---")
        st.subheader("Market Comparison")
        benchmark = st.selectbox(
            "Compare to Benchmark",
            ["^GSPC (S&P 500)", "^IXIC (NASDAQ)", "^DJI (Dow Jones)", 
             "EXS1.DE (Dax ETF)", "EUDF.DE (ISHARES Defense Europe)", 
             "CAC.PA (CAC ETF)", "GDX (Gold Miners ETF)", "None"],
            index=0
        )
        period = st.selectbox(
            "Historical Period", 
            ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y"],
            index=3
        )
        
        st.markdown("---")
        st.subheader("Valuation Settings")
        
        adjust_for_inflation = st.checkbox(
            "Adjust for inflation", 
            value=True,
            help="Uses current inflation rate to adjust growth and discount rates"
        )
        current_inflation = get_inflation_rate()
        if adjust_for_inflation:
            st.markdown(f"Current inflation rate: **{current_inflation:.1%}**")
        
        discount_method = st.radio(
            "Discount Rate Method",
            ["Use industry default", "Manual override"],
            index=0,
            help="Industry defaults are based on typical WACC for each sector"
        )
        
        if discount_method == "Manual override":
            discount_rate = st.slider(
                "Discount Rate (%)", 
                5.0, 20.0, 10.0, 0.5,
                help="Higher rates mean more conservative valuations"
            )
        else:
            st.markdown("**Suggested by industry:**")
        
        growth_period = st.slider(
            "Growth Period (years)", 
            1, 10, 5, 1,
            help="Number of years for high growth phase"
        )
        terminal_growth = st.slider(
            "Terminal Growth Rate (%)", 
            0.0, 5.0, 2.5, 0.1,
            help="Long-term sustainable growth rate after growth period"
        )
        
        if st.button("🔄 Recalculate DCF", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    # Main analysis flow
    if uploaded_file is not None:
        try:
            excel_data = pd.read_excel(uploaded_file)
            if excel_data.empty:
                st.error("Uploaded file is empty")
                return
            
            # Get and validate tickers
            raw_tickers = [str(t).strip() for t in excel_data.iloc[:, 0].dropna().tolist()]
            tickers, invalid_tickers = validate_tickers(raw_tickers)
            
            if not tickers:
                st.error("No valid tickers found in the file")
                return
            
            if invalid_tickers:
                st.warning(f"Invalid tickers ignored: {', '.join(invalid_tickers)}")
            
            if len(tickers) > MAX_TICKERS:
                st.warning(f"Limited to first {MAX_TICKERS} tickers (free tier limit)")
                tickers = tickers[:MAX_TICKERS]
            
            st.success(f"Analyzing {len(tickers)} valid tickers")
            
            # Process tickers
            results, failed = scan_tickers(
                tickers, period, discount_method,
                discount_rate if discount_method == "Manual override" else None,
                growth_period, terminal_growth,
                adjust_for_inflation, current_inflation
            )
            
            # Display results
            if results:
                display_results(results)
            
            if failed:
                st.warning(f"Failed to analyze: {', '.join(failed)}")
        
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
    
    # Sample file section
    st.markdown("---")
    st.subheader("📋 Sample File")
    sample = pd.DataFrame({"Tickers": ["AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "NVDA", "JPM", "V", "WMT"]})
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.dataframe(sample, hide_index=True)
    with col2:
        st.download_button(
            "⬇️ Download Sample",
            data=sample.to_csv(index=False).encode('utf-8'),
            file_name="sample_tickers.csv",
            mime="text/csv",
            use_container_width=True
        )

if __name__ == "__main__":
    main()
