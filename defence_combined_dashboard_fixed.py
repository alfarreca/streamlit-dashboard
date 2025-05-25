import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
from io import StringIO

# ──────────────────────────── Helpers ────────────────────────────

def yf_ticker(ticker: str) -> str:
    try:
        exch, sym = ticker.split(":")
    except ValueError:
        return ticker
    suffix_map = {
        "ETR": "DE",
        "STO": "ST",
        "EPA": "PA",
        "LON": "L",
        "BIT": "MI",
    }
    suffix = suffix_map.get(exch.upper())
    if suffix is None:
        return ticker
    return f"{sym}.{suffix}"

def safe_mul(val, factor):
    return float(val) * factor if isinstance(val, (int, float)) else np.nan

def safe_div(val, divisor):
    return float(val) / divisor if isinstance(val, (int, float)) else np.nan

@st.cache_data(show_spinner=False)
def fetch_weekly_prices(ticker: str) -> pd.DataFrame:
    yf_sym = yf_ticker(ticker)
    df = yf.Ticker(yf_sym).history(period="1y", interval="1d")[["Close"]]

    if df.empty:
        sym = yf_sym.split(".")[0].lower()
        url = f"https://stooq.com/q/d/l/?s={sym}&i=w"
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            if "Date" in resp.text:
                df = pd.read_csv(StringIO(resp.text), parse_dates=["Date"], index_col="Date")[["Close"]]
        except requests.RequestException:
            df = pd.DataFrame()

    df = df.sort_index()
    if not df.empty:
        df = df.resample("W-FRI").last().dropna()
    return df

@st.cache_data(show_spinner=False)
def fetch_fundamentals(tickers: tuple[str, ...]) -> pd.DataFrame:
    rows = []
    for raw in tickers:
        t = yf_ticker(raw)
        info = yf.Ticker(t).info or {}
        rows.append({
            "Ticker": raw,
            "Dividend Yield (%)": safe_mul(info.get("dividendYield"), 100),
            "Payout Ratio (%)": safe_mul(info.get("payoutRatio"), 100),
            "Free Cash Flow (m)": safe_div(info.get("freeCashflow"), 1e6),
            "Interest Coverage": info.get("interestCoverage", np.nan),
            "P/E (TTM)": info.get("trailingPE", np.nan),
        })
    return pd.DataFrame(rows).set_index("Ticker").sort_index()

def compute_signal(df: pd.DataFrame) -> str:
    if len(df) < 20:
        return "n/a"
    ma10 = df["Close"].rolling(10).mean().iloc[-1]
    ma20 = df["Close"].rolling(20).mean().iloc[-1]
    if np.isnan(ma10) or np.isnan(ma20):
        return "n/a"
    return "Buy" if ma10 > ma20 else "Sell"

# ──────────────────────────── Streamlit ────────────────────────────

def main() -> None:
    st.set_page_config(page_title="Defense Sector Dashboard", layout="wide")
    st.title("\U0001F6E1\ufe0f Defense Sector: Combined Metrics & Price Dashboard")

    # ─── Ticker Input ─────────────────────────────────────────
    st.markdown("### Tickers")
    tick_input = st.text_input("Enter tickers (e.g., ETR:RHM STO:SAAB-B EPA:HO or just RHM SAAB-B HO)",
                               "RHM SAAB-B HO BA LDO")

    # Mapping known tickers to full form
    known = {
        "RHM": "ETR:RHM",
        "SAAB-B": "STO:SAAB-B",
        "HO": "EPA:HO",
        "BA": "LON:BA",
        "LDO": "BIT:LDO",
    }

    if st.button("\U0001F501 Load Tickers"):
        raw_tickers = [t.strip() for t in tick_input.split()]
        tickers = tuple(known.get(t, t) for t in raw_tickers)
    else:
        tickers = ("ETR:RHM", "STO:SAAB-B", "EPA:HO", "LON:BA", "BIT:LDO")

    # ─── Fetch & Compute Data ─────────────────────────────────────
    fundamentals = fetch_fundamentals(tickers)
    signals, last_dates = [], []
    for tick in tickers:
        wk = fetch_weekly_prices(tick)
        if wk.empty:
            signals.append("n/a")
            last_dates.append("")
        else:
            signals.append(compute_signal(wk))
            last_dates.append(wk.index[-1].strftime("%Y-%m-%d"))

    fundamentals["MA Signal"] = signals
    fundamentals["Last Price Date"] = last_dates

    st.subheader("\U0001F4CA Fundamentals & Weekly MA Signals")
    st.dataframe(
        fundamentals.style.format({
            "Dividend Yield (%)": "{:.2f}",
            "Payout Ratio (%)": "{:.2f}",
            "Free Cash Flow (m)": "{:,.0f}",
        }),
        use_container_width=True,
    )

    # ─── Weekly Chart ─────────────────────────────────────────────
    st.markdown("---")
    selection = st.selectbox("Select a ticker to view the weekly chart:", tickers)
    chart_df = fetch_weekly_prices(selection)

    if chart_df.empty:
        st.info("\u2757 Price data not available for the selected ticker.")
    else:
        chart_df = chart_df.copy()
        chart_df["MA10"] = chart_df["Close"].rolling(10).mean()
        chart_df["MA20"] = chart_df["Close"].rolling(20).mean()
        st.subheader(f"\U0001F4C8 Weekly Close & Moving Averages — {selection}")
        st.line_chart(chart_df[["Close", "MA10", "MA20"]])

if __name__ == "__main__":
    main()
