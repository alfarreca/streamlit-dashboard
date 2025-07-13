
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Google Sheets settings
SCOPE = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
GSHEET_ID = "1M9Vb7SnSwAGw3Uaqrje8m7nmQHJdqKXQoLkplZiDPt8"
GSHEET_RANGE = "Sheet1"
CREDENTIALS_PATH = "credentials/credentials.json"

@st.cache_data(show_spinner=True)
def load_watchlist_from_gsheet():
    creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPE)
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=GSHEET_ID, range=GSHEET_RANGE).execute()
    values = result.get("values", [])
    if not values:
        return pd.DataFrame()
    df = pd.DataFrame(values[1:], columns=values[0])
    return df

@st.cache_data(show_spinner=False)
def fetch_data(ticker, period="6mo"):
    try:
        df = yf.download(ticker, period=period)
        df["Ticker"] = ticker
        return df
    except Exception as e:
        return pd.DataFrame()

def plot_chart(df, ticker):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df.index,
                                 open=df["Open"],
                                 high=df["High"],
                                 low=df["Low"],
                                 close=df["Close"],
                                 name='Candlestick'))
    fig.update_layout(title=f"{ticker} Price Chart", xaxis_title="Date", yaxis_title="Price")
    st.plotly_chart(fig)

def main():
    st.title("📊 Automated Technical Analysis Report")
    with st.spinner("Loading your watchlist from Google Sheets..."):
        df_watchlist = load_watchlist_from_gsheet()
    if df_watchlist.empty:
        st.warning("Watchlist is empty or failed to load.")
        return
    st.dataframe(df_watchlist)

    tickers = df_watchlist["Symbol"].dropna().unique().tolist()

    for ticker in tickers:
        st.subheader(f"📈 {ticker}")
        df_price = fetch_data(ticker)
        if not df_price.empty:
            plot_chart(df_price, ticker)
        else:
            st.error(f"⚠️ Failed to fetch data for {ticker}")

if __name__ == "__main__":
    main()
