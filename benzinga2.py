import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.title("📊 Watchlist Metrics Enricher")

st.markdown("### Upload your watchlist (XLSX, must have a 'Symbol' column)")

uploaded_file = st.file_uploader(
    label="Drag and drop file here",
    type=["xlsx"],
    accept_multiple_files=False,
    help="Limit 200MB per file • XLSX",
)

if uploaded_file:
    try:
        df_watchlist = pd.read_excel(uploaded_file)
        st.success("File uploaded successfully!")
        st.write("Preview:", df_watchlist.head())

        if "Symbol" not in df_watchlist.columns:
            st.error("Uploaded file must have a 'Symbol' column.")
        else:
            st.dataframe(df_watchlist)

            if st.button("Add Metrics"):
                @st.cache_data(show_spinner=True)
                def fetch_metrics(symbol):
                    try:
                        ticker = yf.Ticker(symbol)
                        hist = ticker.history(period="1mo")
                        if hist.empty:
                            return [np.nan]*5
                        current_price = hist["Close"][-1]
                        avg_volume = hist["Volume"].mean() / 1e6
                        high = hist["High"].rolling(window=14).max()
                        low = hist["Low"].rolling(window=14).min()
                        prev_close = hist["Close"].shift(1)
                        tr = pd.concat([
                            high - low,
                            abs(high - prev_close),
                            abs(low - prev_close)
                        ], axis=1).max(axis=1)
                        atr = tr.rolling(window=14).mean().iloc[-1]
                        atr_pct = atr / current_price * 100 if current_price else np.nan
                        volume_pct = avg_volume / (hist["Volume"].max() / 1e6) * 100 if hist["Volume"].max() else np.nan
                        return [current_price, avg_volume, atr, atr_pct, volume_pct]
                    except Exception as e:
                        return [np.nan]*5

                # Add new columns
                newcols = ["Current Price", "Avg Volume (M)", "ATR (Volatility)", "ATR (% of Price)", "Volume as % of Max"]
                st.info("Fetching metrics. Please wait (may take a few seconds)...")
                df_metrics = df_watchlist["Symbol"].apply(lambda x: pd.Series(fetch_metrics(x), index=newcols))
                df_enriched = pd.concat([df_watchlist, df_metrics], axis=1)
                st.dataframe(df_enriched)

                # Download button
                csv = df_enriched.to_csv(index=False).encode('utf-8')
                st.download_button("Download Enriched Table as CSV", csv, "enriched_watchlist.csv", "text/csv")

    except Exception as e:
        st.error(f"Error reading the Excel file: {e}")
else:
    st.info("Upload an XLSX file to begin.")
