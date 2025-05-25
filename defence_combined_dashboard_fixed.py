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
        hist = yf.Ticker(t).history(period="6mo", interval="1wk")

        price = hist["Close"].iloc[-1] if not hist.empty else np.nan
        ma10 = hist["Close"].rolling(10).mean().iloc[-1] if len(hist) >= 10 else np.nan
        ma20 = hist["Close"].rolling(20).mean().iloc[-1] if len(hist) >= 20 else np.nan
        vol = hist["Volume"].iloc[-1] if not hist.empty else np.nan
        vol_ma10 = hist["Volume"].rolling(10).mean().iloc[-1] if len(hist) >= 10 else np.nan

        pct_vs_ma10 = ((price - ma10) / ma10 * 100) if ma10 and not np.isnan(ma10) else np.nan
        signal = "Buy" if ma10 > ma20 else "Sell" if not np.isnan(ma10) and not np.isnan(ma20) else "n/a"
        crossover = "Above" if price > ma10 else "Below" if not np.isnan(ma10) else "n/a"
        divergence = "Overbought" if pct_vs_ma10 > 10 else "Oversold" if pct_vs_ma10 < -10 else "OK"
        prev_price = hist["Close"].iloc[-2] if len(hist) >= 2 else np.nan
        last_updated = hist.index[-1].strftime("%Y-%m-%d") if not hist.empty else ""

        rows.append({
            "Ticker": raw,
            "Price": price,
            "MA10": ma10,
            "MA20": ma20,
            "% vs MA10": pct_vs_ma10,
            "Volume": vol,
            "Vol MA10": vol_ma10,
            "Signal": signal,
            "Last Updated": last_updated,
            "Crossover": crossover,
            "Divergence": divergence,
            "Prev Price": prev_price,
            "Dividend Yield (%)": safe_mul(info.get("dividendYield"), 100),
            "Payout Ratio (%)": safe_mul(info.get("payoutRatio"), 100),
            "Free Cash Flow (m)": safe_div(info.get("freeCashflow"), 1e6),
            "Interest Coverage": info.get("interestCoverage", np.nan),
            "P/E (TTM)": info.get("trailingPE", np.nan),
        })
    return pd.DataFrame(rows).set_index("Ticker").sort_index()

# ──────────────────────────── Streamlit ────────────────────────────

def main() -> None:
    st.set_page_config(page_title="Defense Sector Dashboard", layout="wide")
    st.title("\U0001F6E1\ufe0f Defense Sector: Weekly Signal Dashboard")

    st.markdown("#### Enter tickers below (e.g., RHM SAAB-B HO BA LDO or AAPL TSLA MSFT)")
    user_input = st.text_input("Enter tickers", "")
    tickers = [t.strip().upper() for t in user_input.split()] if user_input else []

    if not tickers:
        st.info("\u2139\ufe0f Please enter ticker symbols above and press Enter to load the dashboard.")
        return

    if st.button("Load Tickers"):
        with st.spinner("Fetching data..."):
            df = fetch_fundamentals(tuple(tickers))

            st.markdown("---")
            st.subheader("📊 All Tickers – Technical & Fundamental Metrics")
            st.dataframe(
                df.style.format({
                    "Price": "{:.2f}",
                    "MA10": "{:.2f}",
                    "MA20": "{:.2f}",
                    "% vs MA10": "{:.2f}%",
                    "Volume": "{:,.0f}",
                    "Vol MA10": "{:,.0f}",
                    "Dividend Yield (%)": "{:.2f}",
                    "Payout Ratio (%)": "{:.2f}",
                    "Free Cash Flow (m)": "{:,.0f}",
                    "P/E (TTM)": "{:.2f}"
                }),
                use_container_width=True,
            )

            st.markdown("---")
            selection = st.selectbox("Select a ticker to view the weekly chart:", tickers)
            chart_df = fetch_weekly_prices(selection)

            if chart_df.empty:
                st.warning("\u26a0\ufe0f No price data available for this ticker.")
            else:
                chart_df["MA10"] = chart_df["Close"].rolling(10).mean()
                chart_df["MA20"] = chart_df["Close"].rolling(20).mean()
                st.subheader(f"📈 Weekly Close & Moving Averages — {selection}")
                st.line_chart(chart_df[["Close", "MA10", "MA20"]])

if __name__ == "__main__":
    main()
