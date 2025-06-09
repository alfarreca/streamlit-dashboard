import streamlit as st
import pandas as pd

# ---- MOCK IMPLEMENTATION FOR backtest_ticker ----
# Replace this with your actual backtesting logic as needed.
def backtest_ticker(ticker, threshold=80, holding_days=[5, 10, 20]):
    # This mock just creates a DataFrame with dummy returns for demonstration
    data = {
        "Ticker": [ticker] * len(holding_days),
        "Holding Days": holding_days,
    }
    for h in holding_days:
        data[f"Return_{h}D"] = [round((hash(ticker) % 100) / 10 - 5 + h, 2)]
    return pd.DataFrame(data)

st.title("Momentum Backtest Tool")

# File uploader for Excel files with tickers
uploaded_file = st.file_uploader(
    "Upload an Excel file with tickers (column name: Ticker)", 
    type=["xlsx"]
)

# Disable manual input if file is uploaded
manual_disabled = uploaded_file is not None
tickers = st.text_input(
    "Or enter tickers manually (comma-separated)", 
    value="FCX,NUE,RIO.L",
    disabled=manual_disabled
)

threshold = st.number_input(
    "Momentum score threshold", min_value=0, max_value=100, value=80
)
holding_days = st.multiselect(
    "Holding periods (days)", [5, 10, 20], default=[5, 10, 20]
)

run = st.button("Run Backtest")

if run:
    user_tickers = []
    # If file uploaded, use tickers from file
    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            if 'Ticker' in df.columns:
                user_tickers = df['Ticker'].dropna().astype(str).str.strip().str.upper().tolist()
            else:
                st.warning("No column named 'Ticker' found in your file.")
        except Exception as e:
            st.error(f"Error reading Excel file: {e}")
    else:
        # If no file, use manual entry
        user_tickers = [t.strip().upper() for t in tickers.split(",") if t.strip()]

    if not user_tickers:
        st.warning("No tickers provided. Please enter or upload at least one.")
    else:
        all_results = []
        with st.spinner("Running backtest..."):
            for t in user_tickers:
                df = backtest_ticker(t, threshold=threshold, holding_days=holding_days)
                if df is not None and not df.empty:
                    all_results.append(df)
        if all_results:
            final_df = pd.concat(all_results, ignore_index=True)
            st.success("Backtest completed!")

            # Show summary stats per holding period
            summary = []
            for h in holding_days:
                col = f"Return_{h}D"
                if col in final_df:
                    avg_return = final_df[col].mean()
                    win_rate = (final_df[col] > 0).mean() * 100
                    summary.append({
                        "Holding Period": f"{h} Days",
                        "Avg Return (%)": round(avg_return, 2),
                        "Win Rate (%)": round(win_rate, 2)
                    })
            if summary:
                st.subheader("Summary Stats")
                st.dataframe(pd.DataFrame(summary))

            # Show a snippet of detailed results
            st.subheader("Sample Backtest Results")
            st.dataframe(final_df.head(20))

            # CSV download
            csv = final_df.to_csv(index=False).encode()
            st.download_button(
                label="Download All Results as CSV",
                data=csv,
                file_name="momentum_backtest_results.csv",
                mime="text/csv"
            )
        else:
            st.warning("No results. Try different tickers or parameters.")
else:
    st.info("Configure your options and click 'Run Backtest'.")
