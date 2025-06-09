import yfinance as yf
import pandas as pd
import numpy as np

def calculate_momentum(hist):
    if hist.empty or len(hist) < 50:
        return None

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

    def calculate_di_crossovers(hist, period=14):
        high = hist['High']
        low = hist['Low']
        close = hist['Close']
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0)
        minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0)
        tr1 = high - low
        tr2 = np.abs(high - close.shift())
        tr3 = np.abs(low - close.shift())
        tr = np.maximum.reduce([tr1, tr2, tr3])
        atr = pd.Series(tr).rolling(window=period, min_periods=period).mean()
        plus_di = 100 * pd.Series(plus_dm).rolling(window=period, min_periods=period).mean() / atr
        minus_di = 100 * pd.Series(minus_dm).rolling(window=period, min_periods=period).mean() / atr
        bullish_crossover = (plus_di > minus_di) & (plus_di.shift(1) <= minus_di.shift(1))
        bearish_crossover = (minus_di > plus_di) & (minus_di.shift(1) <= plus_di.shift(1))
        return plus_di, minus_di, bullish_crossover, bearish_crossover

    plus_di_c, minus_di_c, bullish_cross, bearish_cross = calculate_di_crossovers(hist)
    last_bullish = bool(bullish_cross.iloc[-1]) if not bullish_cross.empty else False
    last_bearish = bool(bearish_cross.iloc[-1]) if not bearish_cross.empty else False

    score = 0
    if close.iloc[-1] > ema20 > ema50 > ema200:
        score += 30
    elif close.iloc[-1] > ema50 > ema200:
        score += 20
    elif close.iloc[-1] > ema200:
        score += 10

    if 60 <= rsi < 80:
        score += 20
    elif 50 <= rsi < 60 or 80 <= rsi <= 90:
        score += 10

    if macd_hist > 0 and macd_line_above_signal:
        score += 15

    if volume_ratio > 1.5:
        score += 15
    elif volume_ratio > 1.2:
        score += 10

    if adx > 30:
        score += 20
    elif adx > 25:
        score += 15
    elif adx > 20:
        score += 10

    if last_bullish:
        score += 10
    if last_bearish:
        score -= 10

    score = max(0, min(100, score))
    return score

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

if __name__ == "__main__":
    tickers = ["FCX", "NUE", "RIO.L"]  # Replace with your list
    all_results = []

    for t in tickers:
        print(f"Backtesting {t}...")
        df = backtest_ticker(t)
        if df is not None:
            all_results.append(df)

    final_df = pd.concat(all_results, ignore_index=True)
    final_df.to_csv("momentum_backtest_results.csv", index=False)
    print("Backtest completed. Results saved to 'momentum_backtest_results.csv'")
