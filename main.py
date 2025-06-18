from backtesting import Backtest, Strategy
import talib
from backtesting.test import GOOG

class GridTradingStrategy(Strategy):
    ATR_PERIOD = 14
    NUMBER_OF_LEVELS = 5
    STOP_LOSS_FACTOR = 1.2
    TAKE_PROFIT_FACTOR = 0.25
    
    def init(self):
        self.atr = self.I(talib.ATR, self.data.High, self.data.Low, self.data.Close, self.ATR_PERIOD)
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
        
        if not self.position:
            self.active = True
            self.traded_ltp = ltp
            self.traded_atr = atr
            self.sl = self.traded_ltp - (self.STOP_LOSS_FACTOR * self.traded_atr)
            self.tp = self.traded_ltp + (self.TAKE_PROFIT_FACTOR * self.traded_atr)
            
            self.buy(size=1, sl=self.sl, tp=self.tp)
            self.traded_prices.append(ltp)  
            
        else:
            for level in range(self.NUMBER_OF_LEVELS):
                price_trigger = self.traded_ltp - (0.2 * level * self.traded_atr)
                if (ltp < price_trigger):
                    self.level += 1
                    size = 2 ** self.level  
                    self.buy(size=size, sl=self.sl, tp=self.tp)
                    self.traded_prices.append(ltp)  
                    break
        
        if len(self.traded_prices) != 0:
            average_traded_price = sum(self.traded_prices) / len(self.traded_prices) 
            if (self.level > (self.NUMBER_OF_LEVELS/2)) and (ltp > average_traded_price):
                self.position.close()
                self.level = 1
                self.active = False
                self.traded_prices = []  
            
       
        
bt = Backtest(GOOG, GridTradingStrategy, cash=10_000, commission=0.002)    
stats = bt.run()
bt.plot()
print(stats)
            
        
        