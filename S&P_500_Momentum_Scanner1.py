# ========== FILTERS ==========
with st.sidebar:
    st.header("Momentum Filters")
    min_score = st.slider("Minimum Momentum Score", 0, 100, 70, 5)
    trend_options = ["↑ Strong", "↑ Medium", "↗ Weak"]
    selected_trends = st.multiselect("Trend Strength", options=trend_options, default=trend_options)
    price_range = st.slider("Price Range ($)", 0.0, 500.0, (10.0, 200.0), 5.0)
    exchange_options = df["Exchange"].unique()
    selected_exchanges = st.multiselect("Exchanges", options=exchange_options, default=["NASDAQ", "NYSE"])
    # Add ADX filter checkbox
    adx_filter = st.checkbox("Only show ADX > 25 (Strong Trends)", value=False)

# ========== DATA PROCESSING ==========
if st.session_state.initial_results:
    filtered = pd.DataFrame(st.session_state.initial_results)
    filtered = filtered[
        (filtered["Momentum_Score"] >= min_score) &
        (filtered["Trend"].isin(selected_trends)) &
        (filtered["Price"].between(*price_range)) &
        (filtered["Exchange"].isin(selected_exchanges)) &
        # Add ADX filter condition if checkbox is checked
        ((filtered["ADX"] > 25) if adx_filter else True)
    ].sort_values("Momentum_Score", ascending=False)
    
    st.session_state.filtered_results = filtered
