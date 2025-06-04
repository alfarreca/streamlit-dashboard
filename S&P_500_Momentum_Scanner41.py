import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_exponential
import pytz
import numpy as np

# ... [rest of your script above remains unchanged] ...

def main():
    st.set_page_config(page_title="S&P 500 Momentum Scanner", layout="wide")
    st.title("S&P 500 Momentum Scanner")

    df = get_google_sheet_data()
    if df.empty:
        st.warning("No data loaded from Google Sheets.")
        return

    df["YF_Symbol"] = df.apply(
        lambda row: map_to_yfinance_symbol(row["Symbol"], row["Exchange"]), axis=1
    )

    exchanges = sorted(df["Exchange"].unique().tolist())
    selected_exchange = st.sidebar.selectbox("Exchange", ["All"] + exchanges)
    min_score = st.sidebar.slider("Min Momentum Score", 0, 100, 50)

    ticker_data = []
    progress = st.progress(0, text="Fetching ticker data...")
    total = len(df)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(get_ticker_data, row["Symbol"], row["Exchange"], row["YF_Symbol"])
            for idx, row in df.iterrows()
        ]
        for i, f in enumerate(as_completed(futures)):
            data = f.result()
            if data:
                ticker_data.append(data)
            progress.progress((i + 1) / total, text=f"Processed {i+1}/{total} tickers")
    progress.empty()

    results_df = pd.DataFrame(ticker_data)
    st.session_state["raw_results_df"] = results_df.copy()

    if not results_df.empty:
        results_df = results_df.reset_index(drop=True)
        if selected_exchange != "All":
            filtered = results_df[
                (results_df["Momentum_Score"] >= min_score) &
                (results_df["Exchange"] == selected_exchange)
            ].copy()
        else:
            filtered = results_df[results_df["Momentum_Score"] >= min_score].copy()
    else:
        filtered = pd.DataFrame()

    st.session_state.filtered_results = filtered

    display_results(filtered)

    # --- Sticky selectbox for ticker selection ---
    if not filtered.empty:
        symbol_options = ["— Select a symbol —"] + filtered["Symbol"].tolist()
        placeholder = symbol_options[0]

        # Reset selection if filtered symbols change (to keep things in sync)
        if (
            "symbol_select" not in st.session_state
            or st.session_state.get("symbol_options") != symbol_options
        ):
            st.session_state["symbol_select"] = placeholder
            st.session_state["symbol_options"] = symbol_options

        # Get the current index for the selectbox
        try:
            current_index = symbol_options.index(st.session_state["symbol_select"])
        except ValueError:
            current_index = 0
            st.session_state["symbol_select"] = placeholder

        selected = st.selectbox(
            "Select a symbol for details",
            symbol_options,
            index=current_index,
            key="symbol_select_box"
        )

        if selected != st.session_state["symbol_select"]:
            st.session_state["symbol_select"] = selected

        if st.session_state["symbol_select"] != placeholder:
            display_symbol_details(st.session_state["symbol_select"])

if __name__ == "__main__":
    main()
