import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import plotly.graph_objs as go
import io

FRED_API_KEY = "a79018b53e3085363528cf148b358708"
FRED_SERIES = {
    "Fed BS": "WALCL",
    "TGA": "WTREGEN",
    "RRP": "RRPONTSYD"
}

def fetch_fred_series(series_id, start_date):
    url = f"https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": start_date,
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    obs = r.json()['observations']
    data = {o['date']: float(o['value']) if o['value'] not in ['.', None] else None for o in obs}
    return data

def get_weekly_liquidity_data(start_date="2021-08-05"):
    data = {}
    for name, series_id in FRED_SERIES.items():
        data[name] = fetch_fred_series(series_id, start_date)
    all_dates = sorted(set(data['Fed BS'].keys()) | set(data['TGA'].keys()) | set(data['RRP'].keys()))
    # Only keep Fridays
    output = []
    for d in all_dates:
        date_obj = datetime.strptime(d, "%Y-%m-%d")
        if date_obj.weekday() == 4: # Friday
            bs = data['Fed BS'].get(d, 0)
            tga = data['TGA'].get(d, 0)
            rrp = data['RRP'].get(d, 0)
            netliq = bs - tga - rrp
            output.append([d, bs, tga, rrp, netliq])
    return pd.DataFrame(output, columns=['Date','Fed BS','TGA','RRP','Net Liquidity'])

def align_to_friday(reference_dates, align_df, value_col):
    # Make a dict of date->value for fast lookup
    align_map = {pd.to_datetime(r['Date']).date(): r[value_col] for _, r in align_df.iterrows()}
    result = []
    for d in reference_dates:
        ref_dt = pd.to_datetime(d).date()
        val = align_map.get(ref_dt, None)
        result.append(val)
    return result

def align_btc_to_friday(friday_dates, btc_df):
    # BTC closes are for Saturdays; for Friday 2021-08-06, want BTC close from 2021-08-07
    btc_map = {pd.to_datetime(r['Date']).date(): r['Close'] for _, r in btc_df.iterrows()}
    result = []
    for d in friday_dates:
        dt = pd.to_datetime(d).date() + timedelta(days=1)
        result.append(btc_map.get(dt, None))
    return result

st.title("US Liquidity Monitor (FRED, BTC, NASDAQ, SPX)")

uploaded_file = st.file_uploader("Upload your Excel (.xlsx) for custom BTC or NASDAQ/SPX data (optional):", type=["xlsx"])

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    btc_df = pd.read_excel(xls, "Bitcoin")
    nasdaqspx_df = pd.read_excel(xls, "NASDAQ_SPX")
else:
    # Use bundled example demo data (from your file for the demo; in real deployment, provide static example or blank)
    btc_df = pd.read_excel("/mnt/data/Liquidity-Focused US (1).xlsx", "Bitcoin")
    nasdaqspx_df = pd.read_excel("/mnt/data/Liquidity-Focused US (1).xlsx", "NASDAQ_SPX")

st.subheader("Downloading latest weekly FRED liquidity data...")
liq_df = get_weekly_liquidity_data()
friday_dates = liq_df["Date"].tolist()

st.subheader("Merging with Bitcoin and Index Data...")
# Align BTC
btc_col = align_btc_to_friday(friday_dates, btc_df)
# Align NASDAQ and SPX
nasdaq_map = {pd.to_datetime(r['Date']).date(): r['NASDAQ'] for _, r in nasdaqspx_df.iterrows()}
spx_map = {pd.to_datetime(r['Date']).date(): r['SPX'] for _, r in nasdaqspx_df.iterrows()}
nasdaq_col = [nasdaq_map.get(pd.to_datetime(d).date(), None) for d in friday_dates]
spx_col = [spx_map.get(pd.to_datetime(d).date(), None) for d in friday_dates]

liq_df['BTC Close'] = btc_col
liq_df['NASDAQ'] = nasdaq_col
liq_df['SPX'] = spx_col

st.dataframe(liq_df)

# Chart Section
st.subheader("Net Liquidity, Bitcoin, and Indexes Over Time")
fig = go.Figure()
fig.add_trace(go.Scatter(x=liq_df['Date'], y=liq_df['Net Liquidity'], mode='lines', name='Net Liquidity'))
fig.add_trace(go.Scatter(x=liq_df['Date'], y=liq_df['BTC Close'], mode='lines', name='BTC Close', yaxis="y2"))
fig.add_trace(go.Scatter(x=liq_df['Date'], y=liq_df['NASDAQ'], mode='lines', name='NASDAQ', yaxis="y3"))
fig.add_trace(go.Scatter(x=liq_df['Date'], y=liq_df['SPX'], mode='lines', name='SPX', yaxis="y4"))
# For simplicity, keep 1 y-axis. For more advanced, use secondary_y, etc.
fig.update_layout(
    title='Liquidity, BTC, and Indexes',
    xaxis_title='Date',
    yaxis_title='Value',
    legend=dict(orientation="h")
)
st.plotly_chart(fig, use_container_width=True)

st.info("You can re-upload your Excel sheet to refresh custom BTC/NASDAQ/SPX data, or deploy as-is to Streamlit Cloud. For advanced features (alerts, downloads, etc.), just ask!")

