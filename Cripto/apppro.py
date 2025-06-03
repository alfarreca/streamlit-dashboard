if not filtered_tokens.empty:
    cols = st.columns(3)
    for i, (_, row) in enumerate(filtered_tokens.iterrows()):
        with cols[i % 3]:
            logo = fetch_token_logo(row["Token"])
            if logo:
                st.image(logo, width=40)
            st.write(f"**{row['Name']} ({row['Token']})**")
            st.write(f"Market Cap: ${row['Market Cap (B)']:.2f}B")
            st.write(f"Focus: {row['Focus']}")
            st.write(f"TVL: ${row['TVL (B)']:.1f}B")
            st.write(f"Composability: {row['Composability']}")
            st.markdown("---")
    # Token metrics table
    st.subheader("Token Metrics Comparison")
    st.dataframe(
        filtered_tokens.drop(columns=["Focus"]),
        use_container_width=True,
        hide_index=True
    )
else:
    st.warning("No tokens match your selected filters.")
