import streamlit as st
import pandas as pd
from io import BytesIO
from momentum_backtest import backtest_ticker

st.title("Momentum Backtest Tool")

tickers = st.text_input(
    "Enter tickers (comma-separated)", 
    value="FCX,NUE,RIO.L"
)
threshold = st.number_input(
    "Momentum score threshold", min_value=0, max_value=100, value=80
)
holding_days = st.multiselect(
    "Holding periods (days)", [5, 10, 20], default=[5, 10, 20]
)

run = st.button("Run Backtest")

if run:
    user_tickers = [t.strip().upper() for t in tickers.split(",") if t.strip()]
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
