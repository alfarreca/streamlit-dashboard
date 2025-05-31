# In the sidebar controls section (around line 150 in the full script), replace with:

with st.sidebar:
    st.header("Momentum Filters")
    
    # Relative Strength Filter (exactly as shown in screenshot)
    rel_strength_min = st.slider(
        "Min Rel Strength (%)",
        min_value=-20.0,
        max_value=30.0,
        value=0.0,
        step=0.1,
        help="Minimum relative strength compared to benchmark"
    )
    
    # Volatility Filter (exactly as shown in screenshot)
    max_volatility = st.slider(
        "Max Volatility (%)",
        min_value=5.0,
        max_value=50.0,
        value=30.0,
        step=0.1,
        help="Maximum allowed volatility"
    )
    
    # Volume Filter (exactly as shown in screenshot)
    min_volume = st.slider(
        "Min Avg Volume",
        min_value=0,
        max_value=10_000_000,
        value=500_000,
        step=100_000,
        help="Minimum average trading volume"
    )
    
    # MA Crossover Filter (exactly as shown in screenshot)
    ma_filter = st.selectbox(
        "MA Crossover",
        options=['All', 'Golden Cross', 'Death Cross'],
        index=0,
        help="Filter by moving average crossover status"
    )
    
    if st.button("🔄 Load/Refresh Data", type="primary"):
        with st.spinner("Loading market data..."):
            st.session_state.full_data = load_full_dataset()
            st.session_state.filtered_results = apply_filters(
                st.session_state.full_data,
                {
                    'rel_strength_min': rel_strength_min,
                    'max_volatility': max_volatility,
                    'min_volume': min_volume,
                    'ma_filter': ma_filter
                }
            )
            st.toast("Data loaded successfully!", icon="✅")
