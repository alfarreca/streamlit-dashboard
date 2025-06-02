import streamlit as st
import pandas as pd
import numpy as np

def main():
    st.set_page_config(page_title="Silver Watchlist", layout="wide")
    
    # Custom CSS for styling
    st.markdown("""
    <style>
        .header-style {
            font-size: 24px;
            font-weight: bold;
            color: #4682B4;
            margin-bottom: 20px;
        }
        .subheader-style {
            font-size: 18px;
            font-weight: bold;
            color: #4682B4;
            margin-top: 20px;
            margin-bottom: 10px;
        }
        .dataframe {
            width: 100%;
        }
        .positive-change {
            color: green;
        }
        .negative-change {
            color: red;
        }
        .info-box {
            background-color: #f0f2f6;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="header-style">Silver Investment Watchlist</div>', unsafe_allow_html=True)
    
    # Create the watchlist dataframe
    data = {
        "Asset": [
            "Silver Spot", "Gold Spot", "iShares Silver ETF", "Sprott Physical Silver Trust",
            "Global X Silver Miners ETF", "Wheaton Precious Metals", "First Majestic Silver",
            "Pan American Silver", "Hecla Mining", "Gold Miners ETF"
        ],
        "Type": [
            "Commodity", "Commodity", "ETF", "Closed-End Fund", "ETF", 
            "Silver Streaming Stock", "Silver Miner", "Silver Miner", "Silver Miner", "ETF"
        ],
        "Ticker": [
            "CURRENCY:XAGUSD", "CURRENCY:XAUUSD", "SLV", "PSLV", "SIL", 
            "WPM", "AG", "PAAS", "HL", "GDX"
        ],
        "Live Price": [
            32.46, 3374.57, 31.29, 11.48, 45.62, 
            90.34, 6.83, 25.99, 5.65, 53.39
        ],
        "52W High": [
            34.83, 3430.21, 31.74, 11.73, 43.15, 
            86.75, 7.94, 28.02, 7.53, 51.91
        ],
        "52W Low": [
            26.6525, 2292.71, 24.33, 9.17, 29.58, 
            52.04, 4.62, 18.58, 4.54, 33.15
        ],
        "1Y Change (%)": [
            0.1548, 0.4181, 0.1219, 0.1135, 0.3370, 
            0.6402, -0.0367, 0.1971, -0.0325, 0.5035
        ],
        "Gold/Silver Ratio": [
            103.96, np.nan, np.nan, np.nan, np.nan, 
            np.nan, np.nan, np.nan, np.nan, np.nan
        ],
        "52W High Gold/Silver Ratio": [
            112.7993, np.nan, np.nan, np.nan, np.nan, 
            np.nan, np.nan, np.nan, np.nan, np.nan
        ],
        "52W Low Gold/Silver Ratio": [
            73.1471, np.nan, np.nan, np.nan, np.nan, 
            np.nan, np.nan, np.nan, np.nan, np.nan
        ],
        "Gold/Silver Ratio1Y Change (%)": [
            0.253, np.nan, np.nan, np.nan, np.nan, 
            np.nan, np.nan, np.nan, np.nan, np.nan
        ]
    }
    
    df = pd.DataFrame(data)
    
    # Add current price vs 52W high/low indicators
    df['Current vs 52W High'] = (df['Live Price'] / df['52W High'] - 1) * 100
    df['Current vs 52W Low'] = (df['Live Price'] / df['52W Low'] - 1) * 100
    
    # Format percentages
    percentage_cols = ['1Y Change (%)', 'Current vs 52W High', 'Current vs 52W Low', 
                      'Gold/Silver Ratio1Y Change (%)']
    for col in percentage_cols:
        df[col] = df[col].apply(lambda x: f"{x:.2%}" if pd.notnull(x) else "")
    
    # Display the main dataframe
    st.markdown('<div class="subheader-style">Silver Investment Vehicles</div>', unsafe_allow_html=True)
    
    # Add filters
    col1, col2, col3 = st.columns(3)
    with col1:
        asset_type = st.multiselect("Filter by Type", options=df['Type'].unique(), default=df['Type'].unique())
    with col2:
        price_range = st.slider("Filter by Live Price Range", 
                              min_value=float(df['Live Price'].min()), 
                              max_value=float(df['Live Price'].max()), 
                              value=(float(df['Live Price'].min()), float(df['Live Price'].max())))
    with col3:
        sort_by = st.selectbox("Sort By", options=df.columns[3:], index=3)
        sort_order = st.radio("Sort Order", ["Ascending", "Descending"], horizontal=True)
    
    # Apply filters
    filtered_df = df[df['Type'].isin(asset_type)]
    filtered_df = filtered_df[(filtered_df['Live Price'] >= price_range[0]) & 
                            (filtered_df['Live Price'] <= price_range[1])]
    
    # Apply sorting
    filtered_df = filtered_df.sort_values(by=sort_by, ascending=(sort_order == "Ascending"))
    
    # Display the filtered and sorted dataframe
    st.dataframe(
        filtered_df.style.applymap(
            lambda x: 'color: green' if isinstance(x, str) and '%' in x and float(x.strip('%')) > 0 
            else ('color: red' if isinstance(x, str) and '%' in x and float(x.strip('%')) < 0 
            else '', 
            subset=percentage_cols
        ),
        use_container_width=True
    )
    
    # Key metrics section
    st.markdown('<div class="subheader-style">Key Silver Market Metrics</div>', unsafe_allow_html=True)
    
    # Calculate key metrics
    current_ratio = df.loc[0, 'Gold/Silver Ratio']
    ratio_high = df.loc[0, '52W High Gold/Silver Ratio']
    ratio_low = df.loc[0, '52W Low Gold/Silver Ratio']
    ratio_change = df.loc[0, 'Gold/Silver Ratio1Y Change (%)']
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Current Gold/Silver Ratio", f"{current_ratio:.2f}", 
                 f"{ratio_change} YoY", delta_color="inverse")
    with col2:
        st.metric("52-Week High Ratio", f"{ratio_high:.2f}", 
                 f"{(ratio_high - current_ratio):.2f} above current")
    with col3:
        st.metric("52-Week Low Ratio", f"{ratio_low:.2f}", 
                 f"{(current_ratio - ratio_low):.2f} below current")
    
    # Insights from the Notes sheet
    st.markdown('<div class="subheader-style">Market Insights</div>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="info-box">
        <strong>Insight 1 (Sound):</strong><br>
        The gold/silver ratio near 100 is well above its long-term average (~70–80), signaling silver is relatively 
        undervalued versus gold. A tilt toward physical silver or low-fee silver ETFs (e.g. SLV, PSLV) when the 
        ratio exceeds 100 can capture mean-reversion.
    </div>
    
    <div class="info-box">
        <strong>Insight 2 (Contra-intuitive):</strong><br>
        Rather than boosting pure silver exposure, overweighting high-quality silver miners (e.g. WPM, SIL) could 
        actually deliver better leveraged returns—miners often outperform the metal during rallies and offer 
        optionality on operational improvements, dividends and M&A upside that bullion cannot.
    </div>
    """, unsafe_allow_html=True)
    
    # Price performance visualization
    st.markdown('<div class="subheader-style">Price Performance Analysis</div>', unsafe_allow_html=True)
    
    chart_data = filtered_df[['Asset', 'Live Price', '52W High', '52W Low']].melt(
        id_vars='Asset', var_name='Metric', value_name='Price'
    )
    
    st.bar_chart(
        chart_data,
        x='Asset',
        y='Price',
        color='Metric',
        use_container_width=True
    )
    
    # Add some space at the bottom
    st.markdown("<br><br>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
