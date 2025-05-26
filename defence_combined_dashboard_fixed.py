elif page == "Overview":
    st.markdown("## 🗂️ Overview")
    default_text = "ETR:RHM STO:SAAB-B EPA:HO LON:BA BIT:LDO"

    user_text = st.text_input("Enter tickers (space or comma separated)", default_text)
    if st.button("Load Tickers"):
        st.session_state["tickers"] = split_tickers(user_text)

    tickers = st.session_state.get("tickers", split_tickers(default_text))
    show_tbl = st.checkbox("✅ Show full metrics table", True)

    fund_df = fetch_fundamentals(tickers)
    tech_df = pd.DataFrame({t: technicals(fetch_weekly_ohlcv(t)) for t in tickers}).T
    combined = pd.concat([tech_df, fund_df], axis=1).round(2)

    if show_tbl:
        st.markdown("### 📊 All Metrics")
        st.dataframe(combined, use_container_width=True)

        csv = combined.to_csv().encode("utf-8")
        st.download_button(
            label="📥 Download metrics as CSV",
            data=csv,
            file_name="defense_metrics.csv",
            mime="text/csv",
        )
