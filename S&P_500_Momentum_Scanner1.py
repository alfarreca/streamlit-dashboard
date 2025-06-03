import streamlit as st
import pandas as pd

st.title("S&P 500 Momentum Scanner")

# ========== DATA LOADING ==========

st.sidebar.header("Data Upload")
upload = st.sidebar.file_uploader(
    "Upload your S&P 500 data (.csv or .xlsx)", 
    type=["csv", "xlsx"]
)

# Helper function to read uploaded file
def load_data(file):
    try:
        if file.name.endswith(".csv"):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        return df
    except Exception as e:
        st.error(f"Error loading file: {e}")
        return pd.DataFrame()

# Store initial results in session state
if upload:
    df = load_data(upload)
    if not df.empty:
        st.session_state["initial_results"] = df.to_dict(orient="records")
        st.success("Data loaded successfully!")
    else:
        st.session_state["initial_results"] = []
elif "initial_results" not in st.session_state:
    st.session_state["initial_results"] = []

# ========== FILTERS ==========

if st.session_state["initial_results"]:
    df = pd.DataFrame(st.session_state["initial_results"])
    with st.sidebar:
        st.header("Momentum Filters")
        min_score = st.slider("Minimum Momentum Score", 0, 100, 70, 5)
        trend_options = ["↑ Strong", "↑ Medium", "↗ Weak"]
        selected_trends = st.multiselect("Trend Strength", options=trend_options, default=trend_options)
        price_range = st.slider("Price Range ($)", 0.0, 500.0, (10.0, 200.0), 5.0)
        # Robustly handle missing Exchange column
        if "Exchange" in df.columns:
            exchange_options = df["Exchange"].dropna().unique()
            default_exchanges = [ex for ex in ["NASDAQ", "NYSE"] if ex in exchange_options]
            selected_exchanges = st.multiselect("Exchanges", options=exchange_options, default=default_exchanges)
        else:
            exchange_options = []
            selected_exchanges = []
        # Robustly handle missing ADX column
        adx_filter = st.checkbox("Only show ADX > 25 (Strong Trends)", value=False) \
            if "ADX" in df.columns else False
else:
    st.sidebar.info("No data available for filtering. Please upload a file first.")
    min_score = 70
    trend_options = ["↑ Strong", "↑ Medium", "↗ Weak"]
    selected_trends = trend_options
    price_range = (10.0, 200.0)
    selected_exchanges = []
    adx_filter = False

# ========== DATA PROCESSING ==========

if st.session_state["initial_results"]:
    filtered = pd.DataFrame(st.session_state["initial_results"])
    try:
        filter_mask = (
            (filtered["Momentum_Score"] >= min_score if "Momentum_Score" in filtered.columns else True) &
            (filtered["Trend"].isin(selected_trends) if "Trend" in filtered.columns else True) &
            (filtered["Price"].between(*price_range) if "Price" in filtered.columns else True) &
            (filtered["Exchange"].isin(selected_exchanges) if "Exchange" in filtered.columns and selected_exchanges else True)
        )
        if adx_filter and "ADX" in filtered.columns:
            filter_mask &= (filtered["ADX"] > 25)
        filtered = filtered[filter_mask]
        filtered = filtered.sort_values("Momentum_Score", ascending=False) if "Momentum_Score" in filtered.columns else filtered
        st.session_state["filtered_results"] = filtered
    except Exception as e:
        st.error(f"Error during filtering: {e}")
        filtered = pd.DataFrame()
        st.session_state["filtered_results"] = filtered
else:
    filtered = pd.DataFrame()
    st.session_state["filtered_results"] = filtered

# ========== DISPLAY RESULTS ==========

st.header("Filtered Results")
if not filtered.empty:
    st.dataframe(filtered)
else:
    st.write("No data to display. Please upload and filter your data.")

# ========== DOWNLOAD FILTERED DATA ==========

if not filtered.empty:
    csv = filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download Filtered Results as CSV",
        csv,
        "filtered_results.csv",
        "text/csv",
        key="download-csv"
    )
