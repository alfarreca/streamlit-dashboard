import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import numpy as np

# --- Configuration ---
st.set_page_config(layout="wide", page_title="AlphaPod Trader")

# --- API Key Handling ---
POLYGON_KEY = st.secrets.get("POLYGON_KEY", "rOaZAKKbjkTXFj7FVfQaWormDpSQj8Ki")  # Fallback to demo key

# --- Session State ---
if "trades" not in st.session_state:
    st.session_state.trades = []
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []

# --- Core Functions ---
def fetch_live_earnings():
    """Get real earnings data from Polygon.io"""
    url = "https://api.polygon.io/v2/reference/earnings"
    params = {
        "apiKey": POLYGON_KEY,
        "date.gte": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
        "date.lte": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
        "limit": 50
    }
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json().get("results", [])
            return sorted(data, key=lambda x: x.get("reportDate", ""), reverse=True)
        else:
            st.warning(f"API Error: {response.status_code} - Using demo data")
            return get_demo_earnings()
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return get_demo_earnings()

def get_demo_earnings():
    """Fallback demo data"""
    return [
        {
            "ticker": "NVDA",
            "reportDate": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
            "epsEstimate": 3.34,
            "eps": 3.71,
            "surprisePercent": 11.08
        },
        {
            "ticker": "TSLA",
            "reportDate": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"),
            "epsEstimate": 0.73,
            "eps": 0.85,
            "surprisePercent": 16.44
        }
    ]

[... REST OF THE ORIGINAL CODE REMAINS THE SAME ...]
