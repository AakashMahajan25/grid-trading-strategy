from backtesting import Backtest, Strategy
import talib
from backtesting.test import GOOG

class GridTradingStrategy(Strategy):
    ATR_PERIOD = 14
    
    def init(self):
        self.atr = self.I(talib.ATR, self.data.High, self.data.Low, self.data.Close, self.ATR_PERIOD)
        self.active = False
        self.traded_ltp = -1
        self.traded_atr = -1
        self.sl = -1
        self.tp = -1
        self.level = 0
    
    def next(self):
        atr = self.atr[-1]
        ltp = self.data.Close[-1]
        
        if not self.position:
            self.active = True
            self.traded_ltp = ltp
            self.traded_atr = atr
            self.sl = self.traded_ltp - (1.2 * self.traded_atr)
            self.tp = self.traded_ltp + (0.25 * self.traded_atr)
            
            self.buy(size=1, sl=self.sl, tp=self.tp)
            
        elif (ltp < (self.traded_ltp - 0.2*self.traded_atr)) and (self.level == 0):
            self.level = self.level + 1
            self.buy(size=2, sl=self.sl, tp=self.tp)
            
        elif (ltp < (self.traded_ltp - 0.4*self.traded_atr)) and (self.level == 1):
            self.level = self.level + 1
            self.buy(size=4, sl=self.sl, tp=self.tp)
            
        elif (ltp < (self.traded_ltp - 0.6*self.traded_atr)) and (self.level == 2):
            self.level = self.level + 1
            self.buy(size=8, sl=self.sl, tp=self.tp)
            
        elif (ltp < (self.traded_ltp - 0.8*self.traded_atr)) and (self.level == 3):
            self.level = self.level + 1
            self.buy(size=16, sl=self.sl, tp=self.tp)
            
        if (self.level > 2) and (ltp > (self.traded_ltp - 0.5*self.traded_atr)):
            self.position.close()
            self.level = 0
            self.active = False
            
       
        
bt = Backtest(GOOG, GridTradingStrategy, cash=10_000, commission=0.002)    
stats = bt.run()
bt.plot()
print(stats)
            
        
        