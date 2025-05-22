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
    """Turn an 'EXCHANGE:SYMBOL' string into the Yahoo‑Finance‑friendly code."""
    if ":" not in mixed_ticker:
        return mixed_ticker  # already Yahoo format
    exch, symbol = mixed_ticker.split(":", 1)
    suffix_map = {
        "ETR": "DE",  # Frankfurt / Xetra
        "STO": "ST",  # Stockholm
        "EPA": "PA",  # Paris
        "LON": "L",   # London
        "BIT": "MI",  # Milan
    }
    suffix = suffix_map.get(exch.upper())
    return f"{symbol}.{suffix}" if suffix else mixed_ticker


def _safe(val):
    return np.nan if val is None else val


@st.cache_data(show_spinner=False)
def fetch_weekly_ohlcv(ticker: str) -> pd.DataFrame:
    """
    Returns a **weekly‑Friday** OHLCV dataframe (Close + Volume at minimum).
    Falls back to Stooq if Yahoo has no data.
    """
    ysym = yf_symbol(ticker)

    # 1️⃣ primary — Yahoo Finance ------------------------------------------------
    df = (
        yf.Ticker(ysym)
        .history(period="1y", interval="1d")
        .loc[:, ["Close", "Volume"]]
    )

    # 2️⃣ fallback — Stooq (Close only) ----------------------------------------
    if df.empty:
        csv_sym = ysym.split(".")[0].lower()
        url = f"https://stooq.com/q/d/l/?s={csv_sym}&i=d"
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            if "Date" in resp.text:
                df = pd.read_csv(
                    StringIO(resp.text),
                    parse_dates=["Date"],
                    index_col="Date",
                ).loc[:, ["Close"]]
                df["Volume"] = np.nan  # no volume in Stooq daily CSV
        except requests.RequestException:
            df = pd.DataFrame()

    # 3️⃣ consolidate to weekly‑Friday -----------------------------------------
    if df.empty:
        return df

    df = df.sort_index()

    price = df["Close"].resample("W-FRI").last()
    vol = df["Volume"].resample("W-FRI").sum(min_count=1)
    dfw = pd.concat({"Close": price, "Volume": vol}, axis=1).dropna(subset=["Close"])
    return dfw


@st.cache_data(show_spinner=False)
def fetch_fundamentals(tickers: tuple[str, ...]) -> pd.DataFrame:
    """Pull essential valuation & income metrics from Yahoo Finance."""
    rows = []
    for t in tickers:
        info = yf.Ticker(yf_symbol(t)).info or {}
        rows.append(
            {
                "Ticker": t,
                "Dividend Yield (%)": _safe(info.get("dividendYield")) * 100,
                "Dividend Payout Ratio (%)": _safe(info.get("payoutRatio")) * 100,
                "Free Cash Flow (LC m)": _safe(info.get("freeCashflow")) / 1e6,
            }
        )
    return pd.DataFrame(rows).set_index("Ticker")


# ════════════════════════════════════════════════════════════════
# Computations
# ════════════════════════════════════════════════════════════════

def compute_technical_metrics(dfw: pd.DataFrame) -> dict[str, float | str]:
    """Return a dict with the metrics shown in the summary table."""
    latest = dfw.iloc[-1]

    ma10 = dfw["Close"].rolling(10).mean().iloc[-1]
    ma20 = dfw["Close"].rolling(20).mean().iloc[-1]
    vol_ma10 = dfw["Volume"].rolling(10).mean().iloc[-1]

    crossover = "Above" if latest.Close > ma20 else "Below"
    divergence = (
        "Overbought" if latest.Close >= ma10 * 1.1 else ("Oversold" if latest.Close <= ma10 * 0.9 else "OK")
    )
    signal = "Buy" if ma10 > ma20 else "Sell"

    return {
        "Price": latest.Close,
        "MA10": ma10,
        "MA20": ma20,
        "% vs MA10": (latest.Close - ma10) / ma10 * 100,
        "Volume": latest.Volume,
        "Vol MA10": vol_ma10,
        "Signal": signal,
        "Last Updated": latest.name.strftime("%m/%d/%Y"),
        "Crossover": crossover,
        "Divergence": divergence,
    }


# ════════════════════════════════════════════════════════════════
# Streamlit UI
# ════════════════════════════════════════════════════════════════

def main() -> None:
    st.set_page_config(page_title="Defense Sector: Weekly Signal Dashboard", layout="wide")

    st.title("🛡️ Defense Sector: Weekly Signal Dashboard")

    tickers = (
        "ETR:RHM",   # Rheinmetall
        "STO:SAAB-B", # Saab AB B‑shares
        "EPA:HO",    # Thales
        "LON:BA",    # BAE Systems
        "BIT:LDO",   # Leonardo
    )

    # ─── Controls ────────────────────────────────────────────────
    show_table = st.checkbox("Show All Tickers Table", value=True)
    selected = st.selectbox("Select a Ticker to View Chart", tickers, index=0)

    # ─── Core data pulls (cached) ────────────────────────────────
    fund_df = fetch_fundamentals(tickers)

    tech_rows = {}
    for t in tickers:
        dfw = fetch_weekly_ohlcv(t)
        tech_rows[t] = compute_technical_metrics(dfw) if not dfw.empty else {}

    tech_df = pd.DataFrame.from_dict(tech_rows, orient="index")

    full_df = pd.concat([tech_df, fund_df], axis=1).round(2)
    full_df = full_df.reindex(columns=[
        "Price", "MA10", "MA20", "% vs MA10", "Volume", "Vol MA10", "Signal", "Last Updated",
        "Crossover", "Divergence", "Prev Price", "Prev MA10",  # placeholders to match screenshot
        "Dividend Yield (%)", "Dividend Payout Ratio (%)", "Free Cash Flow (LC m)",
    ])

    # highlight big dividend/yield columns
    def _highlight(series: pd.Series):
        return ["background-color: #FFEB3B" if not pd.isna(x) and x == series.max() else "" for x in series]

    if show_table:
        st.subheader("📊 All Tickers – Technical & Fundamental Metrics")
        st.dataframe(
            full_df.style.apply(_highlight, subset=["Dividend Yield (%)", "Dividend Payout Ratio (%)"]),
            use_container_width=True,
        )

    # ─── Chart ───────────────────────────────────────────────────
    df_sel = fetch_weekly_ohlcv(selected)
    if df_sel.empty:
        st.warning("No price data available for the selected ticker.")
    else:
        dfp = df_sel.copy()
        dfp["MA10"] = dfp["Close"].rolling(10).mean()
        dfp["MA20"] = dfp["Close"].rolling(20).mean()
        st.subheader(f"📈 Weekly Price Chart: {selected}")
        st.line_chart(dfp[["Close", "MA10", "MA20"]])


if __name__ == "__main__":
    main()
