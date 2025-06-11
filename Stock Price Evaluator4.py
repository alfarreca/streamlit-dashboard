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

# Industry-specific discount rate suggestions
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

# Default inflation rate
DEFAULT_INFLATION = 0.025  # 2.5%

def get_inflation_rate():
    """Return current inflation rate"""
    return DEFAULT_INFLATION

with st.sidebar:
    st.header("Configuration")
    uploaded_file = st.file_uploader("Upload Excel File (xlsx)", type=["xlsx"])
    benchmark = st.selectbox(
        "Compare to Benchmark",
        ["^GSPC (S&P 500)", "^IXIC (NASDAQ)", "^DJI (Dow Jones)", 
         "EXS1.DE (Dax ETF)", "EUDF.DE (ISHARES Defense Europe)", 
         "CAC.PA (CAC ETF)", "GDX (Gold Miners ETF)", "None"]
    )
    period = st.selectbox("Historical Period", ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y"])
    
    st.markdown("---")
    st.markdown("**Valuation Settings**")
    
    adjust_for_inflation = st.checkbox("Adjust for inflation", value=True)
    current_inflation = get_inflation_rate()
    if adjust_for_inflation:
        st.markdown(f"Current inflation rate: {current_inflation:.1%}")
    
    discount_method = st.radio(
        "Discount Rate Method",
        ["Use industry default", "Manual override"],
        index=0
    )
    
    if discount_method == "Manual override":
        discount_rate = st.slider("Discount Rate (%)", 5.0, 20.0, 10.0, 0.5)
    else:
        st.markdown("**Suggested by industry:**")
    
    growth_period = st.slider("Growth Period (years)", 1, 10, 5)
    terminal_growth = st.slider("Terminal Growth Rate (%)", 0.0, 5.0, 2.5, 0.1)
    
    if st.button("Recalculate DCF"):
        st.cache_data.clear()
        st.rerun()

def calculate_dcf(fcf, growth_rate, discount_rate, growth_period, terminal_growth, inflation_rate=0.0):
    """Calculate intrinsic value using DCF model"""
    if inflation_rate > 0:
        real_discount = discount_rate - inflation_rate
        real_growth = growth_rate - inflation_rate
        real_terminal = max(0, terminal_growth - inflation_rate)
    else:
        real_discount = discount_rate
        real_growth = growth_rate
        real_terminal = terminal_growth
    
    present_value = 0
    for year in range(1, growth_period + 1):
        future_fcf = fcf * (1 + real_growth) ** year
        present_value += future_fcf / ((1 + real_discount) ** year)
    
    terminal_fcf = fcf * (1 + real_growth) ** growth_period
    terminal_value = (terminal_fcf * (1 + real_terminal)) / (real_discount - real_terminal)
    return present_value + (terminal_value / ((1 + real_discount) ** growth_period))

@st.cache_data(show_spinner="Fetching stock data...")
def get_stock_data(ticker, period, discount_method, manual_rate, growth_period, terminal_growth, adjust_inflation, inflation):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        info = stock.info
        sector = info.get('sector', 'Technology')
        
        if discount_method == "Use industry default":
            nominal_rate = SECTOR_DISCOUNT_RATES.get(sector, 10.0) / 100
            suggested_rate = SECTOR_DISCOUNT_RATES.get(sector, 10.0)
        else:
            nominal_rate = manual_rate / 100
            suggested_rate = manual_rate

        cashflow = stock.cashflow
        fcf = cashflow.loc['Free Cash Flow'].iloc[0] if (cashflow is not None and 'Free Cash Flow' in cashflow.index) else np.nan
        
        data = {
            "Ticker": ticker,
            "Sector": sector,
            "Discount Rate": suggested_rate,
            "Current Price": info.get('currentPrice', info.get('regularMarketPrice', np.nan)),
            "FCF (ttm)": fcf,
            "Revenue Growth": info.get('revenueGrowth', np.nan),
            "Inflation Adjusted": "Yes" if adjust_inflation else "No"
        }
        
        if not np.isnan(fcf) and fcf > 0:
            growth_rate = info.get('revenueGrowth', 0.05)
            intrinsic_value = calculate_dcf(
                fcf, growth_rate, nominal_rate, 
                growth_period, terminal_growth/100,
                inflation if adjust_inflation else 0.0
            )
            shares = info.get('sharesOutstanding', np.nan)
            if not np.isnan(shares) and shares > 0:
                data["Intrinsic Value"] = intrinsic_value / shares
                if not np.isnan(data["Current Price"]):
                    data["Margin of Safety"] = ((data["Intrinsic Value"] - data["Current Price"]) / data["Intrinsic Value"])
        
        return data, hist
    except Exception as e:
        st.error(f"Error processing {ticker}: {str(e)}")
        return None, None

@st.cache_data(show_spinner="Scanning tickers...")
def scan_tickers(tickers, period, discount_method, manual_rate, growth_period, terminal_growth, adjust_inflation, inflation):
    results = []
    failed = []
    for ticker in tickers:
        data, hist = get_stock_data(
            ticker, period, discount_method, manual_rate,
            growth_period, terminal_growth, adjust_inflation, inflation
        )
        if data:
            results.append(data)
        else:
            failed.append(ticker)
    return results, failed

def main():
    if uploaded_file is not None:
        try:
            excel_data = pd.read_excel(uploaded_file)
            tickers = [str(t).strip().upper() for t in excel_data.iloc[:, 0].dropna().tolist()]
            
            if not tickers:
                st.warning("No tickers found in the file.")
            else:
                st.success(f"Found {len(tickers)} tickers")
                
                results, failed = scan_tickers(
                    tickers, period, discount_method,
                    discount_rate if discount_method == "Manual override" else None,
                    growth_period, terminal_growth,
                    adjust_for_inflation, current_inflation
                )
                
                if results:
                    df = pd.DataFrame(results)
                    df = df.replace({None: np.nan})
                    
                    # Display results
                    st.subheader("Valuation Metrics")
                    st.dataframe(df.style.format({
                        "Current Price": "${:.2f}",
                        "FCF (ttm)": "${:,.0f}",
                        "Revenue Growth": "{:.1%}",
                        "Discount Rate": "{:.1f}%",
                        "Intrinsic Value": "${:.2f}",
                        "Margin of Safety": "{:.1%}"
                    }))
                    
                    # Download button
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df.to_excel(writer, index=False)
                    st.download_button(
                        "Download Results",
                        data=output.getvalue(),
                        file_name="stock_analysis.xlsx",
                        mime="application/vnd.ms-excel"
                    )
                
                if failed:
                    st.warning(f"Failed to fetch: {', '.join(failed)}")
        
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")

    # Sample file download
    st.markdown("### Sample File")
    sample = pd.DataFrame({"Tickers": ["AAPL", "MSFT", "GOOG", "AMZN", "META"]})
    st.write(sample)
    st.download_button(
        "Download Sample",
        data=sample.to_csv(index=False).encode('utf-8'),
        file_name="sample_tickers.csv",
        mime="text/csv"
    )

if __name__ == "__main__":
    main()
