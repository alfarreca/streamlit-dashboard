# -*- coding: utf-8 -*-

import streamlit as st as st import pandas as pd import numpy as np import yfinance as yf import requests import re from io import StringIO

# ────────────────────────────────────────────────────────────────

# Helper utilities

# ────────────────────────────────────────────────────────────────

def yf\_symbol(mixed: str) -> str: """Convert an 'EXCHANGE\:SYMBOL' string to the Yahoo Finance code.""" if ":" not in mixed: return mixed  # already a Yahoo‑style ticker exchange, symbol = mixed.split(":", 1) suffix = { "ETR": "DE",  # Frankfurt / Xetra "STO": "ST",  # Stockholm "EPA": "PA",  # Paris "LON": "L",   # London "BIT": "MI",  # Milan "NYSE": "",   # NYSE (no suffix) "NASDAQ": "",  # Nasdaq (no suffix) }.get(exchange.upper(), "") return f"{symbol}{('.' + suffix) if suffix else ''}"

def \_safe(value): """Return float(value) or NaN.""" try: return float(value) except (TypeError, ValueError): return np.nan

def parse\_ticker\_input(text: str) -> tuple\[str, ...]: """Split user input on commas / whitespace → tuple of non‑empty strings.""" return tuple(tok.strip() for tok in re.split(r"\[ ,]+", text.strip()) if tok.strip())

# ────────────────────────────────────────────────────────────────

# Data fetchers (cached)

# ────────────────────────────────────────────────────────────────

@st.cache\_data(show\_spinner=False) def fetch\_weekly\_ohlcv(ticker: str) -> pd.DataFrame: """Retrieve 1‑year daily data → resample to weekly Friday Close & Volume. Falls back to Stooq if Yahoo returns nothing. """ ysym = yf\_symbol(ticker) df = ( yf.Ticker(ysym) .history(period="1y", interval="1d") .loc\[:, \["Close", "Volume"]] )

```
if df.empty:  # fallback to Stooq daily CSV (no volume)
    sym = ysym.split(".")[0].lower()
    try:
        txt = requests.get(f"https://stooq.com/q/d/l/?s={sym}&i=d", timeout=5).text
        if "Date" in txt:
            df = pd.read_csv(StringIO(txt), parse_dates=["Date"], index_col="Date").loc[:, ["Close"]]
            df["Volume"] = np.nan
    except requests.RequestException:
        pass

if df.empty:
    return df

weekly = pd.DataFrame({
    "Close": df["Close"].resample("W-FRI").last(),
    "Volume": df["Volume"].resample("W-FRI").sum(min_count=1),
}).dropna(subset=["Close"])
return weekly
```

@st.cache\_data(show\_spinner=False) def fetch\_fundamentals(tickers: tuple\[str, ...]) -> pd.DataFrame: """Pull dividend yield, payout ratio, and free‑cash‑flow for each ticker.""" rows = \[] for t in tickers: try: info = yf.Ticker(yf\_symbol(t)).info or {} except Exception: info = {}

```
    raw_dy = _safe(info.get("dividendYield"))
    dy_pct = raw_dy * 100 if (not np.isnan(raw_dy) and raw_dy < 1) else raw_dy

    raw_pr = _safe(info.get("payoutRatio"))
    pr_pct = raw_pr * 100 if not np.isnan(raw_pr) else np.nan

    raw_fcf = _safe(info.get("freeCashflow"))
    fcf_m = raw_fcf / 1e6 if not np.isnan(raw_fcf) else np.nan

    rows.append({
        "Ticker": t,
        "Dividend Yield (%)": dy_pct,
        "Dividend Payout Ratio (%)": pr_pct,
        "Free Cash Flow (LC m)": fcf_m,
    })

df = pd.DataFrame.from_records(rows).set_index("Ticker")
# Ensure all requested tickers exist as index rows (NaNs if data missing)
return df.reindex(tickers)
```

# ────────────────────────────────────────────────────────────────

# Technical calculations

# ────────────────────────────────────────────────────────────────

def compute\_technicals(df: pd.DataFrame) -> dict\[str, float | str]: if df.empty or len(df) < 20: return {}

```
latest = df.iloc[-1]
prev = df.iloc[-2]

ma10 = df["Close"].rolling(10).mean()
ma20 = df["Close"].rolling(20).mean()

return {
    "Price": latest.Close,
    "MA10": ma10.iloc[-1],
    "MA20": ma20.iloc[-1],
    "% vs MA10": (latest.Close - ma10.iloc[-1]) / ma10.iloc[-1] * 100,
    "Volume": latest.Volume,
    "Vol MA10": df["Volume"].rolling(10).mean().iloc[-1],
    "Signal": "Buy" if ma10.iloc[-1] > ma20.iloc[-1] else "Sell",
    "Last Updated": latest.name.strftime("%m/%d/%Y"),
    "Crossover": "Above" if latest.Close > ma20.iloc[-1] else "Below",
    "Divergence": (
        "Overbought" if latest.Close >= ma10.iloc[-1] * 1.1 else (
            "Oversold" if latest.Close <= ma10.iloc[-1] * 0.9 else "OK")
    ),
    "Prev Price": prev.Close,
    "Prev MA10": ma10.iloc[-2],
}
```

# ────────────────────────────────────────────────────────────────

# Streamlit UI

# ────────────────────────────────────────────────────────────────

def main(): st.set\_page\_config(page\_title="Defense Sector Dashboard", layout="wide") st.markdown("## \:shield: Defense Sector: Weekly Signal Dashboard")

```
DEFAULTS = "ETR:RHM STO:SAAB-B EPA:HO LON:BA BIT:LDO"

# ——— Sidebar controls ———
with st.sidebar:
    st.header("Ticker Configuration")
    ticker_input = st.text_input(
        "Enter tickers (comma or space separated)",
        value=st.session_state.get("_ticker_text", DEFAULTS),
    )
    if st.button("Load Tickers", help="Fetch data for the entered tickers"):
        parsed = parse_ticker_input(ticker_input)
        if parsed:
            st.session_state.tickers = parsed
            st.session_state._ticker_text = ticker_input
            st.success("Tickers loaded! ↻ Refresh if the table hasn't updated.")

tickers = st.session_state.get("tickers", parse_ticker_input(DEFAULTS))

# ——— Optional table toggle ———
show_table = st.checkbox("Show All Tickers Table", True)

# ——— Data pulls ———
fund_df = fetch_fundamentals(tickers)
tech_df = pd.DataFrame({t: compute_technicals(fetch_weekly_ohlcv(t)) for t in tickers}).T

combined = pd.concat([tech_df, fund_df], axis=1).round(2)

if show_table:
    st.subheader(":bar_chart: All Tickers – Technical & Fundamental Metrics")
    st.dataframe(
        combined.style.apply(
            lambda s: ["background-color:#FFEB3B" if x == s.max() else "" for x in s],
            subset=["Dividend Yield (%)", "Dividend Payout Ratio (%)"],
        ),
        use_container_width=True,
    )

# ——— Chart ———
sel = st.selectbox("Select a Ticker to View Chart", tickers)
wk = fetch_weekly_ohlcv(sel)
if wk.empty:
    st.warning("No price data available for the selected ticker.")
else:
    plot_df = wk.copy()
    plot_df["MA10"] = plot_df["Close"].rolling(10).mean()
    plot_df["MA20"] = plot_df["Close"].rolling(20).mean()
    st.subheader(f":chart_with_upwards_trend: Weekly Price Chart: {sel}")
    st.line_chart(plot_df[["Close", "MA10", "MA20"]])
```

if **name** == "**main**": main()
