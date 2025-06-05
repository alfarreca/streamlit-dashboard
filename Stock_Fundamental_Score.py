import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import time

SCORE_WEIGHTS = {
    'pe_ratio': 0.2,
    'peg_ratio': 0.25,
    'debt_to_equity': -0.15,
    'current_ratio': 0.1,
    'return_on_equity': 0.15,
    'profit_margin': 0.15
}

@st.cache_data(ttl=3600)
def get_tickers_from_excel(uploaded_file):
    df = pd.read_excel(uploaded_file)
    # Assumes tickers are in first column
    tickers = df.iloc[:, 0].dropna().astype(str).str.strip().tolist()
    return tickers

@st.cache_data(ttl=3600)
def get_fundamentals(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info
    fundamentals = {
        'ticker': ticker,
        'pe_ratio': info.get('trailingPE'),
        'peg_ratio': info.get('pegRatio'),
        'debt_to_equity': info.get('debtToEquity'),
        'current_ratio': info.get('currentRatio'),
        'return_on_equity': info.get('returnOnEquity'),
        'profit_margin': info.get('profitMargins'),
        'company_name': info.get('shortName', ticker),
        'sector': info.get('sector', 'N/A'),
        'industry': info.get('industry', 'N/A'),
        'market_cap': info.get('marketCap')
    }
    hist = stock.history(period="1d")
    fundamentals['price'] = hist['Close'].iloc[-1] if not hist.empty else None
    return fundamentals

def normalize_value(value, min_val, max_val, reverse=False):
    if value is None or min_val is None or max_val is None:
        return 0
    if min_val == max_val:
        return 0.5
    normalized = (value - min_val) / (max_val - min_val)
    return 1 - normalized if reverse else normalized

def calculate_scores(fundamentals_list):
    if not fundamentals_list:
        return []
    df = pd.DataFrame(fundamentals_list)
    metrics = {metric: {
        'min': df[metric].min(),
        'max': df[metric].max(),
        'reverse': metric in ['pe_ratio', 'peg_ratio', 'debt_to_equity']
    } for metric in SCORE_WEIGHTS}
    for metric, params in metrics.items():
        df[f'{metric}_score'] = df[metric].apply(
            lambda x: normalize_value(x, params['min'], params['max'], params['reverse']) * SCORE_WEIGHTS[metric]
        )
    df['total_score'] = df[[f'{m}_score' for m in SCORE_WEIGHTS]].sum(axis=1)
    min_score, max_score = df['total_score'].min(), df['total_score'].max()
    df['normalized_score'] = df['total_score'].apply(
        lambda x: ((x - min_score) / (max_score - min_score)) * 100 if max_score != min_score else 50
    )
    return df.to_dict('records')

def display_results(results):
    if not results:
        st.warning("No results to display")
        return
    df = pd.DataFrame(results).sort_values('normalized_score', ascending=False)
    df['market_cap'] = df['market_cap'].apply(lambda x: f"${x/1e9:.2f}B" if pd.notnull(x) else "N/A")
    df['price'] = df['price'].apply(lambda x: f"${x:.2f}" if pd.notnull(x) else "N/A")
    st.columns(3)[0].metric("Total Stocks", len(df))
    st.columns(3)[1].metric("Highest Score", f"{df['normalized_score'].max():.1f}")
    st.columns(3)[2].metric("Average Score", f"{df['normalized_score'].mean():.1f}")
    min_score = st.slider("Minimum Score", 0, 100, 0)
    sectors = st.multiselect("Filter by Sector", df['sector'].unique(), df['sector'].unique())
    filtered_df = df[(df['normalized_score'] >= min_score) & (df['sector'].isin(sectors))]
    st.dataframe(filtered_df[['ticker', 'company_name', 'sector', 'normalized_score', 'price', 'market_cap']].rename(columns={
        'ticker': 'Ticker', 'company_name': 'Company', 'sector': 'Sector', 'normalized_score': 'Score',
        'price': 'Price', 'market_cap': 'Market Cap'
    }), use_container_width=True)
    csv = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button("Download CSV", csv, f"scores_{datetime.now().strftime('%Y%m%d')}.csv")
    if len(filtered_df) == 0:
        return

    tickers_list = filtered_df['ticker'].tolist()
    # Sticky selectbox logic
    if ('selected_ticker' not in st.session_state) or (st.session_state.selected_ticker not in tickers_list):
        if tickers_list:
            st.session_state.selected_ticker = tickers_list[0]
        else:
            st.session_state.selected_ticker = ""

    selected_ticker = st.selectbox(
        "Select stock for details",
        tickers_list,
        index=tickers_list.index(st.session_state.selected_ticker) if st.session_state.selected_ticker in tickers_list else 0,
        key="selected_ticker"
    )

    selected_stock = df[df['ticker'] == selected_ticker].iloc[0]
    col1, col2 = st.columns(2)
    col1.metric("Company", selected_stock['company_name'])
    col1.metric("Sector", selected_stock['sector'])
    col1.metric("Price", selected_stock['price'])
    col2.metric("Fundamental Score", f"{selected_stock['normalized_score']:.1f}")
    col2.metric("P/E Ratio", selected_stock['pe_ratio'])
    col2.metric("PEG Ratio", selected_stock['peg_ratio'])

def main():
    st.set_page_config(page_title="Stock Analyzer", layout="wide")
    st.title("📈 S&P 500 Fundamental Analysis")

    uploaded_file = st.file_uploader("Upload your S&P 500 Excel (.xlsx) file", type=["xlsx"])

    if uploaded_file is not None:
        # Only load tickers if new file or not yet loaded
        if "tickers" not in st.session_state or st.session_state.uploaded_file_name != uploaded_file.name:
            tickers = get_tickers_from_excel(uploaded_file)
            st.session_state.tickers = tickers
            st.session_state.uploaded_file_name = uploaded_file.name
            st.session_state.results = None  # Clear old results if new file
        else:
            tickers = st.session_state.tickers

        st.success(f"Loaded {len(tickers)} tickers from file")

        if st.button("Analyze Stocks"):
            # Only calculate if not already done or new file uploaded
            with st.spinner("Fetching data and calculating scores..."):
                data = []
                progress = st.progress(0)
                for i, t in enumerate(tickers):
                    data.append(get_fundamentals(t))
                    progress.progress((i + 1) / len(tickers))
                    time.sleep(0.1)
                progress.empty()
                results = calculate_scores(data)
                st.session_state.results = results

        # If results are in session_state, display them
        if st.session_state.get("results") is not None:
            display_results(st.session_state.results)
    else:
        st.info("Please upload an Excel file with tickers in the first column.")

if __name__ == '__main__':
    main()
