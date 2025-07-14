import streamlit as st
import pandas as pd
import yfinance as yf

st.title("📊 Yahoo Finance Ticker Checker + Thematic Tags")

# ✅ Updated theme_map including new tickers
theme_map = {
    # AI & Chips
    "NVDA": "AI/Chips", "AMD": "AI/Chips", "AVGO": "AI/Chips",
    "PLTR": "AI/Defense", "TSLA": "EV/AI", "GOOGL": "AI/Cloud",
    "MSFT": "AI/Cloud", "META": "AI/AR/VR", "SNOW": "AI/Cloud", "AI": "AI Software",

    # Defense
    "LMT": "Defense", "NOC": "Defense", "RTX": "Defense",
    "AVAV": "Drone Makers", "BA": "Defense/Aerospace", "ELBIT.TA": "Defense/Israel",

    # Supply Chain
    "MP": "Supply Chain", "LTHM": "Battery Materials", "ALB": "Battery Materials",
    "LIN": "Industrial Gases", "ASML": "Semiconductor Equipment",

    # Gold & Commodities
    "GOLD": "Gold Miners", "HMY": "Gold Miners", "AEM": "Gold Miners",
    "NEM": "Gold Miners", "SBSW": "Precious Metals", "FCX": "Copper", "RIO": "Diversified Mining",

    # EVs & Energy
    "BYDDF": "EV/China", "NIO": "EV/China", "ENPH": "Solar/Clean Tech",
    "SEDG": "Solar/Clean Tech", "CHPT": "EV Charging", "FSLR": "Solar", "BLNK": "EV Charging",

    # E-Commerce
    "AMZN": "E-Commerce", "SHOP": "E-Commerce", "MELI": "LatAm E-Commerce",
    "JD": "China Tech", "BABA": "China Tech", "PDD": "China Tech",
    "SE": "SE Asia Tech", "WMT": "Retail", "TGT": "Retail",

    # LatAm & EM
    "BZ": "LatAm", "VALE": "LatAm/Commodities", "PAGS": "LatAm Fintech",
    "EPU": "Peru ETF", "EWZ": "Brazil ETF", "FM": "Frontier Markets ETF",

    # Agri
    "DE": "AgTech", "MOS": "Fertilizers", "NTR": "Fertilizers",
    "ADM": "Ag Supply", "BG": "Ag Supply",

    # Finance
    "JPM": "Big Banks", "GS": "Investment Banks", "MS": "Investment Banks",
    "AXP": "Credit/Payments", "PYPL": "Payments", "SQ": "Fintech",

    # Crypto
    "COIN": "Crypto Exchange", "MARA": "Crypto Miners", "RIOT": "Crypto Miners",
    "HUT": "Crypto Miners", "BITF": "Crypto Miners", "GLXY.TO": "Crypto/Canada",

    # Industrials
    "GE": "Industrial", "HON": "Industrial", "ETN": "Electrification", "CAT": "Heavy Equipment",

    # Newly Added from Web
    "BKSY": "Space Tech / Geospatial Intelligence",
    "PL": "Space Tech / Earth Observation",
    "PLS.AX": "Battery Materials / EV Supply Chain",
}

# 📤 Upload
uploaded = st.file_uploader("Upload your watchlist (CSV or Excel)", type=["csv", "xlsx"])

if uploaded:
    df = pd.read_csv(uploaded) if uploaded.name.endswith('.csv') else pd.read_excel(uploaded)
    st.write("Preview:", df.head())

    # Auto-detect ticker column
    ticker_col = next((col for col in df.columns if 'ticker' in col.lower() or 'symbol' in col.lower()), None)
    if not ticker_col:
        ticker_col = st.selectbox("Select ticker column:", df.columns)

    st.write(f"🧠 Checking tickers from: **{ticker_col}**")

    # Add missing columns
    for col in ['Exists_on_Yahoo', 'Yahoo_Exchange', 'Yahoo_Name', 'Yahoo_Sector', 'Yahoo_Industry', 'Yahoo_Country', 'Theme']:
        if col not in df.columns:
            df[col] = ''

    # 🎯 Fill missing Themes first
    df['Theme'] = df.apply(
        lambda r: theme_map.get(r[ticker_col].upper(), r['Theme']) 
        if pd.isna(r['Theme']) or r['Theme'] == '' else r['Theme'], axis=1
    )

    # Run Yahoo Finance check
    if st.button("🔍 Enrich with Yahoo Finance"):
        prog = st.progress(0)
        total = len(df)
        results = []

        for i, ticker in enumerate(df[ticker_col]):
            try:
                tk = yf.Ticker(str(ticker))
                info = tk.info
                if 'longName' in info or 'shortName' in info:
                    exists = True
                    exchange = info.get('exchange', '')
                    name = info.get('longName', info.get('shortName', ''))
                    sector = info.get('sector', '')
                    industry = info.get('industry', '')
                    country = info.get('country', '')
                else:
                    exists = False
                    exchange = name = sector = industry = country = ''
            except Exception:
                exists = False
                exchange = name = sector = industry = country = ''

            results.append((exists, exchange, name, sector, industry, country))
            prog.progress((i + 1) / total)

        df['Exists_on_Yahoo'], df['Yahoo_Exchange'], df['Yahoo_Name'], df['Yahoo_Sector'], df['Yahoo_Industry'], df['Yahoo_Country'] = zip(*results)
        st.success("✅ Data enrichment complete.")
        st.dataframe(df)

        # Offer download
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("⬇ Download Enriched Watchlist", csv, "Enriched_Watchlist.csv", "text/csv")
else:
    st.info("📥 Upload a CSV or Excel file with ticker symbols to begin.")
