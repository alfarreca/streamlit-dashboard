metrics = []
progress_bar = st.progress(0)
for i, symbol in enumerate(tickers):
    try:
        df = get_stock_data(symbol, lookback_days)
        if df.empty or not {'High', 'Low', 'Close', 'Volume'}.issubset(df.columns):
            raise ValueError("No data or missing columns.")
        latest_close = float(df['Close'].iloc[-1])
        avg_volume = float(df['Volume'].mean())
        normalized_vol = avg_volume / 1e6
        volume_pct = avg_volume / max(df['Volume'].max(), 1)
        atr = calculate_atr(df, lookback_days)
        atr_pct = atr / latest_close if latest_close else 0
        call_put_ratio, total_opt_activity = get_options_flow(symbol)
        r1, r2, r3, s1, s2, s3 = calculate_levels(
            latest_close, normalized_vol, call_put_ratio, atr, volume_pct, atr_pct, k1, k2, k3
        )
        metrics.append({
            "Symbol": symbol,
            "Last Price": latest_close,
            "Avg Volume (M)": normalized_vol,
            "ATR": atr,
            "ATR %": atr_pct*100,
            "Vol% of Max": volume_pct*100,
            "R1": r1, "R2": r2, "R3": r3,
            "S1": s1, "S2": s2, "S3": s3,
            "Call/Put Ratio": call_put_ratio,
            "Total Options Volume": total_opt_activity
        })
    except Exception as e:
        metrics.append({
            "Symbol": symbol,
            "Last Price": np.nan,
            "Avg Volume (M)": np.nan,
            "ATR": np.nan,
            "ATR %": np.nan,
            "Vol% of Max": np.nan,
            "R1": np.nan, "R2": np.nan, "R3": np.nan,
            "S1": np.nan, "S2": np.nan, "S3": np.nan,
            "Call/Put Ratio": np.nan,
            "Total Options Volume": np.nan
        })
    progress_bar.progress((i+1)/len(tickers))
