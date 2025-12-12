"""
Technical indicator calculations
"""

from typing import List
import math
from logger_config import get_logger

logger = get_logger(__name__)


class IndicatorCalculator:
    """Calculate technical indicators"""
    
    @staticmethod
    def calculate_rsi(closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0
        
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def calculate_ema(data: List[float], period: int) -> float:
        if len(data) < period:
            return data[-1] if data else 0
        
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    @staticmethod
    def calculate_adx(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 25.0
        
        # Simplified ADX calculation
        tr_list = []
        plus_dm = []
        minus_dm = []
        
        for i in range(1, len(closes)):
            high_diff = highs[i] - highs[i-1]
            low_diff = lows[i-1] - lows[i]
            
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
            tr_list.append(tr)
            
            plus_dm.append(high_diff if high_diff > low_diff and high_diff > 0 else 0)
            minus_dm.append(low_diff if low_diff > high_diff and low_diff > 0 else 0)
        
        if len(tr_list) < period:
            return 25.0
            
        atr = sum(tr_list[-period:]) / period
        if atr == 0:
            return 25.0
            
        plus_di = 100 * sum(plus_dm[-period:]) / period / atr
        minus_di = 100 * sum(minus_dm[-period:]) / period / atr
        
        if plus_di + minus_di == 0:
            return 25.0
            
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        return dx
    
    @staticmethod
    def calculate_chop(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0
        
        atr_sum = 0
        for i in range(-period, 0):
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
            atr_sum += tr
        
        highest_high = max(highs[-period:])
        lowest_low = min(lows[-period:])
        
        if highest_high == lowest_low:
            return 50.0
        
        chop = 100 * math.log10(atr_sum / (highest_high - lowest_low)) / math.log10(period)
        return max(0, min(100, chop))
    
    @staticmethod
    def calculate_kama(closes: List[float], period: int = 10, fast: int = 2, slow: int = 30) -> float:
        if len(closes) < period + 1:
            return closes[-1] if closes else 0
        
        change = abs(closes[-1] - closes[-period-1])
        volatility = sum(abs(closes[i] - closes[i-1]) for i in range(-period, 0))
        
        if volatility == 0:
            return closes[-1]
        
        er = change / volatility
        fast_sc = 2 / (fast + 1)
        slow_sc = 2 / (slow + 1)
        sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
        
        kama = closes[-period-1]
        for i in range(-period, 0):
            kama = kama + sc * (closes[i] - kama)
        
        return kama
    
    @staticmethod
    def calculate_all(ohlcv: List) -> dict:
        if not ohlcv or len(ohlcv) < 20:
            return {}
        
        opens = [c[1] for c in ohlcv]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        closes = [c[4] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]
        
        return {
            'rsi': round(IndicatorCalculator.calculate_rsi(closes), 2),
            'adx': round(IndicatorCalculator.calculate_adx(highs, lows, closes), 2),
            'chop': round(IndicatorCalculator.calculate_chop(highs, lows, closes), 2),
            'kama': round(IndicatorCalculator.calculate_kama(closes), 2),
            'ema_9': round(IndicatorCalculator.calculate_ema(closes, 9), 2),
            'ema_21': round(IndicatorCalculator.calculate_ema(closes, 21), 2),
            'sma_50': round(sum(closes[-50:]) / min(50, len(closes)), 2),
            'current_price': closes[-1],
            'volume': volumes[-1],
        }
