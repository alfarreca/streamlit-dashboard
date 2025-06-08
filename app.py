import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

st.title("NYSE Arca Gold Miners Index (^GDM) - Live Components from Yahoo Finance")

st.write("Fetches the current index members from Yahoo Finance’s [^GDM components page](https://finance.yahoo.com/quote/%5EGDM/components?p=%5EGDM).")

if st.button("Fetch GDM Components Now"):
    # Yahoo Finance components URL for ^GDM
    url = 'https://finance.yahoo.com/quote/%5EGDM/components?p=%5EGDM'
    headers = {
        'User-Agent': 'Mozilla/5.0'
    }

    with st.spinner('Fetching data from Yahoo Finance...'):
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            st.error(f"Failed to load page ({resp.status_code})")
        else:
            soup = BeautifulSoup(resp.text, 'lxml')
            table = soup.find('table')
            if table is None:
                st.error("Could not find the components table on the page (Yahoo may have changed their layout).")
            else:
                df = pd.read_html(str(table))[0]
                st.success(f"Loaded {len(df)} components.")
                st.dataframe(df)

                # Download as CSV
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("Download as CSV", csv, "gdm_components.csv", "text/csv")
else:
    st.info("Click the button to fetch the latest NYSE Arca Gold Miners Index (^GDM) components.")

