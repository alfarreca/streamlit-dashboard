def main():
    sheet_names = get_sheet_names(uploaded_file)

    if len(sheet_names) > 1:
        selected_sheet = st.selectbox("Select sheet to use", sheet_names, key="sheet_selector")
        st.markdown(f"<div class='sheet-selector'>Using sheet: <strong>{selected_sheet}</strong></div>", unsafe_allow_html=True)
    elif len(sheet_names) == 1:
        selected_sheet = sheet_names[0]
    else:
        selected_sheet = None

    if len(sheet_names) > 1:
        st.info(f"Available sheets: {', '.join(sheet_names)}")

    tickers_df = load_tickers_from_sheet(uploaded_file, selected_sheet)

    # --- FULL TICKERS LIST WITH TECHNICALS ---
    if tickers_df is not None and len(tickers_df) > 0:
        st.header("Full Ticker List (with latest technicals)")

        results = []
        for i, row in tickers_df.iterrows():
            ticker = row['YFinance_Symbol']
            display = row['Display_Name']
            try:
                data = load_stock_data(ticker, start_date, end_date)
                if data is not None and not data.empty:
                    data = calculate_indicators(data)
                    last = data.iloc[-1]  # last row

                    # Build dict for table row
                    result = {
                        'Symbol': row['Symbol'],
                        'Exchange': row['Exchange'],
                        'YFinance_Symbol': ticker,
                        'Display_Name': display,
                        'Date': last.name.strftime("%Y-%m-%d") if hasattr(last.name, "strftime") else str(last.name),
                        'Close': last.get('Close', None),
                        'High': last.get('High', None),
                        'Low': last.get('Low', None),
                        'Open': last.get('Open', None),
                        'Volume': last.get('Volume', None),
                        'SMA_20': last.get('SMA_20', None),
                        'SMA_50': last.get('SMA_50', None),
                        'EMA_20': last.get('EMA_20', None),
                        'RSI_14': last.get('RSI_14', None),
                        'MACD': last.get('MACD', None),
                        'MACD_Signal': last.get('MACD_Signal', None),
                        'MACD_Hist': last.get('MACD_Hist', None),
                        'BB_Upper': last.get('BB_Upper', None),
                        'BB_Lower': last.get('BB_Lower', None)
                    }
                else:
                    # If no data
                    result = {
                        'Symbol': row['Symbol'],
                        'Exchange': row['Exchange'],
                        'YFinance_Symbol': ticker,
                        'Display_Name': display,
                        'Date': None, 'Close': None, 'High': None, 'Low': None, 'Open': None, 'Volume': None,
                        'SMA_20': None, 'SMA_50': None, 'EMA_20': None, 'RSI_14': None,
                        'MACD': None, 'MACD_Signal': None, 'MACD_Hist': None, 'BB_Upper': None, 'BB_Lower': None
                    }
            except Exception as e:
                result = {
                    'Symbol': row['Symbol'],
                    'Exchange': row['Exchange'],
                    'YFinance_Symbol': ticker,
                    'Display_Name': display,
                    'Date': None, 'Close': None, 'High': None, 'Low': None, 'Open': None, 'Volume': None,
                    'SMA_20': None, 'SMA_50': None, 'EMA_20': None, 'RSI_14': None,
                    'MACD': None, 'MACD_Signal': None, 'MACD_Hist': None, 'BB_Upper': None, 'BB_Lower': None
                }
            results.append(result)

        full_df = pd.DataFrame(results)
        st.dataframe(full_df, use_container_width=True)
        csv = full_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="full_ticker_list_with_technicals.csv",
            mime="text/csv"
        )
        st.markdown("---")

    # --- SINGLE TICKER VIEW ---
    if tickers_df is not None and len(tickers_df) > 0:
        selected_display = st.selectbox("Select a ticker to analyze", tickers_df['Display_Name'])
        selected_row = tickers_df[tickers_df['Display_Name'] == selected_display].iloc[0]
        base_symbol = selected_row['YFinance_Symbol']

        stock_data = load_stock_data(base_symbol, start_date, end_date)

        if stock_data is not None:
            stock_data = calculate_indicators(stock_data)
            try:
                col1, col2, col3 = st.columns(3)
                with col1:
                    last_close = float(stock_data['Close'].iloc[-1]) if not stock_data.empty else np.nan
                    st.metric(f"{selected_display} Current Price", f"${last_close:.2f}" if not np.isnan(last_close) else "N/A")
                with col2:
                    if len(stock_data) > 1:
                        prev_close = float(stock_data['Close'].iloc[-2])
                        change = float(stock_data['Close'].iloc[-1]) - prev_close
                        pct_change = (change / prev_close) * 100
                        st.metric("Daily Change", f"${change:.2f}", f"{pct_change:.2f}%")
                    else:
                        st.metric("Daily Change", "N/A")
                with col3:
                    last_volume = int(stock_data['Volume'].iloc[-1]) if not stock_data.empty else 0
                    st.metric("Volume", f"{last_volume:,}" if last_volume > 0 else "N/A")
            except Exception as e:
                st.error(f"Error displaying metrics: {str(e)}")
            if not stock_data.empty:
                try:
                    st.subheader(f"{selected_display} Price Chart")
                    fig, ax = plt.subplots(figsize=(12, 6))
                    ax.plot(stock_data.index, stock_data['Close'], label='Close Price', color='blue')
                    if show_sma and 'SMA_20' in stock_data.columns:
                        ax.plot(stock_data.index, stock_data['SMA_20'], label='SMA 20', color='orange', alpha=0.7)
                        ax.plot(stock_data.index, stock_data['SMA_50'], label='SMA 50', color='green', alpha=0.7)
                    if show_ema and 'EMA_20' in stock_data.columns:
                        ax.plot(stock_data.index, stock_data['EMA_20'], label='EMA 20', color='purple', alpha=0.7)
                    if show_bollinger and 'BB_Upper' in stock_data.columns:
                        ax.plot(stock_data.index, stock_data['BB_Upper'], label='Upper Band', color='red', alpha=0.5, linestyle='--')
                        ax.plot(stock_data.index, stock_data['BB_Lower'], label='Lower Band', color='red', alpha=0.5, linestyle='--')
                        ax.fill_between(stock_data.index, stock_data['BB_Lower'], stock_data['BB_Upper'], color='red', alpha=0.1)
                    ax.set_title(f"{selected_display} Price Chart")
                    ax.legend()
                    ax.grid(True)
                    st.pyplot(fig)
                    if show_rsi or show_macd:
                        st.subheader("Technical Indicators")
                        cols = st.columns(2)
                        if show_rsi and 'RSI_14' in stock_data.columns:
                            with cols[0]:
                                st.markdown("**Relative Strength Index (RSI)**")
                                fig_rsi, ax_rsi = plt.subplots(figsize=(12, 3))
                                ax_rsi.plot(stock_data.index, stock_data['RSI_14'], label='RSI 14', color='blue')
                                ax_rsi.axhline(70, color='red', linestyle='--', alpha=0.5)
                                ax_rsi.axhline(30, color='green', linestyle='--', alpha=0.5)
                                ax_rsi.set_ylim(0, 100)
                                ax_rsi.legend()
                                ax_rsi.grid(True)
                                st.pyplot(fig_rsi)
                        if show_macd and 'MACD' in stock_data.columns:
                            with cols[1]:
                                st.markdown("**MACD Indicator**")
                                fig_macd, ax_macd = plt.subplots(figsize=(12, 3))
                                ax_macd.plot(stock_data.index, stock_data['MACD'], label='MACD', color='blue')
                                ax_macd.plot(stock_data.index, stock_data['MACD_Signal'], label='Signal', color='orange')
                                ax_macd.bar(stock_data.index, stock_data['MACD_Hist'], label='Histogram', color='gray', alpha=0.5)
                                ax_macd.axhline(0, color='black', linestyle='-', alpha=0.5)
                                ax_macd.legend()
                                ax_macd.grid(True)
                                st.pyplot(fig_macd)
                    st.subheader("Recent Data")
                    st.dataframe(stock_data.tail(20))
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        stock_data.to_excel(writer, sheet_name='Technical_Analysis')
                    output.seek(0)
                    st.download_button(
                        label="Download Analysis Data",
                        data=output,
                        file_name=f"{selected_display.replace('.', '_')}_analysis.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                except Exception as e:
                    st.error(f"Error plotting charts: {str(e)}")
    else:
        if uploaded_file is not None:
            st.info("Please select a valid sheet with 'Symbol' and 'Exchange' columns")
        else:
            st.info("Please upload an XLSX file with 'Symbol' and 'Exchange' columns to begin.")

if __name__ == "__main__":
    main()
