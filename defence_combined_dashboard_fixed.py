import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
from io import StringIO

# ════════════════════════════════════════════════════════════════
# Helper utilities
# ════════════════════════════════════════════════════════════════

def yf_symbol(mixed_ticker: str) -> str:
    """Convert 'EXCHANGE:SYMBOL' → Yahoo Finance symbol (e.g. ETR:RHM → RHM.DE)."""
    if ":" not in mixed_ticker:
        return mixed_ticker
    exch, symbol = mixed_ticker.split(":", 1)
    suf = {
        "ETR": "DE",  # Xetra / Frankfurt
        "STO": "ST",  # Stockholm
        "EPA": "PA",  # Paris
        "LON": "L",   # London
        "BIT": "MI",  # Milan
    }.get(exch.upper())
    return f"{symbol}.{suf}" if suf else mixed_ticker


def _safe(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return np.nan


@st.cache_data(show_spinner=False)
def fetch_weekly_ohlcv(ticker: str) -> pd.DataFrame:
    """Return weekly‑Friday OHLCV dataframe (Close+Volume at minimum)."""
    ysym = yf_symbol(ticker)

    df = (
        yf.Ticker(ysym)
        .history(period="1y", interval="1d")
        .loc[:, ["Close", "Volume"]]
    )

    if df.empty:
        csv_sym = ysym.split(".")[0].lower()
        url = f"https://stooq.com/q/d/l/?s={csv_sym}&i=d"
        try:
            txt = requests.get(url, timeout=5).text
            if "Date" in txt:
                df = pd.read_csv(StringIO(txt), parse_dates=["Date"], index_col="Date").loc[:, ["Close"]]
                df["Volume"] = np.nan
        except requests.RequestException:
            df = pd.DataFrame()

    if df.empty:
        return df

    wk = pd.DataFrame({
        "Close": df["Close"].resample("W-FRI").last(),
        "Volume": df["Volume"].resample("W-FRI").sum(min_count=1),
    }).dropna(subset=["Close"])
    return wk


@st.cache_data(show_spinner=False)
def fetch_fundamentals(tickers: tuple[str, ...]) -> pd.DataFrame:
    """Fetch dividend yield, payout ratio & FCF.

    Handles quirky Yahoo scaling and avoids KeyErrors when data are missing.
    """
    records: list[dict] = []
    for t in tickers:
        try:
            info = yf.Ticker(yf_symbol(t)).info or {}
        except Exception:
            info = {}

        dy_raw = _safe(info.get("dividendYield"))
        pr_raw = _safe(info.get("payoutRatio"))
        fcf_raw = _safe(info.get("freeCashflow"))

        # Dividend yield: some tickers return fraction (<1), others percentage (>1).
        if np.isnan(dy_raw):
            dy_pct = np.nan
        else:
            dy_pct = dy_raw * 100 if dy_raw < 1 else dy_raw

        # Payout ratio is always a fraction per Yahoo docs
        pr_pct = pr_raw * 100 if not np.isnan(pr_raw) else np.nan

        records.append(
            {
                "Ticker": t,
                "Dividend Yield (%)": dy_pct,
                "Dividend Payout Ratio (%)": pr_pct,
                "Free Cash Flow (LC m)": fcf_raw / 1e6 if not np.isnan(fcf_raw) else np.nan,
            }
        )

    df = pd.DataFrame.from_records(records)
    if "Ticker" in df.columns:
        df = df.set_index("Ticker").sort_index()
    return df.set_index("Ticker").set_index("Ticker")


# ════════════════════════════════════════════════════════════════
# Technical metrics per‑ticker
# ════════════════════════════════════════════════════════════════

def tech_metrics(df: pd.DataFrame) -> dict:
    """Return metrics including previous values for table display."""
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    ma10 = df["Close"].rolling(10).mean()
    ma20 = df["Close"].rolling(20).mean()

    prev_ma10 = ma10.iloc[-2] if len(df) > 1 else np.nan

    signal = "Buy" if ma10.iloc[-1] > ma20.iloc[-1] else "Sell"
    crossover = "Above" if latest.Close > ma20.iloc[-1] else "Below"
    divergence = (
        "Overbought" if latest.Close >= ma10.iloc[-1] * 1.1 else (
            "Oversold" if latest.Close <= ma10.iloc[-1] * 0.9 else "OK")
    )

    return {
        "Price": latest.Close,
        "MA10": ma10.iloc[-1],
        "MA20": ma20.iloc[-1],
        "% vs MA10": (latest.Close - ma10.iloc[-1]) / ma10.iloc[-1] * 100,
        "Volume": latest.Volume,
        "Vol MA10": df["Volume"].rolling(10).mean().iloc[-1],
        "Signal": signal,
        "Last Updated": latest.name.strftime("%m/%d/%Y"),
        "Crossover": crossover,
        "Divergence": divergence,
        "Prev Price": prev.Close,
        "Prev MA10": prev_ma10,
    }


# ════════════════════════════════════════════════════════════════
# Streamlit UI
# ════════════════════════════════════════════════════════════════

def main():
    st.set_page_config(page_title="Defense Sector: Weekly Signal Dashboard", layout="wide")
    st.markdown("## :shield: Defense Sector: Weekly Signal Dashboard")

    tickers = (
        "ETR:RHM",   # Rheinmetall
        "STO:SAAB-B", # Saab
        "EPA:HO",    # Thales
        "LON:BA",    # BAE Systems
        "BIT:LDO",   # Leonardo
    )

    show_table = st.checkbox("Show All Tickers Table", True)
    sel = st.selectbox("Select a Ticker to View Chart", tickers)

    fund = fetch_fundamentals(tickers)

    tech = {t: tech_metrics(fetch_weekly_ohlcv(t)) for t in tickers}
    tech_df = pd.DataFrame.from_dict(tech, orient="index")

    table = pd.concat([tech_df, fund], axis=1).round(2)

    if show_table:
        st.subheader(":bar_chart: All Tickers – Technical & Fundamental Metrics")
        st.dataframe(
            table.style.apply(lambda s: ["background-color:#FFEB3B" if x == s.max() else "" for x in s],
                               subset=["Dividend Yield (%)", "Dividend Payout Ratio (%)"]),
            use_container_width=True,
        )

    # ─── chart ───
    df_chart = fetch_weekly_ohlcv(sel)
    if df_chart.empty:
        st.warning("Price data not available for the selected ticker.")
    else:
        plot = df_chart.copy()
        plot["MA10"] = plot["Close"].rolling(10).mean()
        plot["MA20"] = plot["Close"].rolling(20).mean()
        st.subheader(f":chart_with_upwards_trend: Weekly Price Chart: {sel}")
        st.line_chart(plot[["Close", "MA10", "MA20"]])


if __name__ == "__main__":
    main()
