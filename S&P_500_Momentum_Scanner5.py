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

    # --- UPDATED SYMBOL SELECTION AND DETAILS SECTION ---
    if not filtered.empty:
        if (
            "selected_symbol" not in st.session_state
            or st.session_state.selected_symbol not in filtered["Symbol"].values
        ):
            st.session_state.selected_symbol = filtered["Symbol"].iloc[0]

        selected = st.selectbox(
            "Select a symbol for details",
            filtered["Symbol"],
            index=filtered["Symbol"].tolist().index(st.session_state.selected_symbol),
            key="selected_symbol"
        )

        st.session_state.selected_symbol = selected
        display_symbol_details(selected)
