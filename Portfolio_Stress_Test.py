import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import yfinance as yf  # For market data (requires installation)
import seaborn as sns

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
            'Dot-com Bubble': {'start': '2000-03-01', 'end': '2000-12-01'},
            'Custom Scenario': {}  # To be defined by user
        }
        
    def fetch_historical_data(self, start_date, end_date):
        """Download historical price data for all assets in the portfolio"""
        print("Fetching historical data...")
        data = yf.download(list(self.portfolio.keys()), start=start_date, end=end_date)['Adj Close']
        self.historical_data = data
        return data
    
    def calculate_portfolio_returns(self, data):
        """Calculate daily portfolio returns based on asset weights"""
        returns = data.pct_change().dropna()
        weighted_returns = returns * np.array(list(self.portfolio.values()))
        portfolio_returns = weighted_returns.sum(axis=1)
        return portfolio_returns
    
    def run_stress_test(self, scenario_name, plot=True):
        """Run stress test for a given historical scenario"""
        if scenario_name not in self.scenarios:
            raise ValueError(f"Unknown scenario: {scenario_name}. Available scenarios: {list(self.scenarios.keys())}")
            
        scenario = self.scenarios[scenario_name]
        if scenario_name == 'Custom Scenario':
            if not scenario.get('start') or not scenario.get('end'):
                raise ValueError("Custom scenario requires start and end dates")
        
        data = self.fetch_historical_data(scenario['start'], scenario['end'])
        portfolio_returns = self.calculate_portfolio_returns(data)
        
        # Calculate cumulative returns
        cumulative_returns = (1 + portfolio_returns).cumprod() - 1
        
        if plot:
            self.plot_results(portfolio_returns, cumulative_returns, scenario_name)
            
        return {
            'max_drawdown': self.calculate_max_drawdown(cumulative_returns),
            'worst_day': portfolio_returns.min(),
            'volatility': portfolio_returns.std(),
            'scenario_duration': f"{len(portfolio_returns)} trading days",
            'final_return': cumulative_returns.iloc[-1]
        }
    
    def calculate_max_drawdown(self, cumulative_returns):
        """Calculate maximum drawdown during the stress period"""
        peak = cumulative_returns.expanding(min_periods=1).max()
        drawdown = (cumulative_returns - peak) / (1 + peak)
        return drawdown.min()
    
    def plot_results(self, daily_returns, cumulative_returns, scenario_name):
        """Visualize stress test results"""
        plt.figure(figsize=(15, 10))
        
        # Daily returns plot
        plt.subplot(2, 1, 1)
        sns.histplot(daily_returns, kde=True, bins=30)
        plt.title(f'{scenario_name} - Daily Returns Distribution')
        plt.xlabel('Daily Return')
        plt.ylabel('Frequency')
        
        # Cumulative returns plot
        plt.subplot(2, 1, 2)
        cumulative_returns.plot()
        plt.title(f'{scenario_name} - Cumulative Portfolio Returns')
        plt.xlabel('Date')
        plt.ylabel('Cumulative Return')
        plt.axhline(0, color='black', linestyle='--')
        
        plt.tight_layout()
        plt.show()
    
    def add_custom_scenario(self, name, start_date, end_date):
        """Add a custom historical stress scenario"""
        self.scenarios[name] = {'start': start_date, 'end': end_date}
        print(f"Added custom scenario: {name} ({start_date} to {end_date})")
    
    def monte_carlo_simulation(self, days=30, simulations=1000, plot=True):
        """
        Run Monte Carlo simulation based on historical volatility
        to project potential future stress scenarios
        """
        # Get recent historical data for volatility estimation
        recent_data = self.fetch_historical_data(
            (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d'),
            datetime.now().strftime('%Y-%m-%d')
        )
        returns = self.calculate_portfolio_returns(recent_data)
        mu, sigma = returns.mean(), returns.std()
        
        # Run simulations
        simulations = np.random.normal(mu, sigma, (days, simulations))
        cumulative_simulations = (1 + simulations).cumprod(axis=0) - 1
        
        if plot:
            plt.figure(figsize=(12, 6))
            for i in range(min(100, simulations.shape[1])):  # Plot first 100 paths
                plt.plot(cumulative_simulations[:, i], lw=1, alpha=0.1, color='blue')
            
            # Plot 5th and 95th percentiles
            plt.plot(np.percentile(cumulative_simulations, 5, axis=1), 
                    color='red', linestyle='--', label='5th Percentile')
            plt.plot(np.percentile(cumulative_simulations, 95, axis=1), 
                    color='green', linestyle='--', label='95th Percentile')
            
            plt.title(f'Monte Carlo Simulation ({simulations} paths, {days} days)')
            plt.xlabel('Days')
            plt.ylabel('Cumulative Return')
            plt.legend()
            plt.show()
        
        return {
            'worst_case_30d': np.percentile(cumulative_simulations[-1, :], 5),
            'best_case_30d': np.percentile(cumulative_simulations[-1, :], 95),
            'probability_of_loss': (cumulative_simulations[-1, :] < 0).mean()
        }

# Example usage
if __name__ == "__main__":
    # Define a sample portfolio
    my_portfolio = {
        'AAPL': 0.3,    # Apple stock
        'MSFT': 0.25,   # Microsoft stock
        'BTC-USD': 0.2, # Bitcoin
        'GLD': 0.15,    # Gold ETF
        'TLT': 0.1      # Long-term Treasury ETF
    }
    
    # Initialize stress tester
    tester = PortfolioStressTester(my_portfolio)
    
    # Run predefined stress tests
    print("Running 2008 Financial Crisis Stress Test...")
    results_2008 = tester.run_stress_test('2008 Crisis')
    print("\n2008 Crisis Results:")
    for k, v in results_2008.items():
        print(f"{k.replace('_', ' ').title()}: {v:.2%}" if isinstance(v, float) else f"{k.replace('_', ' ').title()}: {v}")
    
    print("\nRunning COVID Crash Stress Test...")
    results_covid = tester.run_stress_test('COVID Crash')
    print("\nCOVID Crash Results:")
    for k, v in results_covid.items():
        print(f"{k.replace('_', ' ').title()}: {v:.2%}" if isinstance(v, float) else f"{k.replace('_', ' ').title()}: {v}")
    
    # Add and run a custom scenario
    tester.add_custom_scenario('2022 Bear Market', '2022-01-01', '2022-10-01')
    print("\nRunning 2022 Bear Market Stress Test...")
    results_2022 = tester.run_stress_test('2022 Bear Market')
    
    # Run Monte Carlo simulation
    print("\nRunning Monte Carlo Simulation...")
    mc_results = tester.monte_carlo_simulation(days=30, simulations=1000)
    print("\nMonte Carlo Results (30-day projection):")
    for k, v in mc_results.items():
        print(f"{k.replace('_', ' ').title()}: {v:.2%}" if isinstance(v, float) else f"{k.replace('_', ' ').title()}: {v}")
