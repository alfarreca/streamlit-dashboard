import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
import numpy as np

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

def get_stock_data(ticker, period):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        info = stock.info

        data = {
            "Ticker": ticker,
            "Current Price": info.get('currentPrice', info.get('regularMarketPrice', np.nan)),
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
            "Volume": info.get('volume', np.nan),
            "Avg Volume": info.get('averageVolume', np.nan),
            "Sector": info.get('sector', 'N/A'),
            "Industry": info.get('industry', 'N/A')
        }
        return data, hist

    except Exception:
        return None, None

if uploaded_file is not None:
    try:
        excel_data = pd.read_excel(uploaded_file)
        tickers = [str(t).strip().upper() for t in excel_data.iloc[:, 0].dropna().tolist()]

        if not tickers:
            st.warning("No tickers found in the uploaded file.")
        else:
            st.success(f"Found {len(tickers)} tickers in the uploaded file")
            progress_bar = st.progress(0)
            status_text = st.empty()

            results = []
            failed_tickers = []
            benchmark_data = None

            if benchmark != "None":
                benchmark_ticker = benchmark.split()[0]
                try:
                    benchmark_data = yf.Ticker(benchmark_ticker).history(period=period)
                except Exception:
                    benchmark_data = None

            for i, ticker in enumerate(tickers):
                status_text.text(f"Fetching data for {ticker} ({i + 1}/{len(tickers)})")
                data, history = get_stock_data(ticker, period)
                if data:
                    results.append(data)
                else:
                    failed_tickers.append(ticker)
                progress_bar.progress((i + 1) / len(tickers))

            if results:
                df = pd.DataFrame(results)
                df = df.replace({None: np.nan})

                num_cols = [
                    "Current Price", "52 Week High", "52 Week Low", "PE Ratio", "Forward PE",
                    "PEG Ratio", "PS Ratio", "PB Ratio", "Dividend Yield", "Market Cap",
                    "Beta", "Volume", "Avg Volume"
                ]
                for col in num_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')

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

                # Visualization section - **Corrected Block**
                st.subheader("Price Performance")
                valid_tickers = df["Ticker"].tolist()
                selected_ticker = st.selectbox("Select ticker to visualize", valid_tickers)
                selected_history = yf.Ticker(selected_ticker).history(period=period)

                # Only plot if we have enough data
                if not selected_history.empty and (benchmark_data is None or not benchmark_data.empty):
                    fig, ax = plt.subplots(figsize=(10, 5))
                    # Normalize both series
                    norm_selected = selected_history['Close'] / selected_history['Close'].iloc[0]
                    ax.plot(selected_history.index, norm_selected, label=selected_ticker, color='blue')

                    if benchmark_data is not None and not benchmark_data.empty:
                        # Align dates for fair comparison (inner join)
                        norm_benchmark = benchmark_data['Close'] / benchmark_data['Close'].iloc[0]
                        # Intersect dates
                        common_dates = selected_history.index.intersection(benchmark_data.index)
                        ax.plot(common_dates, norm_selected.loc[common_dates], label=f"{selected_ticker} (aligned)", color='blue', alpha=0.5)
                        ax.plot(common_dates, norm_benchmark.loc[common_dates], label=benchmark, color='orange')
                        ax.set_ylabel("Normalized Price (Starting at 1.0)")
                    else:
                        ax.set_ylabel("Normalized Price (Starting at 1.0)")

                    ax.set_title(f"{selected_ticker} vs Benchmark Price Performance")
                    ax.legend()
                    ax.grid(True)
                    st.pyplot(fig)
                else:
                    st.warning("Not enough data available to plot price performance.")

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

            if failed_tickers:
                st.warning(f"No data found for the following tickers: {', '.join(failed_tickers)}")

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
