import streamlit as st
import pandas as pd
import yfinance as yf

st.title("Yahoo Finance Ticker Checker")

uploaded = st.file_uploader("Upload your ticker list (CSV or Excel)", type=["csv", "xlsx"])

if uploaded:
    # Read file
    if uploaded.name.endswith('.csv'):
        df = pd.read_csv(uploaded)
    else:
        df = pd.read_excel(uploaded)
    st.write("Preview:", df.head())

    # Guess ticker column
    ticker_col = None
    for col in df.columns:
        if 'ticker' in col.lower():
            ticker_col = col
            break
    if not ticker_col:
        ticker_col = st.selectbox("Select ticker column:", df.columns)

    st.write(f"Checking Yahoo Finance for tickers in column: **{ticker_col}**")
    df['Exists_on_Yahoo'] = False
    df['Yahoo_Exchange'] = ''
    df['Yahoo_Name'] = ''
    df['Yahoo_Sector'] = ''
    df['Yahoo_Industry'] = ''
    df['Yahoo_Country'] = ''

    # Only check on button click
    if st.button("Check Yahoo Finance"):
        prog = st.progress(0)
        total = len(df)
        results = []
        for i, ticker in enumerate(df[ticker_col]):
            try:
                tk = yf.Ticker(str(ticker))
                info = tk.info
                if 'longName' in info or 'shortName' in info:
                    exists = True
                    exchange = info.get('exchange', '')
                    name = info.get('longName', info.get('shortName', ''))
                    sector = info.get('sector', '')
                    industry = info.get('industry', '')
                    country = info.get('country', '')
                else:
                    exists = False
                    exchange = ''
                    name = ''
                    sector = ''
                    industry = ''
                    country = ''
            except Exception:
                exists = False
                exchange = ''
                name = ''
                sector = ''
                industry = ''
                country = ''
            results.append((exists, exchange, name, sector, industry, country))
            prog.progress((i + 1) / total)
        df['Exists_on_Yahoo'], df['Yahoo_Exchange'], df['Yahoo_Name'], df['Yahoo_Sector'], df['Yahoo_Industry'], df['Yahoo_Country'] = zip(*results)
        st.success("Check complete!")
        st.write(df.head(10))

        # Download link
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Results as CSV", csv, "Checked_Yahoo_Tickers.csv", "text/csv")
else:
    st.info("Upload a CSV or Excel file with a ticker column to begin.")
