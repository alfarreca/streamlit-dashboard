import streamlit as st
import pandas as pd

def main():
    st.title("2000 Technical Scanner")
    
    # Initialize session state variables if they don't exist
    if 'full_data' not in st.session_state:
        st.session_state.full_data = pd.DataFrame()
    if 'filtered_result' not in st.session_state:
        st.session_state.filtered_result = pd.DataFrame()
    
    # Sidebar filters
    with st.sidebar:
        st.header("Filters")
        
        # Momentum filters
        col1, col2 = st.columns(2)
        with col1:
            min_1m_mom = st.slider("1M Min Momentum (%)", -30.0, 50.0, -10.0)
        with col2:
            min_3m_mom = st.slider("3M Min Momentum (%)", -50.0, 100.0, 0.0)
        
        min_rel_strength = st.slider("Min Rel Strength (%)", -20.0, 30.0, 0.0)
        ma_crossover = st.selectbox("MA Crossover", ["All", "Golden Cross", "Death Cross"])
    
    # Main content area
    st.header("Load Data")
    
    # File uploader
    uploaded_file = st.file_uploader("Upload your data file (CSV or Excel)", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        try:
            # Read the file based on extension
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            # Clean column names by stripping whitespace
            df.columns = df.columns.str.strip()
            
            # Standardize column names (handle different naming conventions)
            column_mapping = {
                'Rel Strength': 'Rel Strength (%)',
                '1M Mom': '1M Momentum (%)',
                '3M Mom': '3M Momentum (%)',
                # Add other possible column name variations here
            }
            
            df.rename(columns=column_mapping, inplace=True)
            
            # Store the loaded data in session state
            st.session_state.full_data = df
            
            st.success("Data loaded successfully!")
            
            # Show available columns for debugging
            if st.checkbox("Show column names"):
                st.write("Available columns:", df.columns.tolist())
        
        except Exception as e:
            st.error(f"Error loading file: {str(e)}")
    
    # Filtering logic
    if not st.session_state.full_data.empty:
        try:
            # Check for required columns
            required_columns = [
                'Rel Strength (%)', 
                '1M Momentum (%)', 
                '3M Momentum (%)',
                # Add other required columns here
            ]
            
            missing_cols = [col for col in required_columns if col not in st.session_state.full_data.columns]
            
            if missing_cols:
                st.warning(f"Missing required columns: {', '.join(missing_cols)}")
            else:
                # Apply filters
                filtered = st.session_state.full_data[
                    (st.session_state.full_data['1M Momentum (%)'] >= min_1m_mom) &
                    (st.session_state.full_data['3M Momentum (%)'] >= min_3m_mom) &
                    (st.session_state.full_data['Rel Strength (%)'] >= min_rel_strength)
                ]
                
                # Additional MA Crossover filter
                if ma_crossover != "All":
                    if ma_crossover == "Golden Cross":
                        filtered = filtered[filtered['MA_Status'] == 'Golden Cross']
                    else:
                        filtered = filtered[filtered['MA_Status'] == 'Death Cross']
                
                st.session_state.filtered_result = filtered
                
                # Display results
                st.header("Filtered Results")
                st.dataframe(st.session_state.filtered_result)
                
                # Export option
                if st.button("Export Results"):
                    csv = filtered.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name="filtered_results.csv",
                        mime="text/csv"
                    )
        
        except KeyError as e:
            st.error(f"Column not found in data: {str(e)}")
            st.write("Available columns:", st.session_state.full_data.columns.tolist())
        except Exception as e:
            st.error(f"Error applying filters: {str(e)}")

if __name__ == "__main__":
    main()
