import streamlit as st
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Configurable constant ---
MAX_WORKERS = 8  # Adjust as needed

# --- PLACEHOLDER FUNCTION DEFINITIONS ---
def get_google_sheet_data():
    # TODO: Replace with your code to fetch data from Google Sheets.
    # Must return a pandas DataFrame with columns: Symbol, Exchange, etc.
    return pd.DataFrame([
        {"Symbol": "AAPL", "Exchange": "NASDAQ"},
        {"Symbol": "MSFT", "Exchange": "NASDAQ"},
        {"Symbol": "GOOGL", "Exchange": "NASDAQ"}
    ])

def map_to_yfinance_symbol(symbol, exchange):
    # TODO: Implement your mapping logic
    return symbol

def get_ticker_data(symbol, exchange, yf_symbol):
    # TODO: Replace with your actual data fetching logic
    # Must return a dictionary with at least Symbol, Exchange, Momentum_Score
    return {"Symbol": symbol, "Exchange": exchange, "Momentum_Score": 75}

def display_results(filtered_df):
    st.subheader("Momentum Results")
    st.dataframe(filtered_df)

def display_symbol_details(symbol):
    st.subheader(f"Details for: {symbol}")
    st.write("...")  # Replace with your custom details

# --- MAIN APP LOGIC ---
def main():
    st.set_page_config(page_title="S&P 500 Momentum Scanner", layout="wide")
    st.title("S&P 500 Momentum Scanner")

    try:
        df = get_google_sheet_data()
    except Exception as e:
        st.error(f"Error loading Google Sheet data: {e}")
        return

    if df.empty:
        st.warning("No data loaded from Google Sheets.")
        return

    try:
        df["YF_Symbol"] = df.apply(
            lambda row: map_to_yfinance_symbol(row["Symbol"], row["Exchange"]), axis=1
        )
    except Exception as e:
        st.error(f"Error mapping yfinance symbols: {e}")
        return

    exchanges = sorted(df["Exchange"].unique().tolist())
    selected_exchange = st.sidebar.selectbox("Exchange", ["All"] + exchanges)
    min_score = st.sidebar.slider("Min Momentum Score", 0, 100, 50)

    ticker_data = []
    progress = st.progress(0, text="Fetching ticker data...")
    total = len(df)
    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [
                executor.submit(get_ticker_data, row["Symbol"], row["Exchange"], row["YF_Symbol"])
                for _, row in df.iterrows()
            ]
            for i, f in enumerate(as_completed(futures)):
                data = f.result()
                if data:
                    ticker_data.append(data)
                progress.progress((i + 1) / total, text=f"Processed {i+1}/{total} tickers")
    except Exception as e:
        st.error(f"Error processing ticker data: {e}")
        return
    progress.empty()

    results_df = pd.DataFrame(ticker_data)
    st.session_state["raw_results_df"] = results_df.copy()

    # --- Filtering logic ---
    if not results_df.empty:
        results_df = results_df.reset_index(drop=True)
        if selected_exchange != "All":
            filtered = results_df[
                (results_df["Momentum_Score"] >= min_score) &
                (results_df["Exchange"] == selected_exchange)
            ].copy()
        else:
            filtered = results_df[results_df["Momentum_Score"] >= min_score].copy()
    else:
        filtered = pd.DataFrame()

    st.session_state.filtered_results = filtered
    display_results(filtered)

    # --- Symbol selection and details ---
    if not filtered.empty:
        symbols = filtered["Symbol"].tolist()
        # Only set the default before the widget, never after!
        if (
            "selected_symbol" not in st.session_state
            or st.session_state.selected_symbol not in symbols
        ):
            st.session_state.selected_symbol = symbols[0] if symbols else None

        selected = st.selectbox(
            "Select a symbol for details",
            symbols,
            index=symbols.index(st.session_state.selected_symbol) if st.session_state.selected_symbol in symbols else 0,
            key="selected_symbol"
        )

        # Do NOT assign to st.session_state.selected_symbol after the selectbox!
        # Use the value directly for downstream processing
        if st.session_state.selected_symbol:
            display_symbol_details(st.session_state.selected_symbol)

# --- ENSURE THE APP RUNS ---
if __name__ == "__main__":
    main()
