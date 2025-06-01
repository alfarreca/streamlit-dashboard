import streamlit as st
import pandas as pd
from datetime import datetime

# Dummy function for event filtering; replace with your actual implementation
def apply_event_filters(df):
    # For example, return unchanged
    return df

# Dummy variables for UI filters; replace with your actual logic or st.sidebar widgets
selected_trends = ["Up", "Down"]  # Example: ["Up", "Down", "Sideways"]
selected_exchanges = ["NYSE", "NASDAQ"]  # Example: ["NYSE", "NASDAQ"]

# ========== EVENT ANALYSIS ==========
def get_events_data(ticker_obj):
    """Get upcoming earnings dates using multiple methods with enhanced debugging"""
    ticker = ticker_obj.ticker
    try:
        # Method 1: get_earnings_dates()
        try:
            earnings = ticker_obj.get_earnings_dates()
            if earnings is not None and not earnings.empty:
                future_earnings = earnings[earnings.index > pd.Timestamp.now()]
                if not future_earnings.empty:
                    st.write(f"Found earnings dates for {ticker} via get_earnings_dates()")
                    return sorted(future_earnings.index.tolist())
        except Exception as e:
            st.write(f"Method 1 failed for {ticker}: {str(e)}")
        
        # Method 2: calendar (fallback)
        try:
            calendar = ticker_obj.calendar
            if calendar is not None and not calendar.empty and 'Earnings Date' in calendar:
                dates = [pd.to_datetime(date) for date in calendar['Earnings Date'].tolist()]
                future_dates = [date for date in dates if date > pd.Timestamp.now()]
                if future_dates:
                    st.write(f"Found earnings dates for {ticker} via calendar")
                    return sorted(future_dates)
        except Exception as e:
            st.write(f"Method 2 failed for {ticker}: {str(e)}")
            
        # Method 3: earnings_dates (alternative)
        try:
            if hasattr(ticker_obj, 'earnings_dates'):
                dates = ticker_obj.earnings_dates
                if dates is not None and not dates.empty:
                    future_dates = [date for date in dates if date > pd.Timestamp.now()]
                    if future_dates:
                        st.write(f"Found earnings dates for {ticker} via earnings_dates")
                        return sorted(future_dates)
        except Exception as e:
            st.write(f"Method 3 failed for {ticker}: {str(e)}")
            
        # Method 4: Try with different parameters
        try:
            hist = ticker_obj.history(period="1mo")
            if not hist.empty:
                info = ticker_obj.get_info()
                if 'earningsDate' in info:
                    dates = [pd.to_datetime(d) for d in info['earningsDate']]
                    future_dates = [date for date in dates if date > pd.Timestamp.now()]
                    if future_dates:
                        st.write(f"Found earnings dates for {ticker} via get_info()")
                        return sorted(future_dates)
        except Exception as e:
            st.write(f"Method 4 failed for {ticker}: {str(e)}")
            
    except Exception as e:
        st.warning(f"Critical error fetching earnings dates for {ticker}: {str(e)}")
    
    st.write(f"No earnings dates found for {ticker} after all methods")
    return []

# ========== DISPLAY RESULTS ==========

# Example of how initial_results might be set (replace with your actual logic)
if "initial_results" not in st.session_state:
    # Create a dummy DataFrame for demonstration
    st.session_state.initial_results = [
        {
            "Symbol": "AAPL",
            "Earnings_Dates": [datetime(2025, 7, 20), datetime(2025, 10, 22)],
            "Momentum_Score": 85,
            "Trend": "Up",
            "Price": 180,
            "Exchange": "NASDAQ"
        },
        {
            "Symbol": "TSLA",
            "Earnings_Dates": [datetime(2025, 7, 15)],
            "Momentum_Score": 60,
            "Trend": "Down",
            "Price": 180,
            "Exchange": "NASDAQ"
        }
    ]
    st.session_state.min_score = 50
    st.session_state.price_range = (100, 200)

if "initial_results" in st.session_state and st.session_state.initial_results:
    filtered = pd.DataFrame(st.session_state.initial_results)
    
    # Debug: Show raw earnings data
    st.write("Sample raw earnings data:", filtered[["Symbol", "Earnings_Dates"]].head())
    
    # Apply momentum filters
    filtered = filtered[
        (filtered["Momentum_Score"] >= st.session_state.min_score) &
        (filtered["Trend"].isin(selected_trends)) &
        (filtered["Price"].between(*st.session_state.price_range)) &
        (filtered["Exchange"].isin(selected_exchanges))
    ].copy()

    # Add "Upcoming Earnings Date" column with enhanced handling
    def extract_next_earnings(dates):
        if not dates or len(dates) == 0:
            return "No upcoming earnings"
        
        try:
            # Get all future dates
            future_dates = [date for date in dates if hasattr(date, 'strftime') and date > datetime.now()]
            if not future_dates:
                return "No upcoming earnings"
                
            next_date = min(future_dates)
            days_until = (next_date - datetime.now()).days
            return f"{next_date.strftime('%Y-%m-%d')} (in {days_until} days)"
        except Exception as e:
            st.warning(f"Error processing dates: {e}")
            return "Date error"

    filtered["Upcoming Earnings Date"] = filtered["Earnings_Dates"].apply(extract_next_earnings)
    
    # Debug: Show processed earnings data
    st.write("Processed earnings data:", filtered[["Symbol", "Earnings_Dates", "Upcoming Earnings Date"]].head())
    
    # Apply event filters
    filtered = apply_event_filters(filtered)
    
    filtered = filtered.sort_values("Momentum_Score", ascending=False)
    st.session_state.filtered_results = filtered

    st.write("Final filtered and sorted results:")
    st.dataframe(filtered)
else:
    st.info("No initial results to display.")
