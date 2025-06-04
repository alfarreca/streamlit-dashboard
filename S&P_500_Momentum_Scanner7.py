def display_symbol_details(selected_symbol):
    if not selected_symbol:
        return
    with st.spinner(f'Loading {selected_symbol} analysis...'):
        try:
            symbol_data = st.session_state.filtered_results[
                st.session_state.filtered_results["Symbol"] == selected_symbol
            ].iloc[0]

            st.subheader(f"📊 {selected_symbol} Detailed Analysis")
            tab1, tab2, tab3 = st.tabs(["Price Chart", "Technical Indicators", "Fundamentals"])

            with tab1:
                ticker = yf.Ticker(symbol_data["YF_Symbol"])
                hist = safe_yfinance_fetch(ticker, "6mo")

                if not hist.empty:
                    st.plotly_chart(create_price_chart(hist, selected_symbol), use_container_width=True)
                else:
                    st.warning("Could not load price history for chart")

            with tab2:
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Current Price", f"${symbol_data['Price']:,.2f}")
                    st.metric("5-Day Change", f"{symbol_data['5D_Change']:.1f}%")
                    st.metric("20-Day Change", f"{symbol_data['20D_Change']:.1f}%")

                with col2:
                    st.metric("Momentum Score", symbol_data["Momentum_Score"])
                    st.metric("Trend Strength", symbol_data["Trend"])
                    st.metric("ADX", symbol_data["ADX"])

                with col3:
                    st.metric("RSI", symbol_data["RSI"])
                    st.metric("MACD Histogram", f"{symbol_data['MACD_Hist']:.3f}")
                    st.metric("Volume Ratio", f"{symbol_data['Volume_Ratio']:.2f}x")

                st.progress(symbol_data["Momentum_Score"]/100, text="Momentum Strength")
                st.progress(symbol_data["RSI"]/100, text="RSI")
                st.progress(min(symbol_data["ADX"]/50, 1.0), text="ADX Trend Strength")

            with tab3:
                try:
                    ticker = yf.Ticker(symbol_data["YF_Symbol"])
                    info = ticker.info
                    col1, col2 = st.columns(2)

                    with col1:
                        st.metric("Market Cap", f"${info.get('marketCap', 'N/A')/1e9:,.2f}B" if info.get('marketCap') else "N/A")
                        st.metric("P/E Ratio", info.get('trailingPE', 'N/A'))
                        st.metric("EPS", info.get('trailingEps', 'N/A'))
                        st.metric("Dividend Yield", f"{info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else "0%")

                    with col2:
                        st.metric("52 Week High", f"${info.get('fiftyTwoWeekHigh', 'N/A'):,.2f}")
                        st.metric("52 Week Low", f"${info.get('fiftyTwoWeekLow', 'N/A'):,.2f}")
                        st.metric("Beta", info.get('beta', 'N/A'))
                        st.metric("Average Volume", f"{info.get('averageVolume', 'N/A'):,.0f}")
                except:
                    st.warning("Could not load fundamental data for this stock")

        except Exception as e:
            st.error(f"Error loading {selected_symbol}: {str(e)}")
