import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
import numpy as np
import matplotlib.dates as mdates

st.title("📈 Fundamental Stock Evaluator")
st.markdown("""
**Stocks are priced according to the value of their future cash flows.**  
Upload an Excel file with stock tickers to analyze valuation based on cash flow fundamentals.
""")

# Industry-specific discount rate suggestions (mid-2024)
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

with st.sidebar:
    st.header("Configuration")
    uploaded_file = st.file_uploader("Upload Excel File (xlsx)", type=["xlsx"])
    benchmark = st.selectbox(
        "Compare to Benchmark",
        [
            "^GSPC (S&P 500)", 
            "^IXIC (NASDAQ)", 
            "^DJI (Dow Jones)", 
            "EXS1.DE (Dax ETF)",
            "EUDF.DE (ISHARES Defense Europe)",
            "CAC.PA (CAC ETF)",
            "GDX (Gold Miners ETF)", 
            "None"
        ]
    )
    period = st.selectbox(
        "Historical Period",
        ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y"]
    )
    st.markdown("---")
    st.markdown("**Valuation Settings**")
    
    # Dynamic discount rate selection
    st.markdown("### Discount Rate Selection")
    discount_method = st.radio(
        "Discount Rate Method",
        ["Use industry default", "Manual override"],
        index=0
    )
    
    if discount_method == "Manual override":
        discount_rate = st.slider(
            "Manual Discount Rate (%)",
            5.0, 20.0, 10.0, 0.5,
            help="Higher for risky companies, lower for stable ones"
        )
    else:
        st.markdown(f"**Suggested by industry:**")
    
    growth_period = st.slider(
        "Growth Period (years)",
        1, 10, 5,
        help="Years of above-average growth before terminal phase"
    )
    terminal_growth = st.slider(
        "Terminal Growth Rate (%)",
        0.0, 5.0, 2.5, 0.1,
        help="Long-term stable growth rate (typically 2-3%)"
    )
    
    # Educational tooltip
    with st.expander("💡 Discount Rate Guidance"):
        st.markdown("""
        **2024 Suggested Rates by Industry:**
        - Technology: 10-11%
        - Healthcare: 8-9%
        - Consumer Staples: 7-8%
        - Financials: 9-10%
        - Utilities: 6-7%
        - Energy: 9-10%
        
        **Current Market Conditions (mid-2024):**
        - Risk-free rate: ~4.2% (10Y Treasury)
        - Equity risk premium: 5-6%
        - Typical WACC range: 7-12%
        """)
    
    if st.button("Recalculate DCF", help="Force refresh all calculations"):
        st.cache_data.clear()
        st.rerun()

def calculate_dcf(fcf, growth_rate, discount_rate, growth_period, terminal_growth):
    """Calculate intrinsic value using discounted cash flow model"""
    present_value = 0
    
    # Projected cash flows during growth period
    for year in range(1, growth_period + 1):
        future_fcf = fcf * (1 + growth_rate) ** year
        present_value += future_fcf / ((1 + discount_rate) ** year)
    
    # Terminal value
    terminal_fcf = fcf * (1 + growth_rate) ** growth_period
    terminal_value = (terminal_fcf * (1 + terminal_growth)) / (discount_rate - terminal_growth)
    present_terminal_value = terminal_value / ((1 + discount_rate) ** growth_period)
    
    return present_value + present_terminal_value

@st.cache_data(
    show_spinner="Fetching stock data...",
    hash_funcs={
        "builtins.float": lambda x: hash(x),
        "builtins.int": lambda x: hash(x),
    }
)
def get_stock_data(ticker, period, discount_method, manual_discount_rate, growth_period, terminal_growth):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        info = stock.info
        sector = info.get('sector', 'Technology')
        
        # Determine discount rate
        if discount_method == "Use industry default":
            discount_rate = SECTOR_DISCOUNT_RATES.get(sector, 10.0) / 100
            suggested_rate = SECTOR_DISCOUNT_RATES.get(sector, 10.0)
        else:
            discount_rate = manual_discount_rate / 100
            suggested_rate = manual_discount_rate

        # Get cash flow data
        cashflow = stock.cashflow
        free_cash_flow = cashflow.loc['Free Cash Flow'].iloc[0] if cashflow is not None and 'Free Cash Flow' in cashflow.index else np.nan
        
        data = {
            "Ticker": ticker,
            "Sector": sector,
            "Suggested Discount Rate": suggested_rate,
            "Current Price": info.get('currentPrice', info.get('regularMarketPrice', np.nan)),
            "Free Cash Flow (ttm)": free_cash_flow,
            "Revenue Growth (3Y)": info.get('revenueGrowth', np.nan),
            "Operating Cash Flow": info.get('operatingCashflow', np.nan),
            "PE Ratio": info.get('trailingPE', np.nan),
            "Forward PE": info.get('forwardPE', np.nan),
            "Market Cap": info.get('marketCap', np.nan),
            "Beta": info.get('beta', np.nan),
        }
        
        # Calculate intrinsic value if we have FCF data
        if not np.isnan(free_cash_flow) and free_cash_flow > 0:
            growth_rate = info.get('revenueGrowth', 0.05)  # Default to 5% if not available
            intrinsic_value = calculate_dcf(
                free_cash_flow, 
                growth_rate, 
                discount_rate, 
                growth_period, 
                terminal_growth/100
            )
            shares_outstanding = info.get('sharesOutstanding', np.nan)
            if not np.isnan(shares_outstanding) and shares_outstanding > 0:
                data["Intrinsic Value"] = intrinsic_value / shares_outstanding
                if not np.isnan(data["Current Price"]):
                    data["Margin of Safety"] = (
                        (data["Intrinsic Value"] - data["Current Price"]) / data["Intrinsic Value"]
                    )
        
        return data, hist
    except Exception as e:
        st.error(f"Error fetching data for {ticker}: {str(e)}")
        return None, None

@st.cache_data(show_spinner="Scanning tickers...")
def scan_tickers(tickers, period, discount_method, manual_discount_rate, growth_period, terminal_growth):
    results = []
    failed_tickers = []
    for ticker in tickers:
        data, history = get_stock_data(
            ticker, 
            period, 
            discount_method,
            manual_discount_rate,
            growth_period, 
            terminal_growth
        )
        if data:
            results.append(data)
        else:
            failed_tickers.append(ticker)
    return results, failed_tickers

# ... [keep the rest of your existing functions: get_benchmark_data, get_history] ...

if uploaded_file is not None:
    try:
        excel_data = pd.read_excel(uploaded_file)
        tickers = [str(t).strip().upper() for t in excel_data.iloc[:, 0].dropna().tolist()]

        if not tickers:
            st.warning("No tickers found in the uploaded file.")
        else:
            st.success(f"Found {len(tickers)} tickers in the uploaded file")

            # Scan all tickers
            results, failed_tickers = scan_tickers(
                tickers, 
                period, 
                discount_method,
                discount_rate if discount_method == "Manual override" else None,
                growth_period, 
                terminal_growth
            )

            if results:
                df = pd.DataFrame(results)
                df = df.replace({None: np.nan})

                # Formatting improvements
                format_dict = {
                    "Current Price": "${:.2f}",
                    "Free Cash Flow (ttm)": "${:,.0f}",
                    "Revenue Growth (3Y)": "{:.1%}",
                    "Suggested Discount Rate": "{:.1f}%",
                    "Intrinsic Value": "${:.2f}",
                    "Margin of Safety": "{:.1%}",
                    "Market Cap": "${:,.0f}",
                }
                
                # Display sector-aware metrics
                st.subheader("Valuation Metrics by Sector")
                st.dataframe(
                    df.style.format(format_dict).background_gradient(
                        subset=["Margin of Safety"],
                        cmap="RdYlGn",
                        vmin=-0.5,
                        vmax=0.5
                    ),
                    height=600
                )

                # ... [keep your existing download button and visualization code] ...

                # Enhanced DCF Analysis Section
                st.subheader("Discounted Cash Flow Analysis")
                selected_ticker = st.selectbox(
                    "Select ticker for detailed analysis",
                    df["Ticker"].tolist()
                )
                
                selected_data = df[df["Ticker"] == selected_ticker].iloc[0]
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Current Price", f"${selected_data['Current Price']:.2f}")
                    st.metric("Sector", selected_data['Sector'])
                with col2:
                    st.metric("Intrinsic Value", f"${selected_data.get('Intrinsic Value', 'N/A'):.2f}")
                    st.metric("Discount Rate Used", f"{selected_data['Suggested Discount Rate']:.1f}%")
                with col3:
                    st.metric("Margin of Safety", 
                            f"{selected_data.get('Margin of Safety', 'N/A'):.1%}",
                            delta_color="inverse")

                # ... [rest of your existing code] ...

# ... [keep sample file download section] ...
