import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import time

SCORE_WEIGHTS = {
    'pe_ratio': 0.15,
    'peg_ratio': 0.15,
    'debt_to_equity': -0.1,
    'current_ratio': 0.05,
    'return_on_equity': 0.1,
    'profit_margin': 0.1,
    'dividend_yield': 0.05,
    'eps': 0.1,
    'revenue': 0.1,
    'free_cash_flow': 0.1,
    'ebitda': 0.05,
    'gross_margin': 0.05
}

EXTRA_METRICS = [
    'dividend_yield', 'eps', 'revenue', 'free_cash_flow', 'ebitda', 'gross_margin'
]

EXTRA_METRICS_LABELS = {
    'dividend_yield': 'Dividend Yield',
    'eps': 'EPS (TTM)',
    'revenue': 'Revenue',
    'free_cash_flow': 'Free Cash Flow',
    'ebitda': 'EBITDA',
    'gross_margin': 'Gross Margin'
}

@st.cache_data(ttl=3600)
def get_tickers_from_excel(uploaded_file):
    df = pd.read_excel(uploaded_file)
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
        'market_cap': info.get('marketCap'),
        'dividend_yield': info.get('dividendYield'),
        'eps': info.get('trailingEps'),
        'revenue': info.get('totalRevenue'),
        'free_cash_flow': info.get('freeCashflow'),
        'ebitda': info.get('ebitda'),
        'gross_margin': info.get('grossMargins'),
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
        'reverse': SCORE_WEIGHTS[metric] < 0
    } for metric in SCORE_WEIGHTS}
    for metric, params in metrics.items():
        df[f'{metric}_score'] = df[metric].apply(
            lambda x: normalize_value(x, params['min'], params['max'], params['reverse']) * abs(SCORE_WEIGHTS[metric])
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

    # Show extra metrics in main table
    st.dataframe(
        filtered_df[['ticker', 'company_name', 'sector', 'normalized_score', 'price', 'market_cap'] + EXTRA_METRICS]
        .rename(columns={
            'ticker': 'Ticker',
            'company_name': 'Company',
            'sector': 'Sector',
            'normalized_score': 'Score',
            'price': 'Price',
            'market_cap': 'Market Cap',
            **EXTRA_METRICS_LABELS
        }),
        use_container_width=True
    )

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

    # --- Sector averages for extra metrics ---
    sector_df = df[df['sector'] == selected_stock['sector']]
    st.markdown("### Company Details")
    col1, col2 = st.columns(2)
    col1.metric("Company", selected_stock['company_name'])
    col1.metric("Sector", selected_stock['sector'])
    col1.metric("Price", selected_stock['price'])
    col2.metric("Fundamental Score", f"{selected_stock['normalized_score']:.1f}")
    col2.metric("P/E Ratio", selected_stock['pe_ratio'])
    col2.metric("PEG Ratio", selected_stock['peg_ratio'])

    st.markdown("### Metric Comparison vs. Sector Average")
    for metric in EXTRA_METRICS:
        val = selected_stock[metric]
        avg = sector_df[metric].mean() if not sector_df.empty else None
        label = EXTRA_METRICS_LABELS[metric]
        if avg is not None and val is not None:
            diff = val - avg
            color = "🟢" if diff > 0 else "🔴"
            st.write(f"**{label}:** {val:.3g} | Sector Avg: {avg:.3g} {color} ({'above' if diff>0 else 'below'} sector avg)")
        else:
            st.write(f"**{label}:** {val if val is not None else 'N/A'} | Sector Avg: {'N/A'}")

def main():
    st.set_page_config(page_title="Stock Analyzer", layout="wide")
    st.title("📈 S&P 500 Fundamental Analysis (with Sector Comparison)")

    uploaded_file = st.file_uploader("Upload your S&P 500 Excel (.xlsx) file", type=["xlsx"])

    if uploaded_file is not None:
        if "tickers" not in st.session_state or st.session_state.uploaded_file_name != uploaded_file.name:
            tickers = get_tickers_from_excel(uploaded_file)
            st.session_state.tickers = tickers
            st.session_state.uploaded_file_name = uploaded_file.name
            st.session_state.results = None
        else:
            tickers = st.session_state.tickers

        st.success(f"Loaded {len(tickers)} tickers from file")

        if st.button("Analyze Stocks"):
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

        if st.session_state.get("results") is not None:
            display_results(st.session_state.results)
    else:
        st.info("Please upload an Excel file with tickers in the first column.")

if __name__ == '__main__':
    main()
