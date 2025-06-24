from backtesting import Backtest, Strategy
import talib
from backtesting.test import GOOG
import pandas as pd
from datetime import timedelta
import matplotlib.pyplot as plt
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

class GridTradingStrategy(Strategy):
    ema_short_period = 9
    ema_long_period = 21
    atr_period = 3
    number_of_levels = 5
    grid_spacing = 0.2
    stop_loss_factor = 2.5
    take_profit_factor = 0.5
    
    def init(self):
        self.ema_short = self.I(talib.EMA, self.data.Close, self.ema_short_period)
        self.ema_long = self.I(talib.EMA, self.data.Close, self.ema_long_period)
        self.atr = self.I(talib.ATR, self.data.High, self.data.Low, self.data.Close, self.atr_period)
        self.active = False
        self.traded_ltp = -1
        self.traded_atr = -1
        self.sl = -1
        self.tp = -1
        self.level = 1
        self.traded_prices = []  

        
    def next(self):
        atr = self.atr[-1]
        ltp = self.data.Close[-1]

        if self.position:
            if self.position.is_long:
                new_sl = ltp - (self.stop_loss_factor * self.traded_atr)
                if self.sl < new_sl:
                    self.sl = new_sl
                    self.position.sl = self.sl
            elif self.position.is_short:
                new_sl = ltp + (self.stop_loss_factor * self.traded_atr)
                if self.sl > new_sl:
                    self.sl = new_sl
                    self.position.sl = self.sl
        
        if self.ema_short > self.ema_long:
            if self.position and self.position.is_short:
                self.position.close()
                self.level = 1
                self.active = False
                self.traded_prices = []
                
            if not self.position:
                self.active = True
                self.traded_ltp = ltp
                self.traded_atr = atr
                self.sl = self.traded_ltp - (self.stop_loss_factor * self.traded_atr)
            
                self.buy(size=1, sl=self.sl)
                self.traded_prices.append(ltp)  
            
            else:
                if self.level < self.number_of_levels:
                    price_trigger = self.traded_ltp - (self.grid_spacing * self.level * self.traded_atr)
                    if ltp < price_trigger:
                        self.level += 1
                        size = 2 ** (self.level - 1)
                        new_sl = ltp - (self.stop_loss_factor * self.traded_atr)
                        self.buy(size=size, sl=new_sl)
                        self.traded_prices.append(ltp)
        
            if len(self.traded_prices) != 0:
                average_traded_price = sum(self.traded_prices) / len(self.traded_prices) 
                if (self.level > (self.number_of_levels/2)) and (ltp > average_traded_price):
                    self.position.close()
                    self.level = 1
                    self.active = False
                    self.traded_prices = []  
                    
                    
        elif self.ema_short < self.ema_long:
            if self.position and self.position.is_long:
                self.position.close()
                self.level = 1
                self.active = False
                self.traded_prices = []

            if not self.position:
                self.active = True
                self.traded_ltp = ltp
                self.traded_atr = atr
                self.sl = self.traded_ltp + (self.stop_loss_factor * self.traded_atr)
            
                self.sell(size=1, sl=self.sl)
                self.traded_prices.append(ltp)  
            
            else:
                if self.level < self.number_of_levels:
                    price_trigger = self.traded_ltp + (self.grid_spacing * self.level * self.traded_atr)
                    if ltp > price_trigger:
                        self.level += 1
                        size = 2 ** (self.level - 1)
                        new_sl = ltp + (self.stop_loss_factor * self.traded_atr)
                        self.sell(size=size, sl=new_sl)
                        self.traded_prices.append(ltp)
        
            if len(self.traded_prices) != 0:
                average_traded_price = sum(self.traded_prices) / len(self.traded_prices) 
                if (self.level > (self.number_of_levels/2)) and (ltp < average_traded_price):
                    self.position.close()
                    self.level = 1
                    self.active = False
                    self.traded_prices = []  
            
class WalkForwardOptimization:
    def __init__(self, data, strategy_class, cash=10_000, commission=0.002):
        self.data = data
        self.strategy_class = strategy_class
        self.cash = cash
        self.commission = commission
        self.results = []
        
    def run(self, training_period=84, test_period=42, step_days=42, optimization_params=None, maximize='Equity Final [$]'):
        
        if optimization_params is None:
            optimization_params = {
                'number_of_levels': [2, 5, 8],      
                'grid_spacing': [0.1, 0.3, 0.5],    
                'stop_loss_factor': [2, 3.5, 5],    
                'take_profit_factor': [0.5, 1.0, 1.5]  
            }
            
        if not isinstance(self.data.index, pd.DatetimeIndex):
            self.data.index = pd.to_datetime(self.data.index)
            
        start_date = self.data.index[0]
        end_date = self.data.index[-1]
        
        current_date = start_date
        period_count = 0
        
        while current_date + timedelta(training_period + test_period) <= end_date:
            period_count += 1
            
            training_start = current_date
            training_end = training_start + timedelta(training_period)
            
            test_start = training_end
            test_end = test_start + timedelta(test_period)
            
            training_data = self.data[training_start:training_end]
            test_data = self.data[test_start:test_end]
            
            # EMA long in strategy is approx 21 days, it should have atleast 3 periods thus >63 or nearly eqyal to >65
            # if (len(training_data)<65) or (len(test_data)<10): 
            #     current_date += timedelta(step_days)
            #     continue
            
            try:
                training_bt = Backtest(training_data, self.strategy_class, cash=self.cash, commission=self.commission)
                training_stats = training_bt.optimize(
                    **optimization_params,
                    maximize=maximize,
                    method="grid"
                )
                best_parameters = training_stats._strategy.__dict__
                
                test_bt = Backtest(test_data, self.strategy_class, cash=self.cash, commission=self.commission)
                
                for param, value in best_parameters.items():
                    setattr(test_bt._strategy, param, value)
                    
                test_stats = test_bt.run()
                
                result = {
                    'period': period_count,
                    'training_start': training_start,
                    'training_end': training_end,
                    'test_start': test_start,
                    'test_end': test_end,
                    'best_parameters': best_parameters,
                    'training_return': training_stats['Return [%]'],
                    'test_return': test_stats['Return [%]'],
                    'training_sharpe': training_stats['Sharpe Ratio'],
                    'test_sharpe': test_stats['Sharpe Ratio'],
                    'training_max_drawdown': training_stats['Max. Drawdown [%]'],
                    'test_max_drawdown': test_stats['Max. Drawdown [%]'],
                    'training_trades': training_stats['# Trades'],
                    'test_trades': test_stats['# Trades'],
                    'training_equity_final': training_stats['Equity Final [$]'],
                    'test_equity_final': test_stats['Equity Final [$]']
                }
                
                self.results.append(result)
                
            except Exception as e:
                print(f"Exception occurred in period {period_count}: {e}")
                
            
            current_date += timedelta(step_days)
            
        return self.results
    
    def get_summary(self):
        if not self.results:
            return None
        
        df = pd.DataFrame(self.results)
        
        summary = {
            'total_periods': len(df),
            'avg_training_return': df['training_return'].mean(),
            'avg_test_return': df['test_return'].mean(),
            'avg_training_sharpe': df['training_sharpe'].mean(),
            'avg_test_sharpe': df['test_sharpe'].mean(),
            'avg_training_drawdown': df['training_max_drawdown'].mean(),
            'avg_test_drawdown': df['test_max_drawdown'].mean(),
            'positive_test_periods': (df['test_return'] > 0).sum(),
            'positive_test_rate': (df['test_return'] > 0).mean() * 100,
            'best_test_return': df['test_return'].max(),
            'worst_test_return': df['test_return'].min(),
            'test_return_std': df['test_return'].std(),
            'cumulative_test_return': (1 + df['test_return'] / 100).prod() - 1
        }
        
        return summary
    
    def plot_results(self):
        if not self.results:
            print("No results to plot")
            return
        
        df = pd.DataFrame(self.results)
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        
        # Plot 1: Train vs Test Returns
        axes[0, 0].plot(df['period'], df['training_return'], 'b-', label='Training Return', alpha=0.7)
        axes[0, 0].plot(df['period'], df['test_return'], 'r-', label='Test Return', alpha=0.7)
        axes[0, 0].set_title('Training vs Test Returns')
        axes[0, 0].set_xlabel('Period')
        axes[0, 0].set_ylabel('Return (%)')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # Plot 2: Cumulative Returns
        cumulative_training = (1 + df['training_return'] / 100).cumprod() - 1
        cumulative_test = (1 + df['test_return'] / 100).cumprod() - 1
        axes[0, 1].plot(df['period'], cumulative_training * 100, 'b-', label='Cumulative Training', alpha=0.7)
        axes[0, 1].plot(df['period'], cumulative_test * 100, 'r-', label='Cumulative Test', alpha=0.7)
        axes[0, 1].set_title('Cumulative Returns')
        axes[0, 1].set_xlabel('Period')
        axes[0, 1].set_ylabel('Cumulative Return (%)')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # Plot 3: Sharpe Ratios
        axes[1, 0].plot(df['period'], df['training_sharpe'], 'b-', label='Training Sharpe', alpha=0.7)
        axes[1, 0].plot(df['period'], df['test_sharpe'], 'r-', label='Test Sharpe', alpha=0.7)
        axes[1, 0].set_title('Sharpe Ratios')
        axes[1, 0].set_xlabel('Period')
        axes[1, 0].set_ylabel('Sharpe Ratio')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        
        # Plot 4: Max Drawdowns
        axes[1, 1].plot(df['period'], df['training_max_drawdown'], 'b-', label='Training Max DD', alpha=0.7)
        axes[1, 1].plot(df['period'], df['test_max_drawdown'], 'r-', label='Test Max DD', alpha=0.7)
        axes[1, 1].set_title('Maximum Drawdowns')
        axes[1, 1].set_xlabel('Period')
        axes[1, 1].set_ylabel('Max Drawdown (%)')
        axes[1, 1].legend()
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.show()
        
        return fig
        
    def plot_walkforward_schedule(self):
        """
        Plots a Gantt-style chart showing training and test periods for each walk-forward window.
        Training periods are blue, test periods are orange.
        """
        if not self.results:
            print("No results to plot schedule.")
            return
        import matplotlib.dates as mdates
        import numpy as np
        df = pd.DataFrame(self.results)
        fig, ax = plt.subplots(figsize=(12, 4))
        for i, row in df.iterrows():
            # Training period
            ax.barh(
                y=row['period'],
                width=row['training_end'] - row['training_start'],
                left=row['training_start'],
                height=0.8,
                color='blue',
                edgecolor='black',
                label='Training' if i == 0 else ""
            )
            # Test period
            ax.barh(
                y=row['period'],
                width=row['test_end'] - row['test_start'],
                left=row['test_start'],
                height=0.8,
                color='orange',
                edgecolor='black',
                label='Test' if i == 0 else ""
            )
        ax.set_xlabel('Date')
        ax.set_ylabel('Walk-Forward Window')
        ax.invert_yaxis()
        ax.xaxis_date()
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.legend(loc='upper right')
        plt.tight_layout()
        plt.show()
        return fig
        
        
            
    
           
# Main Function
if __name__ == '__main__':
    # Normal Backtesting Code
    # bt = Backtest(GOOG, GridTradingStrategy, cash=10_000, commission=0.002)    
    # stats = bt.optimize(
    #     number_of_levels=[2, 10],
    #     grid_spacing=[0.1, 0.5],
    #     stop_loss_factor=[2, 5],
    #     take_profit_factor=[0.5, 1.5],
    #     maximize='Equity Final [$]',
    #     return_heatmap=True,
    #     method='grid'
    # )
    # bt.plot()
    # print(stats)

    # # To create a Tradebook
    # trades = stats[0]._trades
    # if not trades.empty:
    #     trades = trades.sort_values(by='EntryTime')
    #     trades.to_csv('tradebook.csv', index=False)
    #     print("Tradebook of the best strategy saved to tradebook.csv")
    # else:
    #     print("No trades were made in the best strategy run.")
        
        
        
        
    # Walk Forward Optimization Code
    wfo_instance = WalkForwardOptimization(GOOG, GridTradingStrategy, cash=10_000, commission=0.002)
    
    optimization_params = {
        'number_of_levels': [2],
        'grid_spacing': [0.1],
        'stop_loss_factor': [2],
        'take_profit_factor': [0.5]
    }
    
    results = wfo_instance.run(training_period=84, test_period=42, step_days=42, optimization_params=None, maximize='Equity Final [$]')
    
    summary = wfo_instance.get_summary()
    
    wfo_instance.plot_results()
    
    # Plot walk-forward schedule (Gantt-style)
    wfo_instance.plot_walkforward_schedule()
    
    # Save detailed results to CSV
    if results:
        results_df = pd.DataFrame(results)
        results_df.to_csv('walk_forward_results.csv', index=False)
        print("\nDetailed walk-forward results saved to 'walk_forward_results.csv'")
    
    
            
        
        