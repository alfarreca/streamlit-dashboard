import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf

# --- Hardcoded S&P 500 Ticker List (Symbol, Exchange) ---
TICKERS = [
    "MMM,NYSE", "AOS,NYSE", "ABT,NYSE", "ABBV,NYSE", "ACN,NYSE", "ADBE,NASDAQ", "AMD,NASDAQ", "AES,NYSE",
    "AFL,NYSE", "A,NYSE", "APD,NYSE", "ABNB,NYSE", "AKAM,NYSE", "ALB,NYSE", "ARE,NYSE", "ALGN,NYSE", "ALLE,NYSE",
    "LNT,NYSE", "ALL,NYSE", "GOOGL,NASDAQ", "GOOG,NASDAQ", "MO,NYSE", "AMZN,NASDAQ", "AMCR,NYSE", "AEE,NYSE",
    "AEP,NYSE", "AXP,NYSE", "AIG,NYSE", "AMT,NYSE", "AWK,NYSE", "AMP,NYSE", "AME,NYSE", "AMGN,NYSE", "APH,NYSE",
    "ADI,NASDAQ", "ANSS,NYSE", "AON,NYSE", "APA,NYSE", "APO,NYSE", "AAPL,NASDAQ", "AMAT,NASDAQ", "APTV,NYSE",
    "ACGL,NYSE", "ADM,NYSE", "ANET,NYSE", "AJG,NYSE", "AIZ,NYSE", "T,NYSE", "ATO,NYSE", "ADSK,NYSE", "ADP,NYSE",
    "AZO,NYSE", "AVB,NYSE", "AVY,NYSE", "AXON,NYSE", "BKR,NYSE", "BALL,NYSE", "BAC,NYSE", "BAX,NYSE", "BDX,NYSE",
    "BRK-B,NYSE", "BBY,NYSE", "TECH,NYSE", "BIIB,NYSE", "BLK,NYSE", "BX,NYSE", "BK,NYSE", "BA,NYSE", "BKNG,NYSE",
    "BSX,NYSE", "BMY,NYSE", "AVGO,NASDAQ", "BR,NYSE", "BRO,NYSE", "BF-B,NYSE", "BLDR,NYSE", "BG,NYSE", "BXP,NYSE",
    "CHRW,NYSE", "CDNS,NYSE", "CZR,NYSE", "CPT,NYSE", "CPB,NYSE", "COF,NYSE", "CAH,NYSE", "KMX,NYSE", "CCL,NYSE",
    "CARR,NYSE", "CAT,NYSE", "CBOE,NYSE", "CBRE,NYSE", "CDW,NYSE", "COR,NYSE", "CNC,NYSE", "CNP,NYSE", "CF,NYSE",
    "CRL,NYSE", "SCHW,NYSE", "CHTR,NYSE", "CVX,NYSE", "CMG,NYSE", "CB,NYSE", "CHD,NYSE", "CI,NYSE", "CINF,NYSE",
    "CTAS,NYSE", "CSCO,NASDAQ", "C,NYSE", "CFG,NYSE", "CLX,NYSE", "CME,NYSE", "CMS,NYSE", "KO,NYSE", "CTSH,NYSE",
    "COIN,NASDAQ", "CL,NYSE", "CMCSA,NYSE", "CAG,NYSE", "COP,NYSE", "ED,NYSE", "STZ,NYSE", "COIN,NYSE", "CEG,NYSE",
    "COO,NYSE", "CPRT,NYSE", "GLW,NYSE", "CPAY,NYSE", "CTVA,NYSE", "CSGP,NYSE", "COST,NYSE", "CTRA,NYSE",
    "CRWD,NASDAQ", "CCI,NYSE", "CSX,NYSE", "CMI,NYSE", "CVS,NYSE", "DHR,NYSE", "DRI,NYSE", "DVA,NYSE", "DAY,NYSE",
    "DECK,NYSE", "DE,NYSE", "DELL,NYSE", "DAL,NYSE", "DVN,NYSE", "DXCM,NYSE", "FANG,NYSE", "DLR,NYSE", "DG,NYSE",
    "DLTR,NYSE", "D,NYSE", "DPZ,NYSE", "DASH,NYSE", "DOV,NYSE", "DOW,NYSE", "DHI,NYSE", "DTE,NYSE", "DUK,NYSE",
    "DD,NYSE", "EMN,NYSE", "ETN,NYSE", "EBAY,NYSE", "ECL,NYSE", "EIX,NYSE", "EW,NYSE", "EA,NYSE", "ELV,NYSE",
    "EMR,NYSE", "ENPH,NYSE", "ETR,NYSE", "EOG,NYSE", "EPAM,NYSE", "EQT,NYSE", "EFX,NYSE", "EQIX,NYSE", "EQR,NYSE",
    "ERIE,NYSE", "ESS,NYSE", "EL,NYSE", "EG,NYSE", "EVRG,NYSE", "ES,NYSE", "EXC,NYSE", "EXE,NYSE", "EXPE,NYSE",
    "EXPD,NYSE", "EXR,NYSE", "XOM,NYSE", "FFIV,NYSE", "FDS,NYSE", "FICO,NYSE", "FAST,NYSE", "FRT,NYSE", "FDX,NYSE",
    "FIS,NYSE", "FITB,NYSE", "FSLR,NYSE", "FE,NYSE", "FI,NYSE", "F,NYSE", "FTNT,NYSE", "FTV,NYSE", "FOXA,NYSE",
    "FOX,NYSE", "BEN,NYSE", "FCX,NYSE", "GRMN,NYSE", "IT,NYSE", "GE,NYSE", "GEHC,NYSE", "GEV,NYSE", "GEN,NYSE",
    "GNRC,NYSE", "GD,NYSE", "GIS,NYSE", "GM,NYSE", "GPC,NYSE", "GILD,NYSE", "GPN,NYSE", "GL,NYSE", "GDDY,NYSE",
    "GS,NYSE", "HAL,NYSE", "HIG,NYSE", "HAS,NYSE", "HCA,NYSE", "DOC,NYSE", "HSIC,NYSE", "HSY,NYSE", "HES,NYSE",
    "HPE,NYSE", "HLT,NYSE", "HOLX,NYSE", "HD,NYSE", "HON,NYSE", "HRL,NYSE", "HST,NYSE", "HWM,NYSE", "HPQ,NYSE",
    "HUBB,NYSE", "HUM,NYSE", "HBAN,NYSE", "HII,NYSE", "IBM,NYSE", "IEX,NYSE", "IDXX,NYSE", "ITW,NYSE", "INCY,NYSE",
    "IR,NYSE", "PODD,NYSE", "INTC,NASDAQ", "ICE,NYSE", "IFF,NYSE", "IP,NYSE", "IPG,NYSE", "INTU,NYSE", "ISRG,NYSE",
    "IVZ,NYSE", "INVH,NYSE", "IQV,NYSE", "IRM,NYSE", "JBHT,NYSE", "JBL,NYSE", "JKHY,NYSE", "J,NYSE", "JNJ,NYSE",
    "JCI,NYSE", "JPM,NYSE", "JNPR,NYSE", "K,NYSE", "KVUE,NYSE", "KDP,NYSE", "KEY,NYSE", "KEYS,NYSE", "KMB,NYSE",
    "KIM,NYSE", "KMI,NYSE", "KKR,NYSE", "KLAC,NYSE", "KHC,NYSE", "KR,NYSE", "LHX,NYSE", "LH,NYSE", "LRCX,NYSE",
    "LW,NYSE", "LVS,NYSE", "LDOS,NYSE", "LEN,NYSE", "LII,NYSE", "LLY,NYSE", "LIN,NYSE", "LYV,NYSE", "LKQ,NYSE",
    "LMT,NYSE", "L,NYSE", "LOW,NYSE", "LULU,NYSE", "LYB,NYSE", "MTB,NYSE", "MPC,NYSE", "MKTX,NYSE", "MAR,NYSE",
    "MMC,NYSE", "MLM,NYSE", "MAS,NYSE", "MA,NYSE", "MTCH,NYSE", "MKC,NYSE", "MCD,NYSE", "MCK,NYSE", "MDT,NYSE",
    "MRK,NYSE", "META,NASDAQ", "MET,NYSE", "MTD,NYSE", "MGM,NYSE", "MCHP,NYSE", "MU,NASDAQ", "MSFT,NASDAQ",
    "MAA,NYSE", "MRNA,NYSE", "MHK,NYSE", "MOH,NYSE", "TAP,NYSE", "MDLZ,NYSE", "MPWR,NYSE", "MNST,NYSE", "MCO,NYSE",
    "MS,NYSE", "MOS,NYSE", "MSI,NYSE", "MSCI,NYSE", "NDAQ,NYSE", "NTAP,NYSE", "NFLX,NASDAQ", "NEM,NYSE", "NWSA,NYSE",
    "NWS,NYSE", "NEE,NYSE", "NKE,NYSE", "NI,NYSE", "NDSN,NYSE", "NSC,NYSE", "NTRS,NYSE", "NOC,NYSE", "NCLH,NYSE",
    "NRG,NYSE", "NUE,NYSE", "NVDA,NASDAQ", "NVR,NYSE", "NXPI,NYSE", "ORLY,NYSE", "OXY,NYSE", "ODFL,NYSE", "OMC,NYSE",
    "ON,NYSE", "OKE,NYSE", "ORCL,NYSE", "OTIS,NYSE", "PCAR,NYSE", "PKG,NYSE", "PLTR,NYSE", "PANW,NYSE", "PARA,NYSE",
    "PH,NYSE", "PAYX,NYSE", "PAYC,NYSE", "PYPL,NASDAQ", "PNR,NYSE", "PEP,NYSE", "PFE,NYSE", "PCG,NYSE", "PM,NYSE",
    "PSX,NYSE", "PNW,NYSE", "PNC,NYSE", "POOL,NYSE", "PPG,NYSE", "PPL,NYSE", "PFG,NYSE", "PG,NYSE", "PGR,NYSE",
    "PLD,NYSE", "PRU,NYSE", "PEG,NYSE", "PTC,NYSE", "PSA,NYSE", "PHM,NYSE", "PWR,NYSE", "QCOM,NASDAQ", "DGX,NYSE",
    "RL,NYSE", "RJF,NYSE", "RTX,NYSE", "O,NYSE", "REG,NYSE", "REGN,NYSE", "RF,NYSE", "RSG,NYSE", "RMD,NYSE",
    "RVTY,NYSE", "ROK,NYSE", "ROL,NYSE", "ROP,NYSE", "ROST,NYSE", "RCL,NYSE", "SPGI,NYSE", "CRM,NYSE", "SBAC,NYSE",
    "SLB,NYSE", "STX,NYSE", "SRE,NYSE", "NOW,NYSE", "SHW,NYSE", "SPG,NYSE", "SWKS,NYSE", "SJM,NYSE", "SW,NYSE",
    "SNA,NYSE", "SOLV,NYSE", "SO,NYSE", "LUV,NYSE", "SWK,NYSE", "SBUX,NYSE", "STT,NYSE", "STLD,NYSE", "STE,NYSE",
    "SYK,NYSE", "SMCI,NYSE", "SYF,NYSE", "SNPS,NYSE", "SYY,NYSE", "TMUS,NYSE", "TROW,NYSE", "TTWO,NYSE", "TPR,NYSE",
    "TRGP,NYSE", "TGT,NYSE", "TEL,NYSE", "TDY,NYSE", "TER,NYSE", "TSLA,NASDAQ", "TXN,NASDAQ", "TPL,NYSE", "TXT,NYSE",
    "TMO,NYSE", "TJX,NYSE", "TKO,NYSE", "TSCO,NYSE", "TT,NYSE", "TDG,NYSE", "TRV,NYSE", "TRMB,NYSE", "TFC,NYSE",
    "TYL,NYSE", "TSN,NYSE", "USB,NYSE", "UBER,NYSE", "UDR,NYSE", "ULTA,NYSE", "UNP,NYSE", "UAL,NYSE", "UPS,NYSE",
    "URI,NYSE", "UNH,NYSE", "UHS,NYSE", "VLO,NYSE", "VTR,NYSE", "VLTO,NYSE", "VRSN,NYSE", "VRSK,NYSE", "VZ,NYSE",
    "VRTX,NYSE", "VTRS,NYSE", "VICI,NYSE", "V,NYSE", "VST,NYSE", "VMC,NYSE", "WRB,NYSE", "GWW,NYSE", "WAB,NYSE",
    "WBA,NYSE", "WMT,NYSE", "DIS,NYSE", "WBD,NYSE", "WM,NYSE", "WAT,NYSE", "WEC,NYSE", "WFC,NYSE", "WELL,NYSE",
    "WST,NYSE", "WDC,NYSE", "WY,NYSE", "WSM,NYSE", "WMB,NYSE", "WTW,NYSE", "WDAY,NYSE", "WYNN,NYSE", "XEL,NYSE",
    "XYL,NYSE", "YUM,NYSE", "ZBRA,NYSE", "ZBH,NYSE", "ZTS,NYSE", "XYZ,NYSE", "HOOD,NASDAQ"
]

# --- yfinance data fetch (cache only DataFrame) ---
@st.cache_data(show_spinner=False)
def fetch_history(symbol, period="6mo", interval="1d"):
    try:
        ticker_obj = yf.Ticker(symbol)
        hist = ticker_obj.history(period=period, interval=interval)
        if isinstance(hist, pd.DataFrame) and not hist.empty:
            return hist
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

# --- DMI/ADX chart ---
def create_dmi_chart(hist, symbol):
    if hist.empty or not all(col in hist.columns for col in ['High', 'Low', 'Close']):
        return go.Figure()
    high = hist['High']
    low = hist['Low']
    close = hist['Close']

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()

    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

    plus_di = 100 * (plus_dm.rolling(14).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr)

    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.rolling(14).mean()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name='Price', line=dict(color='yellow'), yaxis='y1'))
    fig.add_trace(go.Scatter(x=hist.index, y=plus_di, name='+DI', line=dict(color='green'), yaxis='y2'))
    fig.add_trace(go.Scatter(x=hist.index, y=minus_di, name='-DI', line=dict(color='red'), yaxis='y2'))
    fig.add_trace(go.Scatter(x=hist.index, y=adx, name='ADX', line=dict(color='blue', width=2), yaxis='y2'))
    fig.add_shape(type="line", x0=hist.index[0], y0=25, x1=hist.index[-1], y1=25, line=dict(color="blue", width=1, dash="dot"), yref="y2")
    fig.update_layout(
        title=f'{symbol} Price with DMI Indicators',
        xaxis_title='Date',
        yaxis_title='Price',
        yaxis2=dict(
            title='DMI Values',
            overlaying='y',
            side='right',
            range=[0, max(plus_di.max(), minus_di.max(), adx.max()) * 1.1 if not pd.isna(adx.max()) else 30]
        ),
        hovermode='x unified',
        height=400,
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

# --- Price & Volume chart ---
def create_price_chart(hist, symbol):
    if hist.empty or not all(col in hist.columns for col in ['Open', 'High', 'Low', 'Close', 'Volume']):
        return go.Figure()
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=hist.index,
        open=hist['Open'],
        high=hist['High'],
        low=hist['Low'],
        close=hist['Close'],
        name='Candlestick'
    ))
    fig.add_trace(go.Bar(
        x=hist.index,
        y=hist['Volume'],
        name='Volume',
        yaxis='y2',
        marker=dict(color='#e1e1e1', opacity=0.3)
    ))
    fig.update_layout(
        title=f"{symbol} Price & Volume",
        xaxis_title='Date',
        yaxis_title='Price',
        yaxis2=dict(title='Volume', overlaying='y', side='right', showgrid=False),
        hovermode='x unified',
        height=400,
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

# --- Symbol Details Display ---
def display_symbol_details(selected_symbol):
    if not selected_symbol:
        st.info("Please select a symbol.")
        return
    symbol = selected_symbol.split(",")[0]  # Only use the ticker for yfinance
    with st.spinner(f'Loading {selected_symbol} analysis...'):
        try:
            st.subheader(f"{selected_symbol} Detailed Analysis")
            hist = fetch_history(symbol)
            if hist.empty:
                st.warning("Could not load price history for chart or indicators")
                return
            tab1, tab2 = st.tabs(["Price Chart", "DMI Indicators"])
            with tab1:
                st.plotly_chart(create_price_chart(hist, symbol), use_container_width=True)
            with tab2:
                st.plotly_chart(create_dmi_chart(hist, symbol), use_container_width=True)
                with st.expander("DMI Indicators Interpretation"):
                    st.markdown("""
                    - **+DI (Green)**: Measures upward movement strength  
                    - **-DI (Red)**: Measures downward movement strength  
                    - **ADX (Blue)**: Measures trend strength (values > 25 suggest strong trend)  
                    - **Bullish Signal**: +DI crosses above -DI  
                    - **Bearish Signal**: -DI crosses above +DI
                    """)
        except Exception as e:
            st.error(f"Error loading {selected_symbol}: {str(e)}")

# --- Main App ---
def main():
    st.title("S&P 500 Momentum Scanner")
    st.sidebar.header("Select Stock Symbol")
    symbols = TICKERS
    if not symbols:
        st.error("No symbols loaded.")
        return
    selected = st.sidebar.selectbox("Symbol", symbols)
    display_symbol_details(selected)

if __name__ == "__main__":
    main()
