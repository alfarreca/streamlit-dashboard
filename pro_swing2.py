import yfinance as yf
import pandas as pd
from ta import add_all_ta_features

def fetch_and_flatten_ticker(ticker, period='6mo', interval='1d'):
    # Download data
    df = yf.download(ticker, period=period, interval=interval, group_by='ticker')
    debug_info = {}
    debug_info['raw_shape'] = df.shape
    debug_info['raw_columns'] = str(df.columns)

    # If DataFrame is MultiIndex (from yfinance), flatten it
    if isinstance(df.columns, pd.MultiIndex):
        if ticker.upper() in [c[1] for c in df.columns]:
            df = df.xs(ticker.upper(), axis=1, level=1, drop_level=True)
            debug_info['flattened'] = f'Flattened MultiIndex using {ticker.upper()}'
        elif ticker.lower() in [c[1].lower() for c in df.columns]:
            # Case-insensitive fallback
            col_map = {c: c[0] for c in df.columns if c[1].lower() == ticker.lower()}
            df = df[list(col_map.keys())]
            df.columns = list(col_map.values())
            debug_info['flattened'] = f'Flattened MultiIndex using fallback {ticker}'
        else:
            debug_info['flattened'] = 'MultiIndex present but ticker not found in columns.'
    else:
        debug_info['flattened'] = 'No MultiIndex, already flat'

    # Check for missing or malformed data
    if df.empty or not set(['Open', 'High', 'Low', 'Close', 'Volume']).issubset(df.columns):
        debug_info['error'] = 'Missing OHLCV columns after flattening'
        return pd.DataFrame(), debug_info

    # Add TA features (with try-except for extra safety)
    try:
        df_ta = add_all_ta_features(df, open="Open", high="High", low="Low", close="Close", volume="Volume")
        debug_info['ta_shape'] = df_ta.shape
        return df_ta, debug_info
    except Exception as e:
        debug_info['error'] = f"TA error: {e}"
        return df, debug_info
