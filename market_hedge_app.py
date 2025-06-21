main_data['Strategy_Cumulative'] = (1 + main_data['Strategy_Returns'].fillna(0)).cumprod()

if main_data['Strategy_Returns'].std() > 0:
    sharpe_ratio = np.sqrt(252) * main_data['Strategy_Returns'].mean() / main_data['Strategy_Returns'].std()
else:
    sharpe_ratio = np.nan

sortino_denom = main_data[main_data['Strategy_Returns'] < 0]['Strategy_Returns'].std()
if pd.notnull(sortino_denom) and sortino_denom > 0:
    sortino_ratio = np.sqrt(252) * main_data['Strategy_Returns'].mean() / sortino_denom
else:
    sortino_ratio = np.nan

fig = px.line(
    main_data,
    y=['Cumulative', 'Strategy_Cumulative'],
    title=f"{ticker} vs. Strategy Performance",
    labels={'value': 'Growth of $1', 'variable': 'Strategy'}
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("📊 Performance Metrics")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Buy & Hold Return", f"{main_data['Cumulative'].iloc[-1]-1:.1%}")
col2.metric("Strategy Return", f"{main_data['Strategy_Cumulative'].iloc[-1]-1:.1%}")
col3.metric("Sharpe Ratio", f"{sharpe_ratio:.2f}" if not np.isnan(sharpe_ratio) else "N/A")
col4.metric("Sortino Ratio", f"{sortino_ratio:.2f}" if not np.isnan(sortino_ratio) else "N/A")

main_data['Drawdown'] = main_data['Cumulative'] / main_data['Cumulative'].cummax() - 1
main_data['Strategy_Drawdown'] = main_data['Strategy_Cumulative'] / main_data['Strategy_Cumulative'].cummax() - 1

fig_dd = px.line(main_data, y=['Drawdown', 'Strategy_Drawdown'], title="Drawdown Comparison")
st.plotly_chart(fig_dd, use_container_width=True)

csv = main_data.to_csv().encode('utf-8')
st.download_button("📥 Download Results CSV", csv, "results.csv")
