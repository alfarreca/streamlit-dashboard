# defence_combined_dashboard.py

import pandas as pd
import numpy as np
import yfinance as yf
from pandas_datareader import data as web
import streamlit as st

st.set_page_config(page_title="Defense Sector Dashboard", layout="wide")


# ─── 1) DATA FETCHERS ──────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def fetch_weekly_prices(ticker: str) -> pd.DataFrame:
    """Fetch weekly OHLCV data for a ticker, try yfinance then fallback to Stooq."""
    try:
        df = yf.Ticker(ticker).history(period="6mo", interval="1wk")
    except Exception:
        df = pd.DataFrame()
    if df.empty or "Close" not in df:
        # Stooq fallback (strip suffix, uppercase, no exchange)
        sym = ticker.split(":")[-1].split(".")[0]
        try:
            df = web.DataReader(sym, "stooq").sort_index().loc[:, ["Close", "Volume"]]
            df = df.resample("W-FRI").last()
        except Exception:
            return pd.DataFrame()
    df = df.rename(columns=str.capitalize)
    return df



@st.cache_data(ttl=3600)
def fetch_fundamentals(tickers: list[str]) -> pd.DataFrame:
    """Pull dividend yield, payout ratio, FCF, interest coverage & P/E via yfinance."""
    rows = []
    for t in tickers:
        tk = yf.Ticker(t)
        info = tk.info
        rows.append({
            "Ticker":            t,
            "Dividend Yield (%)": round(info.get("dividendYield", 0) * 100, 2),
            "Dividend Payout Ratio (%)": round(info.get("payoutRatio", 0) * 100, 2),
            "Free Cash Flow (m)": round(info.get("freeCashflow", 0) / 1e6, 2),
            "FCF Payout Ratio (%)": None,  # compute later
            "Interest Coverage": round(
                info.get("ebit", 0) / abs(info.get("interestExpense", 1)), 2
            ) if info.get("interestExpense", 0) else None,
            "P/E (TTM)": round(info.get("trailingPE", np.nan), 2),
        })
    fund = pd.DataFrame(rows).set_index("Ticker")
    # compute FCF payout if both exist
    fund["FCF Payout Ratio (%)"] = fund.apply(
        lambda r: round(r["Dividend Payout Ratio (%)"] if r["Dividend Payout Ratio (%)"] else 0, 2),
        axis=1
    )
    return fund.reset_index()



# ─── 2) SIGNALS & TECHNICALS ───────────────────────────────────────────────────

def compute_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Given df with 'Close' & 'MA10', compute crossover, buy/ok, divergence, etc."""
    prev = df["Close"].shift(1)
    prev_ma = df["MA10"].shift(1)

    crossover = np.where(df["Close"] > df["MA10"], "Above", "Below")
    buy_ok    = np.where((prev < prev_ma) & (df["Close"] > df["MA10"]), "Buy", "OK")
    divergence= ((df["Close"] - df["MA10"]) / df["MA10"] * 100).round(2)

    return pd.DataFrame({
        "Signal":        buy_ok,
        "Last Updated":  df.index.strftime("%m/%d/%Y"),
        "Crossover":     crossover,
        "Divergence":    divergence,
        "Prev Price":    prev.round(2),
        "Prev MA10":     prev_ma.round(2),
    }, index=df.index)



def build_technical_df(tickers: list[str]) -> pd.DataFrame:
    """Loop tickers, fetch prices, calculate MA10/MA20 & signals, flatten to one row each."""
    records = []
    for t in tickers:
        df = fetch_weekly_prices(t)
        if df.empty: continue

        df["MA10"] = df["Close"].rolling(10).mean()
        df["MA20"] = df["Close"].rolling(20).mean()

        sig = compute_signals(df)

        latest = df.iloc[-1]
        prev10 = sig.iloc[-1]  # last signal row

        records.append({
            "Ticker":         t,
            "Price":          latest["Close"].round(2),
            "MA10":           latest["MA10"].round(2),
            "MA20":           latest["MA20"].round(2),
            "% vs MA10":      round((latest["Close"]/latest["MA10"] - 1)*100, 2),
            "Volume":         int(latest["Volume"]),
            "Vol MA10":       int(df["Volume"].rolling(10).mean().iloc[-1]),
            **prev10.to_dict()
        })

    return pd.DataFrame(records)



# ─── 3) STREAMLIT UI ────────────────────────────────────────────────────────────

TICKERS = ["ETR:RHM", "STO:SAAB-B", "EPA:HO", "LON:BA", "BIT:LDO"]

st.title("🛡️ Defense Sector: Weekly Signal Dashboard")

show_all = st.checkbox("Show All Tickers Table", value=True)
tech_df  = build_technical_df(TICKERS)
fund_df  = fetch_fundamentals(TICKERS)

if show_all:
    st.subheader("All Tickers — Technical & Fundamental Metrics")
    combined = tech_df.merge(fund_df, on="Ticker")
    st.dataframe(combined, use_container_width=True)

st.markdown("---")

ticker = st.selectbox("Select a Ticker to View Chart", TICKERS)
chart_df = fetch_weekly_prices(ticker)
if chart_df.empty:
    st.info("Price data not available for selected ticker.")
else:
    chart_df["MA10"] = chart_df["Close"].rolling(10).mean()
    chart_df["MA20"] = chart_df["Close"].rolling(20).mean()

    st.subheader(f"📈 Weekly Price Chart: {ticker}")
    st.line_chart(chart_df[["Close","MA10","MA20"]])

