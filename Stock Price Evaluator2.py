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
    discount_rate = st.slider("Discount Rate (%)", 5.0, 15.0, 8.0, 0.5)
    growth_period = st.slider("Growth Period (years)", 1, 10, 5)
    terminal_growth = st.slider("Terminal Growth Rate (%)", 0.0, 5.0, 2.5, 0.1)
    if st.button("Recalculate DCF"):
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
def get_stock_data(ticker, period, discount_rate, growth_period, terminal_growth):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        info = stock.info

        # Get cash flow data
        cashflow = stock.cashflow
        free_cash_flow = cashflow.loc['Free Cash Flow'].iloc[0] if cashflow is not None and 'Free Cash Flow' in cashflow.index else np.nan
        
        data = {
            "Ticker": ticker,
            "Current Price": info.get('currentPrice', info.get('regularMarketPrice', np.nan)),
            "Free Cash Flow (ttm)": free_cash_flow,
            "Revenue Growth (3Y)": info.get('revenueGrowth', np.nan),
            "Operating Cash Flow": info.get('operatingCashflow', np.nan),
            "52 Week High": info.get('fiftyTwoWeekHigh', np.nan),
            "52 Week Low": info.get('fiftyTwoWeekLow', np.nan),
            "PE Ratio": info.get('trailingPE', np.nan),
            "Forward PE": info.get('forwardPE', np.nan),
            "PEG Ratio": info.get('pegRatio', np.nan),
            "PS Ratio": info.get('priceToSalesTrailing12Months', np.nan),
            "PB Ratio": info.get('priceToBook', np.nan),
            "Dividend Yield": info.get('dividendYield', np.nan),
            "Market Cap": info.get('marketCap', np.nan),
            "Beta": info.get('beta', np.nan),
            "Sector": info.get('sector', 'N/A'),
            "Industry": info.get('industry', 'N/A')
        }
        
        # Calculate intrinsic value if we have FCF data
        if not np.isnan(free_cash_flow) and free_cash_flow > 0:
            growth_rate = info.get('revenueGrowth', 0.05)  # Default to 5% if not available
            intrinsic_value = calculate_dcf(
                free_cash_flow, 
                growth_rate, 
                discount_rate/100, 
                growth_period, 
                terminal_growth/100
            )
            shares_outstanding = info.get('sharesOutstanding', np.nan)
            if not np.isnan(shares_outstanding) and shares_outstanding > 0:
                intrinsic_value_per_share = intrinsic_value / shares_outstanding
                data["Intrinsic Value"] = intrinsic_value_per_share
                if not np.isnan(data["Current Price"]):
                    data["Margin of Safety"] = (intrinsic_value_per_share - data["Current Price"]) / intrinsic_value_per_share
        
        return data, hist
    except Exception as e:
        st.error(f"Error fetching data for {ticker}: {str(e)}")
        return None, None

@st.cache_data(show_spinner="Scanning tickers...")
def scan_tickers(tickers, period, discount_rate, growth_period, terminal_growth):
    results = []
    failed_tickers = []
    for ticker in tickers:
        data, history = get_stock_data(ticker, period, discount_rate, growth_period, terminal_growth)
        if data:
            results.append(data)
        else:
            failed_tickers.append(ticker)
    return results, failed_tickers

@st.cache_data(show_spinner="Fetching benchmark data...")
def get_benchmark_data(benchmark_ticker, period):
    try:
        return yf.Ticker(benchmark_ticker).history(period=period)
    except Exception:
        return None

@st.cache_data(show_spinner="Fetching price history...")
def get_history(ticker, period):
    try:
        return yf.Ticker(ticker).history(period=period)
    except Exception:
        return pd.DataFrame()

if uploaded_file is not None:
    try:
        excel_data = pd.read_excel(uploaded_file)
        tickers = [str(t).strip().upper() for t in excel_data.iloc[:, 0].dropna().tolist()]

        if not tickers:
            st.warning("No tickers found in the uploaded file.")
        else:
            st.success(f"Found {len(tickers)} tickers in the uploaded file")

            # Scan all tickers (cached)
            results, failed_tickers = scan_tickers(tickers, period, discount_rate, growth_period, terminal_growth)

            # Get benchmark history (cached)
            benchmark_data = None
            if benchmark != "None":
                benchmark_ticker = benchmark.split()[0]
                benchmark_data = get_benchmark_data(benchmark_ticker, period)

            if results:
                df = pd.DataFrame(results)
                df = df.replace({None: np.nan})

                num_cols = [
                    "Current Price", "Free Cash Flow (ttm)", "Revenue Growth (3Y)", 
                    "Operating Cash Flow", "52 Week High", "52 Week Low", 
                    "PE Ratio", "Forward PE", "PEG Ratio", "PS Ratio", 
                    "PB Ratio", "Dividend Yield", "Market Cap", "Beta",
                    "Intrinsic Value", "Margin of Safety"
                ]
                
                for col in num_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')

                st.subheader("Fundamental Valuation Metrics")
                
                # Formatting dictionary
                format_dict = {
                    "Current Price": "${:.2f}",
                    "Free Cash Flow (ttm)": "${:,.0f}",
                    "Revenue Growth (3Y)": "{:.1%}",
                    "Operating Cash Flow": "${:,.0f}",
                    "52 Week High": "${:.2f}",
                    "52 Week Low": "${:.2f}",
                    "PE Ratio": "{:.1f}",
                    "Forward PE": "{:.1f}",
                    "PEG Ratio": "{:.2f}",
                    "PS Ratio": "{:.2f}",
                    "PB Ratio": "{:.2f}",
                    "Dividend Yield": "{:.2%}",
                    "Market Cap": "${:,.0f}",
                    "Beta": "{:.2f}",
                    "Intrinsic Value": "${:.2f}",
                    "Margin of Safety": "{:.1%}"
                }
                
                st.dataframe(df.style.format(format_dict))

                # Download button for results
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Stock Analysis')
                st.download_button(
                    label="Download Results as Excel",
                    data=output.getvalue(),
                    file_name="stock_analysis_results.xlsx",
                    mime="application/vnd.ms-excel"
                )

                # --- DCF Analysis Section ---
                st.subheader("Discounted Cash Flow Analysis")
                valid_tickers = df["Ticker"].tolist()
                selected_ticker = st.selectbox("Select ticker for DCF analysis", valid_tickers)
                
                selected_data = df[df["Ticker"] == selected_ticker].iloc[0]
                
                if not pd.isna(selected_data.get("Free Cash Flow (ttm)", np.nan)):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Current Price", f"${selected_data['Current Price']:.2f}")
                        st.metric("Intrinsic Value", f"${selected_data.get('Intrinsic Value', 'N/A'):.2f}")
                    with col2:
                        st.metric("Free Cash Flow", f"${selected_data['Free Cash Flow (ttm)']:,.0f}")
                        st.metric("Margin of Safety", f"{selected_data.get('Margin of Safety', 'N/A'):.1%}")
                    
                    # Show DCF assumptions
                    with st.expander("DCF Assumptions"):
                        st.write(f"**Growth Rate:** {selected_data['Revenue Growth (3Y)']:.1%} (based on 3Y revenue growth)")
                        st.write(f"**Growth Period:** {growth_period} years")
                        st.write(f"**Discount Rate:** {discount_rate:.1f}%")
                        st.write(f"**Terminal Growth Rate:** {terminal_growth:.1f}%")
                else:
                    st.warning(f"Free Cash Flow data not available for {selected_ticker}")

                # --- Price Performance Section ---
                st.subheader("Price Performance")
                selected_history = get_history(selected_ticker, period)

                if not selected_history.empty and (benchmark_data is None or not benchmark_data.empty):
                    norm_selected = selected_history['Close'] / selected_history['Close'].iloc[0]
                    df_selected = norm_selected.rename('NormPrice_Ticker').to_frame()
                    
                    norm_benchmark = None
                    df_benchmark = None
                    if benchmark_data is not None and not benchmark_data.empty:
                        norm_benchmark = benchmark_data['Close'] / benchmark_data['Close'].iloc[0]
                        df_benchmark = norm_benchmark.rename('NormPrice_Benchmark').to_frame()

                    # Merge on dates (outer), fill missing
                    if df_benchmark is not None:
                        merged = pd.merge(df_selected, df_benchmark, left_index=True, right_index=True, how='outer')
                        merged = merged.ffill().bfill()
                    else:
                        merged = df_selected

                    fig, ax = plt.subplots(figsize=(10, 5))
                    ax.plot(
                        merged.index, merged['NormPrice_Ticker'],
                        label=selected_ticker,
                        color='#0057b7', linewidth=3, marker='o', markersize=6, markerfacecolor='white', markeredgewidth=2
                    )
                    if df_benchmark is not None:
                        ax.plot(
                            merged.index, merged['NormPrice_Benchmark'],
                            label=benchmark,
                            color='#ff6600', linewidth=3, marker='s', markersize=6, markerfacecolor='white', markeredgewidth=2
                        )
                    ax.set_ylabel("Normalized Price (Starting at 1.0)", fontsize=12)
                    ax.set_title(f"{selected_ticker} vs Benchmark Price Performance", fontsize=15, weight='bold')
                    ax.legend(fontsize=12)
                    ax.grid(True, linestyle=':', alpha=0.7)
                    ax.tick_params(axis='x', labelsize=10)
                    ax.tick_params(axis='y', labelsize=10)
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                    fig.autofmt_xdate()
                    st.pyplot(fig)
                else:
                    st.warning("Not enough data available to plot price performance.")

                # --- Valuation Metrics Comparison ---
                st.subheader("Valuation Metrics Comparison")
                metrics = [
                    "PE Ratio", "Forward PE", "PEG Ratio", "PS Ratio", 
                    "PB Ratio", "Dividend Yield", "Free Cash Flow (ttm)"
                ]
                selected_metric = st.selectbox("Select metric to compare", metrics)

                if selected_metric in df.columns:
                    valid_data = df.dropna(subset=[selected_metric])
                    colors = [
                        '#0057b7' if ticker == selected_ticker else 'lightgrey'
                        for ticker in valid_data["Ticker"]
                    ]
                    
                    fig2, ax2 = plt.subplots(figsize=(10, 5))
                    bars = ax2.bar(valid_data["Ticker"], valid_data[selected_metric], color=colors)
                    ax2.set_title(f"Comparison of {selected_metric}")
                    ax2.set_ylabel(selected_metric)
                    
                    # Add value labels on top of bars
                    for bar in bars:
                        height = bar.get_height()
                        ax2.text(bar.get_x() + bar.get_width()/2., height,
                                f'{height:,.2f}' if not selected_metric.endswith('(ttm)') else f'${height:,.0f}',
                                ha='center', va='bottom')
                    
                    plt.xticks(rotation=45)
                    st.pyplot(fig2)

            if failed_tickers:
                st.warning(f"No data found for the following tickers: {', '.join(failed_tickers)}")

    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
else:
    st.info("Please upload an Excel file to begin analysis")

# Sample file download
st.markdown("### Need a sample file?")
sample_data = pd.DataFrame({"Tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "JNJ", "V", "WMT", "PG"]})
st.write(sample_data)
csv = sample_data.to_csv(index=False).encode('utf-8')
st.download_button(
    label="Download Sample CSV",
    data=csv,
    file_name="sample_tickers.csv",
    mime="text/csv"
)