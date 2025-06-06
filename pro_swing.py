def scan_universe(universe, period='6mo'):
    results = []
    
    with st.spinner(f"Scanning {len(universe)} stocks..."):
        progress_bar = st.progress(0)
        
        for i, ticker in enumerate(universe):
            try:
                data = get_stock_data(ticker, period)
                if not data.empty:
                    score = calculate_opportunity_score(data)
                    strategy = generate_strategy(data)
                    
                    # Ensure all required fields are present
                    if score is not None and strategy is not None:
                        results.append({
                            'Ticker': ticker,
                            'Score': score,
                            'Price': data['Close'].iloc[-1],
                            'Change %': (data['Close'].iloc[-1] / data['Close'].iloc[-2] - 1) * 100,
                            'Volume': data['Volume'].iloc[-1],
                            'RSI': data.get('momentum_rsi', float('nan')).iloc[-1],
                            'MACD': data.get('trend_macd_diff', float('nan')).iloc[-1],
                            'BB %': data.get('volatility_bbp', float('nan')).iloc[-1] * 100,
                            'Strategy': strategy
                        })
            except Exception as e:
                st.warning(f"Error processing {ticker}: {str(e)}")
                continue
            
            progress_bar.progress((i + 1) / len(universe))
    
    # Return empty DataFrame if no results, or DataFrame with guaranteed 'Score' column
    if not results:
        return pd.DataFrame(columns=['Ticker', 'Score', 'Price', 'Change %', 'Volume', 'RSI', 'MACD', 'BB %', 'Strategy'])
    
    return pd.DataFrame(results).sort_values('Score', ascending=False)
