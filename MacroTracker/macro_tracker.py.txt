# macro_tracker.py

import streamlit as st
import pandas as pd
from datetime import datetime
import os

# Page setup
st.set_page_config(page_title="Macro + ETF Rotation Tracker", layout="wide")
st.title("🧠 Macro + ETF Rotation Tracker")
st.markdown("Track macro events, investor sentiment shifts, and their ETF implications.")

CSV_FILE = "macro_events.csv"

# Load CSV
def load_macro_data():
    if os.path.exists(CSV_FILE):
        return pd.read_csv(CSV_FILE)
    else:
        return pd.DataFrame(columns=[
            "Date", "Event", "Trigger", "Investor Behavior",
            "Assets Impacted", "ETF Candidates", "Sentiment Risk Level"
        ])

# Save CSV
def save_macro_data(df):
    df.to_csv(CSV_FILE, index=False)

# Initial load
df = load_macro_data()

# --- FORM TO ADD NEW ENTRY ---
st.subheader("➕ Add New Macro Event")
with st.form("add_event_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        date = st.date_input("📅 Date", value=datetime.today())
        event = st.text_input("📰 Event", placeholder="e.g. Retail volatility response")
        trigger = st.text_input("⚠️ Trigger", placeholder="e.g. Trump tariffs / S&P drop")
        behavior = st.text_input("🧠 Investor Behavior", placeholder="e.g. Buy-the-dip + Flight to safety")
    with col2:
        assets = st.text_input("📈 Assets Impacted", placeholder="e.g. SPY, CDs, VIX")
        etfs = st.text_input("📊 ETF Candidates", placeholder="e.g. SPY;SCHD;BIL;VXX")
        risk = st.selectbox("📉 Sentiment Risk Level", ["Low", "Medium", "Medium-High", "High"])
    
    submitted = st.form_submit_button("Add Event")

    if submitted:
        new_row = {
            "Date": date.strftime("%Y-%m-%d"),
            "Event": event,
            "Trigger": trigger,
            "Investor Behavior": behavior,
            "Assets Impacted": assets,
            "ETF Candidates": etfs,
            "Sentiment Risk Level": risk
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        save_macro_data(df)
        st.success("✅ Event added successfully!")

# --- DISPLAY TABLE ---
st.subheader("📊 Current Macro Events")
st.dataframe(df, use_container_width=True)

# --- DOWNLOAD BUTTON ---
csv_data = df.to_csv(index=False).encode("utf-8")
st.download_button("📥 Download Full Dataset", csv_data, "macro_events.csv", "text/csv")
