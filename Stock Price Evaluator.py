import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO

# App title
st.title("📈 Stock Price Evaluator")
st.markdown("Upload an Excel file with stock tickers to get current market data and valuation metrics")

# Sidebar for user inputs
with st.sidebar:
    st.header("Configuration")
    uploaded_file = st.file_uploader("Upload Excel File (xlsx)", type=["xlsx"])
    benchmark = st.selectbox(
        "Compare to Benchmark",
        ["^GSPC (S&P 500)", "^IXIC (NASDAQ)", "^DJI (Dow Jones)", "None"]
    )
    period = st.selectbox(
        "Historical Period",
        ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y"]
    )

# Function to fetch stock data
def get_stock_data(ticker, period):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        info = stock.info
        
        # Get key metrics
        data = {
            "Ticker": ticker,
            "Current Price": info.get('currentPrice', info.get('regularMarketPrice', None)),
            "52 Week High": info.get('fiftyTwoWeekHigh', None),
            "52 Week Low": info.get('fiftyTwoWeekLow', None),
            "PE Ratio": info.get('trailingPE', None),
            "Forward PE": info.get('forwardPE', None),
            "PEG Ratio": info.get('pegRatio', None),
            "PS Ratio": info.get('priceToSalesTrailing12Months', None),
            "PB Ratio": info.get('priceToBook', None),
            "Dividend Yield": info.get('dividendYield', None),
            "Market Cap": info.get('marketCap', None),
            "Beta": info.get('beta', None),
            "Volume": info.get('volume', None),
            "Avg Volume": info.get('averageVolume', None),
            "Sector": info.get('sector', 'N/A'),
            "Industry": info.get('industry', 'N/A')
        }
        
        return data, hist
    
    except Exception as e:
        st.error(f"Error fetching data for {ticker}: {str(e)}")
        return None, None

# Main app logic
if uploaded_file is not None:
    # Read Excel file
    try:
        excel_data = pd.read_excel(uploaded_file)
        tickers = excel_data.iloc[:, 0].tolist()  # Assume tickers are in first column
        
        if not tickers:
            st.warning("No tickers found in the uploaded file.")
        else:
            st.success(f"Found {len(tickers)} tickers in the uploaded file")
            
            # Progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            results = []
            benchmark_data = None
            
            # Get benchmark data if selected
            if benchmark != "None":
                benchmark_ticker = benchmark.split()[0]
                benchmark_data = yf.Ticker(benchmark_ticker).history(period=period)
            
            # Fetch data for each ticker
            for i, ticker in enumerate(tickers):
                status_text.text(f"Fetching data for {ticker} ({i+1}/{len(tickers)})")
                data, history = get_stock_data(ticker, period)
                if data:
                    results.append(data)
                progress_bar.progress((i + 1) / len(tickers))
            
            # Display results
            if results:
                df = pd.DataFrame(results)
                st.subheader("Stock Valuation Metrics")
                st.dataframe(df.style.format({
                    "Current Price": "{:.2f}",
                    "52 Week High": "{:.2f}",
                    "52 Week Low": "{:.2f}",
                    "PE Ratio": "{:.2f}",
                    "Forward PE": "{:.2f}",
                    "PEG Ratio": "{:.2f}",
                    "PS Ratio": "{:.2f}",
                    "PB Ratio": "{:.2f}",
                    "Dividend Yield": "{:.2%}",
                    "Market Cap": "{:,.0f}",
                    "Beta": "{:.2f}",
                    "Volume": "{:,.0f}",
                    "Avg Volume": "{:,.0f}"
                }))
                
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
                
                # Visualization section
                st.subheader("Price Performance")
                selected_ticker = st.selectbox("Select ticker to visualize", tickers)
                
                # Get selected ticker's history
                selected_history = yf.Ticker(selected_ticker).history(period=period)
                
                # Plot price chart
                fig, ax = plt.subplots(figsize=(10, 5))
                ax.plot(selected_history.index, selected_history['Close'], label=selected_ticker)
                
                if benchmark_data is not None:
                    # Normalize both to percentage change for fair comparison
                    norm_selected = selected_history['Close'] / selected_history['Close'].iloc[0]
                    norm_benchmark = benchmark_data['Close'] / benchmark_data['Close'].iloc[0]
                    ax.plot(benchmark_data.index, norm_benchmark, label=benchmark, alpha=0.7)
                    ax.set_ylabel("Normalized Price (Starting at 1.0)")
                else:
                    ax.set_ylabel("Price ($)")
                
                ax.set_title(f"{selected_ticker} Price Performance")
                ax.legend()
                ax.grid(True)
                st.pyplot(fig)
                
                # Additional metrics visualization
                st.subheader("Valuation Metrics Comparison")
                metrics = ["PE Ratio", "Forward PE", "PEG Ratio", "PS Ratio", "PB Ratio", "Dividend Yield"]
                selected_metric = st.selectbox("Select metric to compare", metrics)
                
                if selected_metric in df.columns:
                    fig2, ax2 = plt.subplots(figsize=(10, 5))
                    valid_data = df.dropna(subset=[selected_metric])
                    ax2.bar(valid_data["Ticker"], valid_data[selected_metric])
                    ax2.set_title(f"Comparison of {selected_metric}")
                    ax2.set_ylabel(selected_metric)
                    plt.xticks(rotation=45)
                    st.pyplot(fig2)
                
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
else:
    st.info("Please upload an Excel file to begin analysis")

# Sample file download
st.markdown("### Need a sample file?")
sample_data = pd.DataFrame({"Tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]})
st.write(sample_data)
csv = sample_data.to_csv(index=False).encode('utf-8')
st.download_button(
    label="Download Sample CSV",
    data=csv,
    file_name="sample_tickers.csv",
    mime="text/csv"
)
