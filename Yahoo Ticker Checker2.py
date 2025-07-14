import streamlit as st
import pandas as pd
import yfinance as yf

st.title("📊 Yahoo Finance Ticker Checker + Thematic Tags")

# 🎯 Define hardcoded theme map (extend as needed)
theme_map = {
    # ✅ AI & Semiconductors
    "NVDA": "AI/Chips",
    "AMD": "AI/Chips",
    "AVGO": "AI/Chips",
    "PLTR": "AI/Defense",
    "TSLA": "EV/AI",
    "GOOGL": "AI/Cloud",
    "MSFT": "AI/Cloud",
    "META": "AI/AR/VR",
    "SNOW": "AI/Cloud",
    "AI": "AI Software",

    # ✅ Defense & Security
    "LMT": "Defense",
    "NOC": "Defense",
    "RTX": "Defense",
    "AVAV": "Drone Makers",
    "BA": "Defense/Aerospace",
    "ELBIT.TA": "Defense/Israel",

    # ✅ Supply Chain & Rare Earths
    "MP": "Supply Chain",
    "LTHM": "Supply Chain/Battery Materials",
    "ALB": "Battery Materials",
    "LIN": "Industrial Gases/Supply Chain",
    "ASML": "Semiconductor Equipment",

    # ✅ Gold & Commodities
    "GOLD": "Gold Miners",
    "HMY": "Gold Miners",
    "AEM": "Gold Miners",
    "NEM": "Gold Miners",
    "SBSW": "Precious Metals",
    "FCX": "Copper",
    "RIO": "Diversified Mining",

    # ✅ EVs & Clean Energy
    "BYDDF": "EV/China",
    "NIO": "EV/China",
    "ENPH": "Solar/Clean Tech",
    "SEDG": "Solar/Clean Tech",
    "CHPT": "EV Charging",
    "FSLR": "Solar",
    "BLNK": "EV Charging",

    # ✅ E-Commerce & Consumer
    "AMZN": "E-Commerce",
    "SHOP": "E-Commerce",
    "MELI": "LatAm E-Commerce",
    "JD": "China Tech",
    "BABA": "China Tech",
    "PDD": "China Tech",
    "SE": "SE Asia Tech",
    "WMT": "Retail",
    "TGT": "Retail",

    # ✅ LatAm & Emerging Markets
    "BZ": "LatAm",
    "VALE": "LatAm/Commodities",
    "PAGS": "LatAm Fintech",
    "EPU": "Peru ETF",
    "EWZ": "Brazil ETF",
    "FM": "Frontier Markets ETF",

    # ✅ Agriculture
    "DE": "AgTech",
    "MOS": "Fertilizers",
    "NTR": "Fertilizers",
    "ADM": "Ag Supply",
    "BG": "Ag Supply",

    # ✅ Financials
    "JPM": "Big Banks",
    "GS": "Investment Banks",
    "MS": "Investment Banks",
    "AXP": "Credit/Payments",
    "PYPL": "Payments",
    "SQ": "Fintech",

    # ✅ Crypto & Blockchain Exposure
    "COIN": "Crypto Exchange",
    "MARA": "Crypto Miners",
    "RIOT": "Crypto Miners",
    "HUT": "Crypto Miners",
    "BITF": "Crypto Miners",
    "GLXY.TO": "Crypto/Canada",

    # ✅ Industrial Tech
    "GE": "Industrial",
    "HON": "Industrial",
    "ETN": "Electrification",
    "CAT": "Heavy Equipment",
}

uploaded = st.file_uploader("Upload your ticker list (CSV or Excel)", type=["csv", "xlsx"])

if uploaded:
    if uploaded.name.endswith('.csv'):
        df = pd.read_csv(uploaded)
    else:
        df = pd.read_excel(uploaded)
    st.write("Preview:", df.head())

    # Try to auto-detect ticker column
    ticker_col = None
    for col in df.columns:
        if 'ticker' in col.lower():
            ticker_col = col
            break
    if not ticker_col:
        ticker_col = st.selectbox("Select ticker column:", df.columns)

    st.write(f"🔎 Checking Yahoo Finance for tickers in column: **{ticker_col}**")
    df['Exists_on_Yahoo'] = False
    df['Yahoo_Exchange'] = ''
    df['Yahoo_Name'] = ''
    df['Yahoo_Sector'] = ''
    df['Yahoo_Industry'] = ''
    df['Yahoo_Country'] = ''
    df['Theme'] = ''

    if st.button("Check Yahoo Finance"):
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
                    exchange = ''
                    name = ''
                    sector = ''
                    industry = ''
                    country = ''
            except Exception:
                exists = False
                exchange = ''
                name = ''
                sector = ''
                industry = ''
                country = ''
            theme = theme_map.get(str(ticker).upper(), '')
            results.append((exists, exchange, name, sector, industry, country, theme))
            prog.progress((i + 1) / total)

        df['Exists_on_Yahoo'], df['Yahoo_Exchange'], df['Yahoo_Name'], df['Yahoo_Sector'], df['Yahoo_Industry'], df['Yahoo_Country'], df['Theme'] = zip(*results)
        st.success("✅ Check complete!")
        st.dataframe(df)

        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Download Results as CSV", csv, "Checked_Yahoo_Tickers.csv", "text/csv")

else:
    st.info("📥 Upload a CSV or Excel file with tickers to begin.")
