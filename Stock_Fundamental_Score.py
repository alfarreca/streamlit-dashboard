import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import yfinance as yf
import pandas as pd
from datetime import datetime
import time

# Configuration
CREDENTIALS_FILE = 'credentials.json'  # Google API credentials file

# Fundamental scoring weights (adjust as needed)
SCORE_WEIGHTS = {
    'pe_ratio': 0.2,
    'peg_ratio': 0.25,
    'debt_to_equity': -0.15,  # Negative because lower is better
    'current_ratio': 0.1,
    'return_on_equity': 0.15,
    'profit_margin': 0.15
}

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_google_sheet_tickers(google_sheet_name, worksheet_name):
    """Fetch S&P 500 tickers from Google Sheet"""
    try:
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)
        
        sheet = client.open(google_sheet_name).worksheet(worksheet_name)
        tickers = sheet.col_values(1)[1:]  # Assuming tickers are in first column, skip header
        
        return [ticker.strip() for ticker in tickers if ticker.strip()]
    
    except Exception as e:
        st.error(f"Error accessing Google Sheet: {e}")
        return []

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_fundamentals(ticker):
    """Fetch fundamental data from Yahoo Finance"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Get key metrics (handle missing data)
        fundamentals = {
            'ticker': ticker,
            'pe_ratio': info.get('trailingPE', None),
            'peg_ratio': info.get('pegRatio', None),
            'debt_to_equity': info.get('debtToEquity', None),
            'current_ratio': info.get('currentRatio', None),
            'return_on_equity': info.get('returnOnEquity', None),
            'profit_margin': info.get('profitMargins', None),
            'company_name': info.get('shortName', ticker),
            'sector': info.get('sector', 'N/A'),
            'industry': info.get('industry', 'N/A'),
            'market_cap': info.get('marketCap', None)
        }
        
        # Add current price if available
        hist = stock.history(period="1d")
        if not hist.empty:
            fundamentals['price'] = hist['Close'].iloc[-1]
        
        return fundamentals
    
    except Exception as e:
        st.error(f"Error fetching data for {ticker}: {e}")
        return None

def normalize_value(value, min_val, max_val, reverse=False):
    """Normalize a value to 0-1 scale"""
    if value is None or min_val is None or max_val is None:
        return 0
    
    if min_val == max_val:
        return 0.5
    
    normalized = (value - min_val) / (max_val - min_val)
    
    if reverse:
        return 1 - normalized
    return normalized

def calculate_scores(fundamentals_list):
    """Calculate fundamental scores for all stocks"""
    if not fundamentals_list:
        return []
    
    # Create DataFrame for easier calculations
    df = pd.DataFrame(fundamentals_list)
    
    # Calculate min/max for normalization
    metrics = {
        'pe_ratio': {'min': df['pe_ratio'].min(), 'max': df['pe_ratio'].max(), 'reverse': True},
        'peg_ratio': {'min': df['peg_ratio'].min(), 'max': df['peg_ratio'].max(), 'reverse': True},
        'debt_to_equity': {'min': df['debt_to_equity'].min(), 'max': df['debt_to_equity'].max(), 'reverse': True},
        'current_ratio': {'min': df['current_ratio'].min(), 'max': df['current_ratio'].max(), 'reverse': False},
        'return_on_equity': {'min': df['return_on_equity'].min(), 'max': df['return_on_equity'].max(), 'reverse': False},
        'profit_margin': {'min': df['profit_margin'].min(), 'max': df['profit_margin'].max(), 'reverse': False}
    }
    
    # Calculate normalized scores
    for metric, params in metrics.items():
        df[f'{metric}_score'] = df[metric].apply(
            lambda x: normalize_value(x, params['min'], params['max'], params['reverse']) * SCORE_WEIGHTS[metric]
            if pd.notnull(x) else 0
        )
    
    # Calculate total score
    df['total_score'] = df[[f'{m}_score' for m in SCORE_WEIGHTS.keys()]].sum(axis=1)
    
    # Normalize total score to 0-100
    min_score, max_score = df['total_score'].min(), df['total_score'].max()
    df['normalized_score'] = df['total_score'].apply(
        lambda x: ((x - min_score) / (max_score - min_score)) * 100 if (max_score - min_score) != 0 else 50
    )
    
    # Convert back to list of dicts
    results = df.to_dict('records')
    
    return results

def display_results(results):
    """Display results in Streamlit"""
    if not results:
        st.warning("No results to display")
        return
    
    df = pd.DataFrame(results)
    
    # Sort by score descending
    df = df.sort_values('normalized_score', ascending=False)
    
    # Format columns
    df['market_cap'] = df['market_cap'].apply(lambda x: f"${x/1e9:.2f}B" if pd.notnull(x) else "N/A")
    df['price'] = df['price'].apply(lambda x: f"${x:.2f}" if pd.notnull(x) else "N/A")
    
    # Display metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Stocks Analyzed", len(df))
    col2.metric("Highest Score", f"{df['normalized_score'].max():.1f}")
    col3.metric("Average Score", f"{df['normalized_score'].mean():.1f}")
    
    # Add filters
    st.subheader("Filter Results")
    col1, col2 = st.columns(2)
    
    min_score = col1.slider("Minimum Score", 0, 100, 0)
    sectors = df['sector'].unique()
    selected_sectors = col2.multiselect("Filter by Sector", sectors, default=sectors)
    
    filtered_df = df[(df['normalized_score'] >= min_score) & 
                     (df['sector'].isin(selected_sectors))]
    
    # Display table
    st.subheader("Stock Fundamental Scores")
    st.dataframe(
        filtered_df[['ticker', 'company_name', 'sector', 'normalized_score', 'price', 'market_cap']]
        .rename(columns={
            'ticker': 'Ticker',
            'company_name': 'Company',
            'sector': 'Sector',
            'normalized_score': 'Score',
            'price': 'Price',
            'market_cap': 'Market Cap'
        }),
        height=600,
        use_container_width=True
    )
    
    # Add download button
    csv = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download CSV",
        data=csv,
        file_name=f"fundamental_scores_{datetime.now().strftime('%Y%m%d')}.csv",
        mime='text/csv'
    )
    
    # Show details for selected stock
    st.subheader("Stock Details")
    selected_ticker = st.selectbox("Select a stock to view details", filtered_df['ticker'])
    selected_stock = next(item for item in results if item["ticker"] == selected_ticker)
    
    cols = st.columns(2)
    with cols[0]:
        st.metric("Company", selected_stock['company_name'])
        st.metric("Sector", selected_stock['sector'])
        st.metric("Industry", selected_stock['industry'])
        st.metric("Price", f"${selected_stock.get('price', 'N/A')}")
    
    with cols[1]:
        st.metric("Fundamental Score", f"{selected_stock['normalized_score']:.1f}")
        st.metric("P/E Ratio", selected_stock['pe_ratio'])
        st.metric("PEG Ratio", selected_stock['peg_ratio'])
        st.metric("Debt/Equity", selected_stock['debt_to_equity'])

def main():
    st.set_page_config(
        page_title="Stock Fundamental Analyzer",
        page_icon="📈",
        layout="wide"
    )
    
    st.title("📈 S&P 500 Fundamental Analysis")
    st.markdown("""
    This app analyzes fundamental metrics for S&P 500 stocks fetched from your Google Sheet.
    """)
    
    with st.expander("⚙️ Settings", expanded=True):
        google_sheet_name = st.text_input("Google Sheet Name", "S&P 500 Tickers")
        worksheet_name = st.text_input("Worksheet Name", "Tickers")
        st.info("Ensure your Google Sheet has tickers in the first column of the specified worksheet")
    
    if st.button("Analyze Stocks"):
        with st.spinner("Fetching tickers from Google Sheet..."):
            tickers = get_google_sheet_tickers(google_sheet_name, worksheet_name)
            
            if not tickers:
                st.error("No tickers found. Please check your Google Sheet settings.")
                return
            
            st.success(f"Found {len(tickers)} tickers")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            fundamentals = []
            for i, ticker in enumerate(tickers):
                status_text.text(f"Fetching data for {ticker} ({i+1}/{len(tickers)})")
                data = get_fundamentals(ticker)
                if data:
                    fundamentals.append(data)
                progress_bar.progress((i + 1) / len(tickers))
                time.sleep(0.1)  # Be nice to Yahoo Finance
            
            progress_bar.empty()
            status_text.empty()
            
            if fundamentals:
                with st.spinner("Calculating scores..."):
                    results = calculate_scores(fundamentals)
                    display_results(results)
            else:
                st.error("No fundamental data could be retrieved")

if __name__ == "__main__":
    main()
