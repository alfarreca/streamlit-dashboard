import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
import numpy as np
import matplotlib.dates as mdates

st.title("📈 Stock Price Evaluator")
st.markdown("Upload an Excel file with stock tickers to get current market data and valuation metrics")

with st.sidebar:
    st.header("Configuration")
    uploaded_file = st.file_uploader("Upload Excel File (xlsx)", type=["xlsx"])
    benchmark = st.selectbox(
        "Compare to Benchmark",
        [
            "^GSPC (S&P 500)", 
            "^IXIC (NASDAQ)", 
            "^DJI (Dow Jones)", 
            "GDX (Gold Miners ETF)", 
            "None"
        ]
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

                # --- Price Performance Section ---
                st.subheader("Price Performance")
                valid_tickers = df["Ticker"].tolist()
                selected_ticker = st.selectbox("Select ticker to visualize", valid_tickers)
                selected_history = yf.Ticker(selected_ticker).history(period=period)

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

                # --- Valuation Metrics Comparison with Selected Ticker Highlighted ---
                st.subheader("Valuation Metrics Comparison")
                metrics = ["PE Ratio", "Forward PE", "PEG Ratio", "PS Ratio", "PB Ratio", "Dividend Yield"]
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
