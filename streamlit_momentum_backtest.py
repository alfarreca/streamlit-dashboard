
import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime

# ========== Momentum Score Function ==========
def calculate_momentum(hist):
    if hist.empty or len(hist) < 50:
        return 0
    close = hist['Close']
    high = hist['High']
    low = hist['Low']
    volume = hist['Volume']
    ema20 = close.ewm(span=20).mean().iloc[-1]
    ema50 = close.ewm(span=50).mean().iloc[-1]
    ema200 = close.ewm(span=200).mean().iloc[-1]
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14).mean().iloc[-1]
    avg_loss = loss.ewm(alpha=1/14).mean().iloc[-1]
    rs = avg_gain / avg_loss if avg_loss != 0 else 100
    rsi = 100 - (100 / (1 + rs))
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9).mean()
    macd_hist = macd.iloc[-1] - macd_signal.iloc[-1]
    macd_line_above_signal = macd.iloc[-1] > macd_signal.iloc[-1]
    vol_avg_20 = volume.rolling(20).mean().iloc[-1]
    volume_ratio = volume.iloc[-1] / vol_avg_20 if vol_avg_20 != 0 else 1
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    plus_dm = high.diff().where(lambda x: (x > 0) & (x > low.diff().abs()), 0)
    minus_dm = (-low.diff()).where(lambda x: (x > 0) & (x > high.diff().abs()), 0)
    plus_di = 100 * (plus_dm.rolling(14).sum() / atr)
    minus_di = 100 * (minus_dm.rolling(14).sum() / atr)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.rolling(14).mean().iloc[-1] if not dx.isnull().all() else dx.mean()
    score = 0
    if close.iloc[-1] > ema20 > ema50 > ema200: score += 30
    elif close.iloc[-1] > ema50 > ema200: score += 20
    elif close.iloc[-1] > ema200: score += 10
    if 60 <= rsi < 80: score += 20
    elif 50 <= rsi < 60 or 80 <= rsi <= 90: score += 10
    if macd_hist > 0 and macd_line_above_signal: score += 15
    if volume_ratio > 1.5: score += 15
    elif volume_ratio > 1.2: score += 10
    if adx > 30: score += 20
    elif adx > 25: score += 15
    elif adx > 20: score += 10
    return min(score, 100)

# ========== Backtest Function ==========
def backtest_ticker(ticker_symbol, threshold=80, holding_days=[5, 10, 20]):
    hist = yf.Ticker(ticker_symbol).history(period="6mo")
    if hist.empty or len(hist) < max(holding_days) + 50:
        return None
    results = []
    for i in range(50, len(hist) - max(holding_days)):
        window = hist.iloc[:i+1]
        score = calculate_momentum(window)
        if score >= threshold:
            entry_date = window.index[-1]
            entry_price = window["Close"].iloc[-1]
            entry_result = {
                "Date": entry_date.date(),
                "Ticker": ticker_symbol,
                "Entry_Price": round(entry_price, 2),
                "Momentum_Score": score
            }
            for h in holding_days:
                if i + h < len(hist):
                    exit_price = hist["Close"].iloc[i + h]
                    ret = (exit_price - entry_price) / entry_price
                    entry_result[f"Return_{h}D"] = round(ret * 100, 2)
            results.append(entry_result)
    return pd.DataFrame(results)

# ========== Streamlit App ==========
st.set_page_config(page_title="Momentum Backtest", layout="wide")
st.title("Momentum Strategy Backtest")

tickers_input = st.text_area("Enter comma-separated Yahoo tickers", value="FCX,NUE,RIO.L")
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

threshold = st.slider("Momentum Score Threshold", 0, 100, 80)
holding_days = st.multiselect("Holding Periods (Days)", [5, 10, 20, 30], default=[5, 10, 20])

if st.button("Run Backtest"):
    all_results = []
    progress = st.progress(0)
    for i, t in enumerate(tickers):
        st.write(f"Backtesting {t}...")
        df = backtest_ticker(t, threshold, holding_days)
        if df is not None:
            all_results.append(df)
        progress.progress((i + 1) / len(tickers))
    progress.empty()

    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        st.dataframe(final_df)
        avg_returns = final_df[[c for c in final_df.columns if "Return" in c]].mean().round(2)
        win_rates = (final_df[[c for c in final_df.columns if "Return" in c]] > 0).mean().round(2) * 100
        st.subheader("Performance Summary")
        st.write("Average Returns (%)", avg_returns)
        st.write("Win Rates (%)", win_rates)
        st.download_button("Download Results CSV", final_df.to_csv(index=False), "momentum_backtest.csv")
    else:
        st.warning("No signals met the threshold.")
