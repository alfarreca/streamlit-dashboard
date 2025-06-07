import streamlit as st
import pandas as pd
import plotly.express as px

# --- Page Config ---
st.set_page_config(
    page_title="Stock Performance vs. Dollar Strength",
    page_icon="💵",
    layout="wide"
)

# --- Title & Intro ---
st.title("📊 How Stocks Perform When the Dollar Weakens or Strengthens")
st.markdown("""
*Based on 40 years of historical data (WSJ 2025 analysis).*  
*Use this tool to adjust your portfolio based on USD trends.*
""")

# --- Data (Mocked, but based on article) ---
data = {
    "Asset Class": [
        "International Stocks", "Emerging Market Stocks", "U.S. Large-Caps", 
        "Bonds (Avg. Fund)", "U.S. Small-Caps", "U.S. Value Stocks", 
        "Commodity Stocks"
    ],
    "Return (Dollar Weakens)": [2.57, 2.20, 1.65, 0.71, 0.50, 1.10, -0.30],
    "Return (Dollar Strengthens)": [0.16, 0.10, 1.09, 0.24, 1.16, 0.90, -0.94],
    "Risk (Volatility)": ["Medium", "High", "Low", "Low", "High", "Medium", "High"]
}

df = pd.DataFrame(data)

# --- Sidebar Filters ---
st.sidebar.header("Filters")
dollar_trend = st.sidebar.radio(
    "Select Dollar Trend:",
    ["Weakens", "Strengthens"]
)

# --- Dynamic Data Filtering ---
if dollar_trend == "Weakens":
    df_filtered = df[["Asset Class", "Return (Dollar Weakens)", "Risk (Volatility)"]]
    df_filtered = df_filtered.rename(columns={"Return (Dollar Weakens)": "Avg. Monthly Return (%)"})
    best_assets = ["International Stocks", "Emerging Market Stocks", "U.S. Large-Caps"]
else:
    df_filtered = df[["Asset Class", "Return (Dollar Strengthens)", "Risk (Volatility)"]]
    df_filtered = df_filtered.rename(columns={"Return (Dollar Strengthens)": "Avg. Monthly Return (%)"})
    best_assets = ["U.S. Small-Caps", "U.S. Value Stocks"]

# --- Highlight Best Assets ---
def highlight_best(row):
    if row["Asset Class"] in best_assets:
        return ["background-color: #e6f7ff"] * len(row)
    elif row["Avg. Monthly Return (%)"] < 0:
        return ["background-color: #ffcccc"] * len(row)
    else:
        return [""] * len(row)

styled_df = df_filtered.style.apply(highlight_best, axis=1)

# --- Main Layout ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader(f"Performance When Dollar **{dollar_trend}**")
    st.dataframe(styled_df, use_container_width=True, hide_index=True)

with col2:
    st.subheader("📈 Best Assets to Hold")
    st.markdown(f"""
    - **{dollar_trend}?** Prioritize:  
      {', '.join(f'**{x}**' for x in best_assets)}  
    - **Avoid:**  
      {"Commodity Stocks" if dollar_trend == "Strengthens" else "U.S. Small-Caps"}
    """)

# --- Plotly Chart ---
fig = px.bar(
    df_filtered,
    x="Asset Class",
    y="Avg. Monthly Return (%)",
    color="Risk (Volatility)",
    title=f"Asset Returns When Dollar {dollar_trend} (%)",
    color_discrete_map={"Low": "#4CAF50", "Medium": "#FFC107", "High": "#F44336"}
)
st.plotly_chart(fig, use_container_width=True)

# --- Key Takeaways ---
st.subheader("🎯 Key Takeaways")
st.markdown("""
- **Dollar Weakens?**  
  → International stocks (+2.57%) and bonds outperform.  
- **Dollar Strengthens?**  
  → U.S. small-caps (+1.16%) shine; avoid commodities (-0.94%).  
- *Source: [WSJ (June 2025)](https://www.wsj.com/finance/investing/dollar-stocks-impact-40-years-data)*  
""")

# --- Footer ---
st.caption("App by [Your Name] | Data simulated for illustration.")
