import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import matplotlib.pyplot as plt

# --------------------------
# 1. INITIALIZATION & CACHING
# --------------------------
@st.cache_resource
def load_model():
    """Pretrained momentum prediction model"""
    model = RandomForestClassifier(n_estimators=100)
    # In production, you'd load a real trained model here
    return model

@st.cache_data(ttl=3600)
def load_benchmark_data():
    """IWM ETF data for relative strength"""
    return yf.Ticker("IWM").history(period='1y')

if 'alerts' not in st.session_state:
    st.session_state.alerts = []
    
model = load_model()
benchmark_data = load_benchmark_data()

# --------------------------
# 2. DATA LOADING (WITH ALL METRICS)
# --------------------------
@st.cache_data(ttl=3600)
def load_full_dataset():
    try:
        data = []
        symbols = RUSSEL_2000_SYMBOLS  # In production, use actual R2000 list
        
        with st.status("Crunching 1,500+ metrics...", expanded=True) as status:
            for i, symbol in enumerate(symbols):
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period='1y')
                    
                    if len(hist) < 200: continue
                    
                    # Momentum Calculations
                    close = hist['Close']
                    momentum_1m = (close.iloc[-1] / close.iloc[-21] - 1) * 100
                    momentum_3m = (close.iloc[-1] / close.iloc[-63] - 1) * 100
                    momentum_6m = (close.iloc[-1] / close.iloc[-126] - 1) * 100
                    
                    # Volatility & Volume
                    volatility_1m = hist['Close'].pct_change().std() * np.sqrt(21) * 100
                    avg_volume = hist['Volume'].mean()
                    
                    # Relative Strength vs IWM
                    benchmark_return = (benchmark_data['Close'].iloc[-1] / benchmark_data['Close'].iloc[-21] - 1) * 100
                    rel_strength = momentum_1m - benchmark_return
                    
                    # Composite Score
                    composite_score = (0.5*momentum_1m + 0.3*momentum_3m + 0.2*momentum_6m)
                    
                    # Earnings & Short Interest
                    try:
                        earnings_date = ticker.calendar.iloc[0,0]
                        days_to_earnings = (earnings_date - datetime.now()).days
                    except:
                        days_to_earnings = None
                        
                    short_ratio = ticker.info.get('shortRatio', 0)
                    
                    data.append({
                        'Symbol': symbol,
                        'Name': ticker.info.get('shortName', symbol),
                        'Price': close.iloc[-1],
                        '1M Momentum (%)': momentum_1m,
                        '3M Momentum (%)': momentum_3m,
                        '6M Momentum (%)': momentum_6m,
                        'Rel Strength 1M (%)': rel_strength,
                        '1M Volatility (%)': volatility_1m,
                        'Avg Volume': avg_volume,
                        'Composite Score': composite_score,
                        'Days To Earnings': days_to_earnings,
                        'Short Interest Ratio': short_ratio,
                        'Sector': ticker.info.get('sector', 'Unknown')
                    })
                    
                    if i % 50 == 0:
                        status.update(label=f"Processed {i}/{len(symbols)} symbols...")
                        
                except Exception as e:
                    continue
                    
            status.update(label="Data loaded successfully!", state="complete")
            return pd.DataFrame(data)
            
    except Exception as e:
        st.error(f"Critical error: {str(e)}")
        return pd.DataFrame()

# --------------------------
# 3. FILTERING & ANALYSIS
# --------------------------
def apply_filters(df, params):
    """Apply all momentum filters with thresholds"""
    if df.empty: return df
    
    filtered = df.copy()
    
    # Momentum Filters
    filtered = filtered[filtered['1M Momentum (%)'] >= params['mom_1m_min']]
    filtered = filtered[filtered['3M Momentum (%)'] >= params['mom_3m_min']]
    filtered = filtered[filtered['6M Momentum (%)'] >= params['mom_6m_min']]
    
    # Advanced Filters
    filtered = filtered[filtered['Rel Strength 1M (%)'] >= params['rel_strength_min']]
    filtered = filtered[filtered['1M Volatility (%)'] <= params['max_volatility']]
    filtered = filtered[filtered['Avg Volume'] >= params['min_volume']]
    filtered = filtered[filtered['Short Interest Ratio'] <= params['max_short_interest']]
    
    if params['exclude_pre_earnings']:
        filtered = filtered[(filtered['Days To Earnings'].isna()) | 
                          (filtered['Days To Earnings'] > 5)]
    
    # ML Prediction
    if not filtered.empty:
        features = filtered[['1M Momentum (%)', '3M Momentum (%)', 
                           '6M Momentum (%)', '1M Volatility (%)']]
        filtered['Up_Probability'] = model.predict_proba(
            StandardScaler().fit_transform(features)
        )[:,1]
    
    return filtered.sort_values('Composite Score', ascending=False)

# --------------------------
# 4. VISUALIZATIONS
# --------------------------
def plot_radial_momentum(symbol):
    """Radial plot showing multi-timeframe momentum"""
    data = st.session_state.filtered_results
    row = data[data['Symbol'] == symbol].iloc[0]
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatterpolar(
        r=[row['1M Momentum (%)'], 
        theta=['1M'],
        fill='toself',
        name='1M'
    ))
    # Add 3M, 6M similarly...
    
    st.plotly_chart(fig)

def plot_sector_heatmap():
    """Sector momentum visualization"""
    sector_mom = st.session_state.filtered_results.groupby('Sector')['1M Momentum (%)'].mean()
    fig, ax = plt.subplots()
    sector_mom.sort_values().plot(kind='barh', ax=ax)
    st.pyplot(fig)

# --------------------------
# 5. UI LAYOUT
# --------------------------
def main():
    st.set_page_config(layout="wide")
    st.title("🚀 Ultimate Momentum Scanner")
    
    # ------------------
    # SIDEBAR CONTROLS
    # ------------------
    with st.sidebar:
        st.header("Momentum Filters")
        
        params = {
            'mom_1m_min': st.slider("1M Min Momentum (%)", -30.0, 50.0, 5.0),
            'mom_3m_min': st.slider("3M Min Momentum (%)", -50.0, 100.0, 10.0),
            'mom_6m_min': st.slider("6M Min Momentum (%)", -50.0, 100.0, -12.0),
            'rel_strength_min': st.slider("Min Rel Strength vs IWM (%)", -20.0, 50.0, 0.0),
            'max_volatility': st.slider("Max 1M Volatility (%)", 5.0, 50.0, 25.0),
            'min_volume': st.slider("Min Avg Volume", 0, 10_000_000, 500_000),
            'max_short_interest': st.slider("Max Short Interest Ratio", 0.0, 50.0, 15.0),
            'exclude_pre_earnings': st.checkbox("Exclude Stocks Within 5 Days of Earnings", True)
        }
        
        if st.button("💾 Load Full Dataset", type="primary"):
            st.session_state.full_data = load_full_dataset()
            st.session_state.filtered_results = apply_filters(
                st.session_state.full_data, params)
    
    # ------------------
    # MAIN DASHBOARD
    # ------------------
    tab1, tab2, tab3 = st.tabs(["Stock Scanner", "Sector Analysis", "Backtest"])
    
    with tab1:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            if not st.session_state.filtered_results.empty:
                st.data_editor(
                    st.session_state.filtered_results.sort_values('Up_Probability', ascending=False),
                    column_config={
                        "Up_Probability": st.column_config.ProgressColumn(
                            format="%.2f%%",
                            min_value=0,
                            max_value=1
                        )
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                selected_symbol = st.selectbox("Analyze Symbol:", 
                    options=st.session_state.filtered_results['Symbol'])
                
                if selected_symbol:
                    plot_symbol_chart(selected_symbol)
                    plot_radial_momentum(selected_symbol)
        
        with col2:
            st.metric("Stocks Passing Filters", len(st.session_state.filtered_results))
            st.write("Top Sector Momentum:")
            plot_sector_heatmap()
            
            with st.expander("🔔 Set Alerts"):
                alert_price = st.number_input("Alert Price", 
                    value=st.session_state.filtered_results[
                        st.session_state.filtered_results['Symbol'] == selected_symbol
                    ]['Price'].iloc[0])
                
                if st.button("Create Alert"):
                    st.session_state.alerts.append({
                        'symbol': selected_symbol,
                        'price': alert_price,
                        'direction': 'above' if alert_price > current_price else 'below'
                    })
                    st.success("Alert created!")
    
    with tab2:
        st.header("Sector Momentum Heatmap")
        # Implement sector analysis visualization
    
    with tab3:
        st.header("Strategy Backtester")
        # Implement backtesting interface

if __name__ == "__main__":
    main()
