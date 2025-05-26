import pandas as pd
from datetime import datetime, timedelta
import textwrap

# Construct the full Streamlit script
script = textwrap.dedent("""
    import streamlit as st
    import pandas as pd
    import yfinance as yf
    from datetime import datetime

    # --- LOAD WATCHLIST FROM GOOGLE SHEETS ---
    @st.cache_data(show_spinner=False)
    def load_watchlist():
        url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRe5_juKpIbiTy7fc92QICvpGhawvqKZWDxmrgUTFNtFjNsCPA10e-wt0UJ4eZ-3tlF5Ol55g-U9wke/pub?output=csv"
        df = pd.read_csv(url)
        df = df.dropna(subset=["Symbol", "Exchange"])
        return df

    # --- METRICS CALCULATION ---
    def fetch_metrics(tickers):
        results = []
        for symbol in tickers:
            try:
                exchange = exchange_map.get(symbol, "")
                yf_symbol = f"{symbol}.{exchange_suffix(exchange)}" if exchange_suffix(exchange) else symbol
                data = yf.Ticker(yf_symbol).history(period="6mo", interval="1d")

                if len(data) < 20:
                    continue

                ma10 = data["Close"].rolling(10).mean().iloc[-1]
                ma20 = data["Close"].rolling(20).mean().iloc[-1]
                last_price = data["Close"].iloc[-1]
                volume = data["Volume"].iloc[-1]
                vol_ma10 = data["Volume"].rolling(10).mean().iloc[-1]
                signal = "Buy" if last_price > ma10 else "Sell"
                crossover = "Above" if last_price > ma20 else "Below"
                divergence = "Overbought" if last_price > ma20 * 1.1 else "OK"
                pct_vs_ma10 = 100 * (last_price - ma10) / ma10
                last_updated = data.index[-1].strftime("%Y-%m-%d")

                results.append({
                    "Ticker": symbol,
                    "Price": round(last_price, 2),
                    "MA10": round(ma10, 2),
                    "MA20": round(ma20, 2),
                    "% vs MA10": round(pct_vs_ma10, 2),
                    "Volume": int(volume),
                    "Vol MA10": int(vol_ma10),
                    "Signal": signal,
                    "Last Updated": last_updated,
                    "Crossover": crossover,
                    "Divergence": divergence
                })
            except Exception as e:
                st.warning(f"Failed to load: {symbol} ({e})")
        return pd.DataFrame(results)

    def exchange_suffix(ex: str) -> str:
        suffix_map = {
            "ETR": "DE", "EPA": "PA", "LON": "L", "BIT": "MI", "STO": "ST",
            "SWX": "SW", "TSE": "TO", "ASX": "AX", "HKG": "HK"
        }
        return suffix_map.get(ex.upper(), "")

    # --- MAIN APP ---
    st.set_page_config(layout="wide")
    st.title("📊 Global Defense & AI Stock Dashboard")

    watchlist = load_watchlist()
    symbols = watchlist["Symbol"].tolist()
    exchange_map = dict(zip(watchlist["Symbol"], watchlist["Exchange"]))

    # Ticker input
    default = "TSLA"
    user_input = st.text_input("Enter tickers (space or comma separated):", value=default)
    user_tickers = list(filter(None, [s.strip().upper() for s in user_input.replace(",", " ").split()]))

    if st.button("Load Tickers"):
        if user_tickers:
            df = fetch_metrics(user_tickers)
            st.markdown("### 📊 All Metrics")
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("Please enter at least one ticker.")
""")

# Save script to file
output_path = "/mnt/data/streamlit_all_metrics_dashboard.py"
with open(output_path, "w") as f:
    f.write(script)

output_path
