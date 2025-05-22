"""
Defense Sector – Vertical Signal & Chart Dashboard (auto‑adjust off)
Run:   streamlit run defence_vertical_dashboard.py
"""
from __future__ import annotations

from datetime import date
from typing import Dict, Tuple
import warnings

import pandas as pd
import yfinance as yf
import streamlit as st

# ───────────────── CONFIG ─────────────────
TICKERS: Dict[str, str] = {
    "ETR:RHM": "RHM.DE",
    "STO:SAAB-B": "SAAB-B.ST",
    "EPA:HO": "HO.PA",
    "LON:BA": "BA.L",
    "BIT:LDO": "LDO.MI",
}
CACHE_TTL = 60 * 60 * 24  # 1 day
SAFE_YIELD = (1, 7)
MAX_PAYOUT = 70
MIN_INT_COV = 3
MAX_PE = 40

warnings.filterwarnings("ignore", message="Styler.applymap")

# ────────────── HELPERS ──────────────

def as_pct(val: float | None) -> float | None:
    if val is None or pd.isna(val):
        return None
    return round(val * 100, 1) if val < 1 else round(val, 1)


def trailing_yield(tk: yf.Ticker) -> float | None:
    try:
        price = tk.history(period="1d")["Close"].iloc[-1]
    except Exception:
        return None
    if price is None or price == 0 or pd.isna(price):
        return None
    divs = tk.dividends
    if divs.empty:
        return None
    cash = divs.loc[divs.index >= divs.index.max() - pd.Timedelta(days=365)].sum()
    yld = cash / price * 100
    while yld > 20 and cash > 0.001:
        cash /= 10; yld = cash / price * 100
    return round(yld, 2)

# ───────── FUNDAMENTALS ─────────
@st.cache_data(ttl=CACHE_TTL)
def fetch_fundamentals(map_: Dict[str, str]) -> pd.DataFrame:
    rows = []
    for lbl, code in map_.items():
        tk = yf.Ticker(code)
        info, cf, fin, qfin = tk.info or {}, tk.cashflow, tk.financials, tk.quarterly_financials

        fcf = cf.loc["Free Cash Flow"].iloc[0]/1e6 if "Free Cash Flow" in cf.index else None

        # interest-coverage helper
        def _cov(frame):
            if frame.empty or "Ebit" not in frame.index:
                return None
            ebit = frame.loc["Ebit"].iloc[0]
            for k in ("Interest Expense","Finance Costs","Finance Cost","Net Finance Cost"):
                if k in frame.index and frame.loc[k].iloc[0]:
                    return round(ebit/abs(frame.loc[k].iloc[0]),2)
            return None
        cov = _cov(fin) or _cov(qfin)

        # dividends paid
        div_paid_m = (abs(cf.loc["Dividends Paid"].iloc[0])/1e6
                      if "Dividends Paid" in cf.index else None)
        if div_paid_m is None:
            dr, sh = info.get("dividendRate"), info.get("sharesOutstanding")
            if dr and sh:
                div_paid_m = dr*sh/1e6
        fcf_payout = round(div_paid_m/fcf*100,1) if div_paid_m and fcf else None

        rows.append({
            "Ticker": lbl,
            "Dividend Yield (%)": trailing_yield(tk),
            "Dividend Payout Ratio (%)": as_pct(info.get("payoutRatio")),
            "Free Cash Flow (m)": round(fcf,1) if fcf else None,
            "FCF Payout Ratio (%)": fcf_payout,
            "Interest Coverage": cov,
            "P/E (TTM)": as_pct(info.get("trailingPE")),
        })
    return pd.DataFrame(rows).set_index("Ticker")


# ───────── FUNDAMENTALS ─────────
@st.cache_data(ttl=CACHE_TTL)
def fetch_technical(map_: Dict[str, str]) -> Dict[str, Tuple[pd.DataFrame, dict]]:
    """Try weekly Yahoo download; if blank, fall back to daily then resample to weekly."""
    out: Dict[str, Tuple[pd.DataFrame, dict]] = {}
    for lbl, code in map_.items():
        # 1️⃣ attempt — weekly candles
        df = yf.download(code, period="2y", interval="1wk", auto_adjust=False, progress=False)
        if df.empty:
            # 2️⃣ fallback — daily → resample weekly
            df_daily = yf.download(code, period="2y", interval="1d", auto_adjust=False, progress=False)
            if df_daily.empty:
                continue
            df = df_daily.resample("W-FRI").agg({
                "Open": "first",
                "High": "max",
                "Low": "min",
                "Close": "last",
                "Adj Close": "last",
                "Volume": "sum",
            }).dropna(subset=["Close", "Volume"])
        # standardise Close column
        if "Close" not in df.columns and "Adj Close" in df.columns:
            df = df.rename(columns={"Adj Close": "Close"})
        if not {"Close", "Volume"}.issubset(df.columns):
            continue
        df = df.dropna(subset=["Close", "Volume"])
        df["MA10"], df["MA20"] = df["Close"].rolling(10).mean(), df["Close"].rolling(20).mean()
        last = df.iloc[-1]
        pct = (last.Close / last.MA10 - 1) * 100 if last.MA10 else None
        out[lbl] = (
            df,
            {
                "Price": round(last.Close, 2),
                "MA10": round(last.MA10, 2),
                "MA20": round(last.MA20, 2),
                "% vs MA10": round(pct, 2) if pct else None,
                "Signal": "Buy" if last.Close > last.MA10 else "Hold",
                "Last Updated": date.today().strftime("%m/%d/%Y"),
            },
        )
    return out

# ───────── STREAMLIT UI ─────────
st.set_page_config(page_title="Defense Dashboard", layout="wide")
st.title("🛡️ Defense Sector: Weekly Signal Dashboard")

# fetch data
tech = fetch_technical(TICKERS)
fund = fetch_fundamentals(TICKERS)
tech_df = pd.DataFrame.from_dict({k: v[1] for k, v in tech.items()}, orient="index")
combo = tech_df.join(fund, how="right")  # show fundamentals even if tech empty

# Styling: fundamentals flagged, technicals left plain
fund_cols = [
    "Dividend Yield (%)", "Dividend Payout Ratio (%)", "FCF Payout Ratio (%)",
    "Interest Coverage", "P/E (TTM)"
]

def colour(val, col):
    if col not in fund_cols:
        return ""
    if val is None or pd.isna(val):
        return "background-color:#fecaca;"
    if col == "Dividend Yield (%)" and not SAFE_YIELD[0] <= val <= SAFE_YIELD[1]:
        return "background-color:#fde047;"
    if col == "Dividend Payout Ratio (%)" and val > MAX_PAYOUT:
        return "background-color:#fde047;"
    if col == "FCF Payout Ratio (%)" and val is None:
        return "background-color:#fde047;"
    if col == "Interest Coverage" and val < MIN_INT_COV:
        return "background-color:#fde047;"
    if col == "P/E (TTM)" and val > MAX_PE:
        return "background-color:#fde047;"
    return ""

sty = combo.style.format(precision=2)
for c in fund_cols:
    sty = sty.applymap(lambda x, col=c: colour(x, col), subset=[c])

st.subheader("📊 All Tickers — Technical & Fundamental Metrics")
st.dataframe(sty, use_container_width=True)

# --- chart selector (still relies on technical data) ---
sel = st.selectbox("Select Ticker to View Chart", list(TICKERS.keys()), index=0)
if sel in tech:
    st.subheader(f"📈 Weekly Price Chart: {sel}")
    st.line_chart(tech[sel][0][["Close", "MA10", "MA20"]].dropna())
else:
    st.info("Price data not available for selected ticker.")


# --- Simple test block (for debugging) ---
import yfinance as yf

try:
    rhm = yf.Ticker("RHM.DE").history(period="1mo")
    st.subheader("🔍 Test: RHM.DE price fetch")
    if rhm.empty:
        st.error("⚠️ RHM.DE returned no data.")
    else:
        st.success(f"✅ Fetched {len(rhm)} rows.")
        st.line_chart(rhm["Close"])
except Exception as e:
    st.error(f"Error fetching RHM.DE: {e}")
