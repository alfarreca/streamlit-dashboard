def apply_filters(df, params):
    """Apply all filters based on user parameters"""
    if df.empty:
        return df
    
    filtered = df.copy()
    
    # Apply momentum timeframe filters
    if 'mom_1m_min' in params:
        filtered = filtered[filtered['1M Momentum (%)'] >= params['mom_1m_min']]
    if 'mom_3m_min' in params:
        filtered = filtered[filtered['3M Momentum (%)'] >= params['mom_3m_min']]
    if 'mom_6m_min' in params:
        filtered = filtered[filtered['6M Momentum (%)'] >= params['mom_6m_min']]
    
    # Apply other filters
    if 'rel_strength_min' in params:
        filtered = filtered[filtered['Rel Strength (%)'] >= params['rel_strength_min']]
    if 'max_volatility' in params:
        filtered = filtered[filtered['Volatility (%)'] <= params['max_volatility']]
    if 'min_volume' in params:
        filtered = filtered[filtered['Avg Volume'] >= params['min_volume']]
    if 'ma_filter' in params and params['ma_filter'] != 'All':
        filtered = filtered[filtered['MA_Status'] == params['ma_filter']]
    
    return filtered.sort_values('1M Momentum (%)', ascending=False)
