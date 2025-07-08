import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="EM Resource Market Tracker", layout="wide")

st.title("🌏 EM Resource Market Tracker")

# --- Default article-based watchlist ---
DEFAULT_LIST = [
    # Brazil
    {"Symbol": "EWZ", "Exchange": "NYSEARCA", "Name": "iShares MSCI Brazil ETF", "notes": "Broad Brazil, resource-heavy, “bargain”"},
    {"Symbol": "VALE", "Exchange": "NYSE", "Name": "Vale", "notes": "Brazil, iron ore giant"},
    {"Symbol": "BRSR6B.SA", "Exchange": "B3", "Name": "Bradespar", "notes": "Brazil, mining/vale holding, resource play"},
    # Colombia
    {"Symbol": "GXG", "Exchange": "NYSEARCA", "Name": "Global X MSCI Colombia ETF", "notes": "Colombia, broad equities, “bargain”"},
    {"Symbol": "CIB", "Exchange": "NYSE", "Name": "Bancolombia", "notes": "Colombia, major bank"},
    # Turkey
    {"Symbol": "TUR", "Exchange": "NYSEARCA", "Name": "iShares MSCI Turkey ETF", "notes": "Turkey, broad equities, “bargain”"},
    {"Symbol": "TUPRS.IS", "Exchange": "BIST", "Name": "Tupras", "notes": "Turkey, energy refining"},
    # South Africa
    {"Symbol": "EZA", "Exchange": "NYSEARCA", "Name": "iShares MSCI South Africa ETF", "notes": "South Africa, broad equities, “bargain”"},
    {"Symbol": "GFI", "Exchange": "NYSE", "Name": "Gold Fields", "notes": "South Africa, gold mining"},
    # Egypt
    {"Symbol": "EGYPT.CA", "Exchange": "EGX", "Name": "EFG Hermes Holding", "notes": "Egypt, financials, investable large cap"},
    # Resource/frontier/other EM
    {"Symbol": "ECH", "Exchange": "NYSEARCA", "Name": "iShares MSCI Chile ETF", "notes": "Chile, copper-focused, EM"},
    {"Symbol": "ANTO.L", "Exchange": "LSE", "Name": "Antofagasta", "notes": "Chile, copper mining"},
    {"Symbol": "FM", "Exchange": "NYSEARCA", "Name": "iShares Frontier Markets ETF", "notes": "Vietnam, Kazakhstan, Romania exposure"},
    {"Symbol": "KAP.L", "Exchange": "LSE", "Name": "Kazatomprom (GDR)", "notes": "Kazakhstan, uranium, frontier market"},
    {"Symbol": "LIT", "Exchange": "NYSEARCA", "Name": "Global X Lithium & Battery ETF", "notes": "Frontier/resource, lithium/EV/battery supply chain"},
    {"Symbol": "RIO", "Exchange": "NYSE", "Name": "Rio Tinto", "notes": "Global mining, iron ore/copper, major EM exposure"},
    # India
    {"Symbol": "INDA", "Exchange": "NYSEARCA", "Name": "iShares MSCI India ETF", "notes": "India, broad equities, “expensive”"},
    {"Symbol": "INFY", "Exchange": "NYSE", "Name": "Infosys", "notes": "India, tech/IT, global outsourcing leader"},
    {"Symbol": "HDB", "Exchange": "NYSE", "Name": "HDFC Bank", "notes": "India, major private sector bank"},
    # US
    {"Symbol": "SPY", "Exchange": "NYSEARCA", "Name": "SPDR S&P 500 ETF", "notes": "U.S. large-cap benchmark, “expensive”"},
    {"Symbol": "QQQ", "Exchange": "NASDAQ", "Name": "Invesco QQQ Trust (Nasdaq 100)", "notes": "U.S. tech mega-cap, “expensive, AI-driven”"},
    {"Symbol": "NVDA", "Exchange": "NASDAQ", "Name": "NVIDIA", "notes": "U.S., AI/semiconductors, most valuable tech stock"},
]

# --- Load from uploaded file or use default ---
uploaded_file = st.file_uploader("Upload your EM watchlist Excel file (optional)", type="xlsx")
if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.success("Custom watchlist loaded!")
else:
    df = pd.DataFrame(DEFAULT_LIST)
    st.info("Loaded default watchlist based on article and global benchmarks.")

# --- Add new ticker interactively ---
with st.expander("➕ Add new ticker"):
    with st.form("add_ticker_form"):
        new_symbol = st.text_input("Symbol (Yahoo format)")
        new_exchange = st.text_input("Exchange (e.g., NYSE, NASDAQ, LSE)")
        new_name = st.text_input("Name")
        new_note = st.text_input("Notes")
        submitted = st.form_submit_button("Add Ticker")
        if submitted and new_symbol and new_name:
            df.loc[len(df)] = [new_symbol, new_exchange, new_name, new_note]
            st.success(f"Added {new_symbol}!")

# --- Fetch latest price & performance ---
def fetch_yahoo_data(symbols):
    data = yf.download(symbols, period="6mo", interval="1d", group_by='ticker', auto_adjust=True, progress=False)
    prices = {}
    for symbol in symbols:
        try:
            sym_data = data[symbol]['Close'] if isinstance(data.columns, pd.MultiIndex) else data['Close']
            last = sym_data[-1]
            week = sym_data[-5]
            month = sym_data[-21]
            qtr = sym_data[-63]
            change_1w = (last / week - 1) * 100
            change_1m = (last / month - 1) * 100
            change_3m = (last / qtr - 1) * 100
            prices[symbol] = {
                "Latest Price": last,
                "1W %": change_1w,
                "1M %": change_1m,
                "3M %": change_3m
            }
        except Exception:
            prices[symbol] = {
                "Latest Price": None,
                "1W %": None,
                "1M %": None,
                "3M %": None
            }
    return prices

symbols = df["Symbol"].tolist()
st.info(f"Fetching price data for {len(symbols)} tickers (this may take up to a minute)...")
prices = fetch_yahoo_data(symbols)
df["Latest Price"] = [prices[s]["Latest Price"] for s in symbols]
df["1W %"] = [prices[s]["1W %"] for s in symbols]
df["1M %"] = [prices[s]["1M %"] for s in symbols]
df["3M %"] = [prices[s]["3M %"] for s in symbols]

st.dataframe(df, use_container_width=True)

# --- Chart section ---
st.subheader("📈 Price Chart")
selected = st.selectbox("Select a ticker to chart:", symbols)
if selected:
    data = yf.download(selected, period="6mo", interval="1d", auto_adjust=True, progress=False)
    st.line_chart(data["Close"], height=350)

# --- Download updated table ---
st.download_button(
    label="Download Updated Table (XLSX)",
    data=df.to_excel(index=False, engine="openpyxl"),
    file_name="EM_Resource_Tracker_Results.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
