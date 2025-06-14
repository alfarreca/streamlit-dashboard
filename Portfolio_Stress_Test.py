import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import yfinance as yf
import streamlit as st

class PortfolioStressTester:
    def __init__(self, portfolio):
        """
        Initialize the stress tester with a portfolio
        
        Args:
            portfolio (dict): Dictionary of assets and their weights
                Example: {'AAPL': 0.4, 'MSFT': 0.3, 'BTC-USD': 0.2, 'GLD': 0.1}
        """
        self.portfolio = portfolio
        self.historical_data = None
        self.scenarios = {
            '2008 Crisis': {'start': '2007-10-01', 'end': '2009-03-01'},
            'COVID Crash': {'start': '2020-02-01', 'end': '2020-04-01'},
            '2022 Bear Market': {'start': '2022-01-01', 'end': '2022-10-01'},
            'Custom Scenario': {}  # To be defined by user
        }
        
    def fetch_historical_data(self, start_date, end_date):
        """Download historical price data for all assets in the portfolio"""
        st.write(f"Fetching data for {list(self.portfolio.keys())} from {start_date} to {end_date}")
        
        try:
            data = yf.download(
                list(self.portfolio.keys()), 
                start=start_date, 
                end=end_date,
                progress=False,
                group_by='ticker'
            )
            
            # Handle single asset case (returns Series instead of DataFrame)
            if len(self.portfolio) == 1:
                asset = list(self.portfolio.keys())[0]
                data = pd.DataFrame({asset: data['Adj Close']})
            else:
                data = data['Adj Close']
                
            # Check if we got any data
            if data.empty:
                raise ValueError("No data returned from Yahoo Finance")
                
            # Check which assets we actually received
            missing = set(self.portfolio.keys()) - set(data.columns)
            if missing:
                st.warning(f"Could not fetch data for: {missing}")
                
            return data
            
        except Exception as e:
            st.error(f"Error fetching data: {str(e)}")
            return None
    
    def calculate_portfolio_returns(self, data):
        """Calculate daily portfolio returns based on asset weights"""
        if data is None:
            return None
            
        # Ensure we only keep assets that were successfully downloaded
        valid_assets = [asset for asset in self.portfolio.keys() if asset in data.columns]
        if not valid_assets:
            raise ValueError("None of the portfolio assets were found in the downloaded data")
        
        # Normalize weights for the valid assets only
        valid_weights = np.array([self.portfolio[asset] for asset in valid_assets])
        valid_weights /= valid_weights.sum()  # Re-normalize to 1
        
        returns = data[valid_assets].pct_change().dropna()
        weighted_returns = returns * valid_weights
        portfolio_returns = weighted_returns.sum(axis=1)
        return portfolio_returns
    
    def run_stress_test(self, scenario_name):
        """Run stress test for a given historical scenario"""
        if scenario_name not in self.scenarios:
            raise ValueError(f"Unknown scenario: {scenario_name}")
            
        scenario = self.scenarios[scenario_name]
        if scenario_name == 'Custom Scenario':
            if not scenario.get('start') or not scenario.get('end'):
                raise ValueError("Custom scenario requires start and end dates")
        
        data = self.fetch_historical_data(scenario['start'], scenario['end'])
        if data is None:
            return None
            
        portfolio_returns = self.calculate_portfolio_returns(data)
        if portfolio_returns is None:
            return None
        
        # Calculate cumulative returns
        cumulative_returns = (1 + portfolio_returns).cumprod() - 1
        
        results = {
            'max_drawdown': self.calculate_max_drawdown(cumulative_returns),
            'worst_day': portfolio_returns.min(),
            'volatility': portfolio_returns.std(),
            'scenario_duration': f"{len(portfolio_returns)} trading days",
            'final_return': cumulative_returns.iloc[-1],
            'data': data,
            'portfolio_returns': portfolio_returns,
            'cumulative_returns': cumulative_returns
        }
            
        return results
    
    def calculate_max_drawdown(self, cumulative_returns):
        """Calculate maximum drawdown during the stress period"""
        peak = cumulative_returns.expanding(min_periods=1).max()
        drawdown = (cumulative_returns - peak) / (1 + peak)
        return drawdown.min()
    
    def plot_results(self, results, scenario_name):
        """Visualize stress test results using matplotlib"""
        if results is None:
            return None
            
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        # Daily returns histogram
        ax1.hist(results['portfolio_returns'], bins=30, alpha=0.7)
        ax1.set_title(f'{scenario_name} - Daily Returns Distribution')
        ax1.set_xlabel('Daily Return')
        ax1.set_ylabel('Frequency')
        
        # Cumulative returns line plot
        ax2.plot(results['cumulative_returns'])
        ax2.set_title(f'{scenario_name} - Cumulative Portfolio Returns')
        ax2.set_xlabel('Date')
        ax2.set_ylabel('Cumulative Return')
        ax2.axhline(0, color='black', linestyle='--')
        
        plt.tight_layout()
        return fig
    
    def add_custom_scenario(self, name, start_date, end_date):
        """Add a custom historical stress scenario"""
        self.scenarios[name] = {'start': start_date, 'end': end_date}
        st.success(f"Added custom scenario: {name} ({start_date} to {end_date})")

# Streamlit UI
def main():
    st.title("Portfolio Stress Test")
    st.write("Analyze how your portfolio would perform under historical market stress scenarios")
    
    # Portfolio input
    st.sidebar.header("Portfolio Configuration")
    assets = st.sidebar.text_area(
        "Enter assets and weights (format: TICKER:WEIGHT, one per line)",
        "AAPL:0.4\nMSFT:0.3\nBTC-USD:0.2\nGLD:0.1"
    )
    
    try:
        portfolio = {}
        for line in assets.split('\n'):
            if line.strip():
                ticker, weight = line.split(':')
                portfolio[ticker.strip()] = float(weight.strip())
    except Exception as e:
        st.error(f"Invalid portfolio format: {str(e)}")
        st.stop()
    
    if not portfolio:
        st.error("Please enter at least one asset with weight")
        st.stop()
    
    # Initialize tester
    tester = PortfolioStressTester(portfolio)
    
    # Scenario selection
    st.header("Select Stress Scenario")
    scenario = st.selectbox(
        "Choose a historical scenario",
        list(tester.scenarios.keys())
    )
    
    # Custom scenario inputs
    if scenario == 'Custom Scenario':
        col1, col2 = st.columns(2)
        start_date = col1.date_input("Start date", value=datetime(2020, 1, 1))
        end_date = col2.date_input("End date", value=datetime(2020, 12, 31))
        tester.scenarios['Custom Scenario'] = {
            'start': start_date.strftime('%Y-%m-%d'),
            'end': end_date.strftime('%Y-%m-%d')
        }
    
    # Run stress test
    if st.button("Run Stress Test"):
        with st.spinner("Running analysis..."):
            results = tester.run_stress_test(scenario)
            
            if results is None:
                st.error("Failed to run stress test")
                st.stop()
            
            st.success("Stress test completed!")
            
            # Display results
            st.subheader("Results Summary")
            col1, col2, col3 = st.columns(3)
            col1.metric("Max Drawdown", f"{results['max_drawdown']:.2%}")
            col2.metric("Worst Daily Return", f"{results['worst_day']:.2%}")
            col3.metric("Final Return", f"{results['final_return']:.2%}")
            
            col4, col5 = st.columns(2)
            col4.metric("Volatility (std dev)", f"{results['volatility']:.2%}")
            col5.metric("Duration", results['scenario_duration'])
            
            # Show charts
            st.subheader("Performance Charts")
            fig = tester.plot_results(results, scenario)
            st.pyplot(fig)
            
            # Show raw data
            if st.checkbox("Show raw data"):
                st.subheader("Historical Prices")
                st.dataframe(results['data'])
                
                st.subheader("Daily Returns")
                st.dataframe(results['portfolio_returns'].to_frame(name='Return'))

if __name__ == "__main__":
    main()
