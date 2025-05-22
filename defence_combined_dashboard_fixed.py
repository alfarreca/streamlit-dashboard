import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
from io import StringIO

# ════════════════════════════════════════════════════════════════
# Symbol helpers
# ════════════════════════════════════════════════════════════════

def yf_symbol(mixed: str) -> str:
    """Convert 'EXCH:SYMB' → Yahoo code; return arg untouched if already fine."""
    if ":" not in mixed:
        return mixed
    exch, sym = mixed.split(":", 1)
    suffix = {
        "ETR": "DE",
        "STO": "ST",
        "EPA": "PA",
        "LON": "L",
        "BIT": "MI",
    }.get(exch.upper())
    return f"{sym}.{suffix}" if suffix else mixed


def _safe(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return np.nan


# ════════════════════════════════════════════════════════════════
# Data fetchers (cached)
# ════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False)
def fetch_weekly_ohlcv(ticker: str) -> pd.DataFrame:
    """1‑year daily → weekly‑Friday Close & Volume; Stooq fallback."""
    ysym = yf_symbol(ticker)
    df = (
        yf.Ticker(ysym)
        .history(period="1y", interval="1d")
        .loc[:, ["Close", "Volume"]]
    )

    # fallback: stooq daily
    if df.empty:
        code = ysym.split(".")[0].lower()
        try:
            txt = requests.get(f"https://stooq.com/q/d/l/?s={code}&i=d", timeout=5).text
            if "Date" in txt:
                df = pd.read_csv(StringIO(txt), parse_dates=["Date"], index_col="Date").loc[:, ["Close"]]
                df["Volume"] = np.nan
        except requests.RequestException:
            pass

    if df.empty:
        return df

    wk = pd.DataFrame(
        {
            "Close": df["Close"].resample("W-FRI").last(),
            "Volume": df["Volume"].resample("W-FRI").sum(min_count=1),
        }
    ).dropna(subset=["Close"])
    return wk


@st.cache_data(show_spinner=False)
def fetch_fundamentals(tickers: tuple[str, ...]) -> pd.DataFrame:
    """Return a DF indexed by *tickers*; columns: dividend yield, payout ratio, FCF."""
    dy, pr, fcf = [], [], []
    for t in tickers:
        try:
            info = yf.Ticker(yf_symbol(t)).info or {}
        except Exception:
            info = {}

        # Dividend yield quirks
        raw_dy = _safe(info.get("dividendYield"))
        dy_pct = raw_dy * 100 if (not np.isnan(raw_dy) and raw_dy < 1) else raw_dy
        dy.append(dy_pct)

        # Payout ratio (always a fraction per docs)
        raw_pr = _safe(info.get("payoutRatio"))
        pr.append(raw_pr * 100 if not np.isnan(raw_pr) else np.nan)

        # Free cash‑flow (convert to millions local currency)
        raw_fcf = _safe(info.get("freeCashflow"))
        fcf.append(raw_fcf / 1e6 if not np.isnan(raw_fcf) else np.nan)

    return pd.DataFrame(
        {
            "Dividend Yield (%)": dy,
            "Dividend Payout Ratio (%)": pr,
            "Free Cash Flow (LC m)": fcf,
        },
        index=tickers,
    )


# ════════════════════════════════════════════════════════════════
# Technical calculations
# ════════════════════════════════════════════════════════════════

def calc_technicals(df: pd.DataFrame) -> dict:
    if df.empty or len(df) < 20:
        return {}

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


# ════════════════════════════════════════════════════════════════
# Streamlit UI
# ════════════════════════════════════════════════════════════════

def main():
    st.set_page_config(page_title="Defense Sector Dashboard", layout="wide")
    st.markdown("## :shield: Defense Sector: Weekly Signal Dashboard")

    tickers = (
        "ETR:RHM",
        "STO:SAAB-B",
        "EPA:HO",
        "LON:BA",
        "BIT:LDO",
    )

    # UI controls
    show_tbl = st.checkbox("Show All Tickers Table", True)
    sel = st.selectbox("Select a Ticker to View Chart", tickers)

    # Data pulls
    fund_df = fetch_fundamentals(tickers)
    tech_df = pd.DataFrame({t: calc_technicals(fetch_weekly_ohlcv(t)) for t in tickers}).T

    combined = pd.concat([tech_df, fund_df], axis=1).round(2)

    if show_tbl:
        st.subheader(":bar_chart: All Tickers – Technical & Fundamental Metrics")
        st.dataframe(
            combined.style.apply(lambda s: ["background-color:#FFEB3B" if x == s.max() else "" for x in s],
                                  subset=["Dividend Yield (%)", "Dividend Payout Ratio (%)"]),
            use_container_width=True,
        )

    # Chart
    wk = fetch_weekly_ohlcv(sel)
    if wk.empty:
        st.warning("No price data for selected ticker.")
    else:
        plot = wk.copy()
        plot["MA10"] = plot["Close"].rolling(10).mean()
        plot["MA20"] = plot["Close"].rolling(20).mean()
        st.subheader(f":chart_with_upwards_trend: Weekly Price Chart: {sel}")
        st.line_chart(plot[["Close", "MA10", "MA20"]])


if __name__ == "__main__":
    main()
