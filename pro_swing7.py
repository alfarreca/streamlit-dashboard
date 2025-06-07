import streamlit as st
import pandas as pd
import yfinance as yf
from ta import add_all_ta_features
import time
import matplotlib.pyplot as plt
import numpy as np
import requests

import socket
from requests.exceptions import HTTPError, ConnectionError, Timeout

def clean_tickers(ticker_list):
    return (
        pd.Series(ticker_list)
        .dropna()
        .astype(str)
        .str.replace(r'^"|"$', '', regex=True)
        .str.strip()
        .str.upper()
        .unique()
        .tolist()
    )

def get_stock_data(data, ticker):
    if ticker not in data or data[ticker].empty or len(data[ticker]) < 2:
        return pd.DataFrame()
    df = data[ticker].copy()
    min_rows = 15
    if len(df) < min_rows:
        return pd.DataFrame()
    try:
        df = add_all_ta_features(
            df, open="Open", high="High", low="Low", close="Close", volume="Volume"
        )
        if 'trend_macd' in df and 'trend_macd_signal' in df:
            macd = df['trend_macd']
            signal = df['trend_macd_signal']
            macd_prev = macd.shift(1)
            signal_prev = signal.shift(1)
            df['macd_cross'] = np.where(
                (macd_prev < signal_prev) & (macd > signal), 'cross up',
                np.where((macd_prev > signal_prev) & (macd < signal), 'cross down', '')
            )
    except Exception as e:
        st.warning(f"TA error for {ticker}: {e}")
        return pd.DataFrame()
    return df

def calculate_opportunity_score(data):
    if data.empty:
        return 0
    rsi = data['momentum_rsi'].iloc[-1] if 'momentum_rsi' in data else float('nan')
    macd = data['trend_macd_diff'].iloc[-1] if 'trend_macd_diff' in data else float('nan')
    bbp = data['volatility_bbp'].iloc[-1] if 'volatility_bbp' in data else float('nan')
    score = 0
    if not pd.isna(rsi):
        score += (100 - abs(rsi - 50)) * 0.5
    if not pd.isna(macd):
        score += (macd * 100) * 0.25
    if not pd.isna(bbp):
        score += (100 - abs(bbp - 0.5) * 200) * 0.25
    return round(score, 1)

def generate_strategy(data):
    entry, exit = [], []
    stop_loss, take_profit = None, None
    if not data.empty:
        rsi = data['momentum_rsi'].iloc[-1] if 'momentum_rsi' in data else None
        macd = data['trend_macd_diff'].iloc[-1] if 'trend_macd_diff' in data else None
        bbp = data['volatility_bbp'].iloc[-1] if 'volatility_bbp' in data else None
        close = data['Close'].iloc[-1]
        if rsi is not None:
            if rsi < 35: entry.append(f"RSI ({rsi:.1f}) < 35 (Oversold)")
            elif rsi > 65: entry.append(f"RSI ({rsi:.1f}) > 65 (Overbought)")
        if macd is not None:
            entry.append("MACD positive" if macd > 0 else "MACD negative")
        if bbp is not None:
            if bbp < 0.2: entry.append("Price near lower Bollinger Band")
            elif bbp > 0.8: entry.append("Price near upper Bollinger Band")
        if rsi is not None:
            if rsi < 30 or rsi > 70: exit.append(f"RSI crosses {'40' if rsi<30 else '60'}")
        exit.append("MACD crosses signal line (opp. dir)")
        atr = data['volatility_atr'].iloc[-1] if 'volatility_atr' in data else None
        if atr is not None:
            stop_loss = f"{close - atr * 1.5:.2f} (1.5x ATR)"
            take_profit = f"{close + atr * 3:.2f} (3x ATR)"
    return {
        'entry_rules': entry,
        'exit_rules': exit,
        'stop_loss': stop_loss,
        'take_profit': take_profit
    }

def download_with_retry(tickers, period, interval='1d', max_retries=3, sleep_base=1):
    for attempt in range(max_retries):
        try:
            batch_data = yf.download(
                tickers=tickers, period=period, interval=interval, group_by="ticker", timeout=15, threads=True
            )
            if isinstance(batch_data.columns, pd.MultiIndex):
                batch_data = batch_data.swaplevel(axis=1)
            return batch_data, None
        except (socket.timeout, Timeout, ConnectionError) as e:
            err = f"Network error: {e}"
        except HTTPError as e:
            err = f"HTTP error: {e}"
        except Exception as e:
            err = f"Other error: {e}"
        time.sleep(sleep_base * (2 ** attempt))  # exponential backoff
    return None, err

def scan_universe_batched(universe, period='6mo', batch_size=500):
    results = []
    failed = []
    failed_details = {}
    total = len(universe)
    with st.spinner(f"Scanning {total} stocks in batches of {batch_size}..."):
        progress_bar = st.progress(0)
        for batch_start in range(0, total, batch_size):
            batch_end = min(batch_start + batch_size, total)
            batch = universe[batch_start:batch_end]
            batch_data, batch_error = download_with_retry(batch, period)
            if batch_data is None:
                st.warning(f"Batch yfinance download failed: {batch_error}")
                for ticker in batch:
                    failed.append(ticker)
                    failed_details[ticker] = batch_error
                continue
            for i, ticker in enumerate(batch):
                st.write(f"Batch {batch_start//batch_size+1} | Processing ticker {i+1+batch_start} / {total}: {ticker}")
                try:
                    data = get_stock_data(batch_data, ticker)
                    if not data.empty:
                        score = calculate_opportunity_score(data)
                        strategy = generate_strategy(data)
                        if score is not None and strategy is not None:
                            results.append({
                                'Ticker': ticker,
                                'Score': score,
                                'Price': data['Close'].iloc[-1],
                                'Change %': (data['Close'].iloc[-1] / data['Close'].iloc[-2] - 1) * 100,
                                'Volume': data['Volume'].iloc[-1],
                                'RSI': data['momentum_rsi'].iloc[-1] if 'momentum_rsi' in data else float('nan'),
                                'MACD': data['trend_macd_diff'].iloc[-1] if 'trend_macd_diff' in data else float('nan'),
                                'MACD Cross': data['macd_cross'].iloc[-1] if 'macd_cross' in data else '',
                                'BB %': data['volatility_bbp'].iloc[-1] * 100 if 'volatility_bbp' in data else float('nan'),
                                'Strategy': strategy
                            })
                    else:
                        failed.append(ticker)
                        failed_details[ticker] = "No valid data returned or not enough rows."
                except Exception as e:
                    st.warning(f"Error processing {ticker}: {str(e)}")
                    failed.append(ticker)
                    failed_details[ticker] = str(e)
                progress = (batch_start + i + 1) / total
                progress_bar.progress(progress)
                time.sleep(0.01)
    if not results:
        return pd.DataFrame(columns=['Ticker', 'Score', 'Price', 'Change %', 'Volume', 'RSI', 'MACD', 'MACD Cross', 'BB %', 'Strategy']), failed, failed_details
    return pd.DataFrame(results).sort_values('Score', ascending=False), failed, failed_details

# --- rest of your script below ---

# Replace calls to scan_universe_batched to handle the new return signature!
# For example:
# results, failed, failed_details = scan_universe_batched(...)

# When displaying failed tickers, also show error details:
# with st.expander("Show Failed Tickers"):
#     for t in st.session_state.failed_tickers:
#         st.write(f"{t}: {st.session_state.failed_details.get(t, '')}")

# The rest of your code (from st.set_page_config onward) remains the same, just update how you receive and display the failed tickers and details.
