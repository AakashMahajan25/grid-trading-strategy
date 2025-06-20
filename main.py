from backtesting import Backtest, Strategy
import talib
from backtesting.test import GOOG
import pandas as pd

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
            
        
           
        
if __name__ == '__main__':
    bt = Backtest(GOOG, GridTradingStrategy, cash=10_000, commission=0.002)    
    stats = bt.optimize(
        number_of_levels=[2, 10],
        grid_spacing=[0.1, 0.5],
        stop_loss_factor=[2, 5],
        take_profit_factor=[0.5, 1.5],
        maximize='Equity Final [$]',
        return_heatmap=True
    )
    bt.plot()
    print(stats)

    # Extract and save the tradebook from the best run
    trades = stats[0]._trades
    if not trades.empty:
        trades = trades.sort_values(by='EntryTime')
        trades.to_csv('tradebook.csv', index=False)
        print("Tradebook of the best strategy saved to tradebook.csv")
    else:
        print("No trades were made in the best strategy run.")
            
        
        