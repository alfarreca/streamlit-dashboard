# -*- coding: utf-8 -*-

"""Defense Sector Multi‑Ticker Dashboard (Streamlit)

Paste any combination of `EXCHANGE:SYMBOL` tickers in the sidebar, click
**Load Tickers**, and the app recalculates technical + fundamental metrics and
a weekly‑price chart.

Works both locally (`streamlit run`) and on Streamlit Community Cloud.
"""

import re
from io import StringIO

import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# ────────────────────────────────────────────────────────────────

# Helpers

# ────────────────────────────────────────────────────────────────

def yf\_symbol(mixed: str) -> str:
"""Convert an 'EXCHANGE\:SYMBOL' code → Yahoo Finance symbol."""
if ":" not in mixed:
return mixed
exch, sym = mixed.split(":", 1)
suffix\_map = {
"ETR": "DE",  # Xetra / Frankfurt
"STO": "ST",  # Stockholm
"EPA": "PA",  # Paris
"LON": "L",   # London
"BIT": "MI",  # Milan
"NYSE": "",   # NYSE
"NASDAQ": "",  # Nasdaq
}
suf = suffix\_map.get(exch.upper(), "")
return f"{sym}{('.' + suf) if suf else ''}"

def parse\_input(text: str) -> tuple\[str, ...]:
"""Split user text on commas / whitespace, drop empties."""
return tuple(tok.strip() for tok in re.split(r"\[ ,]+", text) if tok.strip())

def \_safe(val):
try:
return float(val)
except (TypeError, ValueError):
return np.nan

# ────────────────────────────────────────────────────────────────

# Data fetchers (cached)

# ────────────────────────────────────────────────────────────────

@st.cache\_data(show\_spinner=False)
def fetch\_weekly\_ohlcv(ticker: str) -> pd.DataFrame:
ysym = yf\_symbol(ticker)
daily = yf.Ticker(ysym).history(period="1y", interval="1d")\[\["Close", "Volume"]]

```
if daily.empty:
    code = ysym.split(".")[0].lower()
    try:
        txt = requests.get(f"https://stooq.com/q/d/l/?s={code}&i=d", timeout=5).text
        if "Date" in txt:
            daily = pd.read_csv(StringIO(txt), parse_dates=["Date"], index_col="Date")[["Close"]]
            daily["Volume"] = np.nan
    except requests.RequestException:
        return pd.DataFrame()

weekly = pd.DataFrame({
    "Close": daily["Close"].resample("W-FRI").last(),
    "Volume": daily["Volume"].resample("W-FRI").sum(min_count=1),
}).dropna(subset=["Close"])
return weekly
```

@st.cache\_data(show\_spinner=False)
def fetch\_fundamentals(tickers: tuple\[str, ...]) -> pd.DataFrame:
rows = \[]
for t in tickers:
try:
info = yf.Ticker(yf\_symbol(t)).info or {}
except Exception:
info = {}

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

return pd.DataFrame(rows).set_index("Ticker").reindex(tickers)
```

# ────────────────────────────────────────────────────────────────

# Technical metrics

# ────────────────────────────────────────────────────────────────

def tech\_metrics(df: pd.DataFrame) -> dict\[str, float | str]:
if df.empty or len(df) < 20:
return {}

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
    "Last Updated": latest.name.strftime("%Y-%m-%d"),
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

def main():
st.set\_page\_config(page\_title="Defense Sector Dashboard", layout="wide")
st.title("🛡️ Defense Sector: Weekly Signal Dashboard")

\_default = "ETR\:RHM STO\:SAAB-B EPA\:HO LON\:BA BIT\:LDO"
with st.sidebar:
st.header("Tickers")
user\_text = st.text\_input("Enter tickers", \_default)
if st.button("Load Tickers"):
st.session\_state.tickers = parse\_input(user\_text)
tickers = st.session\_state.get("tickers", parse\_input(\_default))

```
show_table = st.checkbox("Show All Tickers Table", True)

fund = fetch_fundamentals(tickers)
tech = pd.DataFrame({t: tech_metrics(fetch_weekly_ohlcv(t)) for t in tickers}).T

combo = pd.concat([tech, fund], axis=1).round(2)

if show_table:
    st.subheader("📊 All Tickers – Technical & Fundamental Metrics")
    st.dataframe(
        combo.style.apply(
            lambda s: ["background-color:#FFEB3B" if x == s.max() else "" for x in s],
            subset=["Dividend Yield (%)", "Dividend Payout Ratio (%)"],
        ),
        use_container_width=True,
    )

sel = st.selectbox("Select Ticker to View Chart", tickers)
df_w = fetch_weekly_ohlcv(sel)
if df_w.empty:
    st.warning("No price data available.")
else:
    chart = df_w.copy()
    chart["MA10"] = chart["Close"].rolling(10).mean()
    chart["MA20"] = chart["Close"].rolling(20).mean()
    st.subheader(f"📈 Weekly Price Chart: {sel}")
    st.line_chart(chart[["Close", "MA10", "MA20"]])
```

if **name** == "**main**":
main()
