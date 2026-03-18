"""
Institutional-grade technical indicator calculations for swing trading.

Includes:
  - Trend: EMA stack (9/21/50/200), Supertrend, Ichimoku Cloud
  - Momentum: RSI-14, Stochastic RSI, MACD (12/26/9), Williams %R, CMF
  - Volatility: ATR, Bollinger Bands, Keltner Channels, ADX/DI
  - Volume: OBV, VWAP, Volume MA ratio, MFI
  - Structure: Heikin Ashi candles, Pivot Points (Classic + Camarilla)
  - Regime: Choppiness Index, trend/ranging classifier
"""

from typing import List, Dict, Any, Optional, Tuple
import math
from logger_config import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ema(data: List[float], period: int) -> List[float]:
    if len(data) < period:
        return []
    k = 2.0 / (period + 1)
    result = [sum(data[:period]) / period]
    for price in data[period:]:
        result.append(price * k + result[-1] * (1 - k))
    return result


def _sma(data: List[float], period: int) -> List[float]:
    out = []
    for i in range(len(data)):
        if i < period - 1:
            out.append(float('nan'))
        else:
            out.append(sum(data[i - period + 1: i + 1]) / period)
    return out


def _stdev(data: List[float], period: int) -> List[float]:
    out = []
    for i in range(len(data)):
        if i < period - 1:
            out.append(float('nan'))
        else:
            window = data[i - period + 1: i + 1]
            mean = sum(window) / period
            variance = sum((x - mean) ** 2 for x in window) / period
            out.append(math.sqrt(variance))
    return out


def _true_range(highs: List[float], lows: List[float], closes: List[float]) -> List[float]:
    tr = [highs[0] - lows[0]]
    for i in range(1, len(closes)):
        tr.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        ))
    return tr


def _rma(data: List[float], period: int) -> List[float]:
    """Wilder's smoothed moving average (RMA)."""
    if len(data) < period:
        return []
    alpha = 1.0 / period
    result = [sum(data[:period]) / period]
    for x in data[period:]:
        result.append(alpha * x + (1 - alpha) * result[-1])
    return result


# ---------------------------------------------------------------------------
# Core indicator functions (return full series aligned to input length)
# ---------------------------------------------------------------------------

class IndicatorCalculator:
    """Institutional-grade indicator calculator for swing trading systems."""

    # ---- Trend indicators ------------------------------------------------

    @staticmethod
    def ema_series(closes: List[float], period: int) -> List[float]:
        raw = _ema(closes, period)
        padding = [float('nan')] * (len(closes) - len(raw))
        return padding + raw

    @staticmethod
    def sma_series(closes: List[float], period: int) -> List[float]:
        return _sma(closes, period)

    @staticmethod
    def supertrend(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        atr_period: int = 10,
        multiplier: float = 3.0,
    ) -> Tuple[List[float], List[int]]:
        """
        Supertrend indicator.
        Returns (supertrend_line, direction) where direction: 1=bullish, -1=bearish.
        """
        n = len(closes)
        tr = _true_range(highs, lows, closes)
        atr = _rma(tr, atr_period)
        atr_pad = [float('nan')] * (n - len(atr))
        atr_full = atr_pad + atr

        hl2 = [(h + l) / 2 for h, l in zip(highs, lows)]
        upper_band = [hl2[i] + multiplier * atr_full[i] for i in range(n)]
        lower_band = [hl2[i] - multiplier * atr_full[i] for i in range(n)]

        supertrend = [float('nan')] * n
        direction = [1] * n

        for i in range(atr_period, n):
            # Adjust bands
            if i > atr_period:
                if lower_band[i] < lower_band[i - 1] or closes[i - 1] < lower_band[i - 1]:
                    lower_band[i] = lower_band[i]
                else:
                    lower_band[i] = lower_band[i - 1]

                if upper_band[i] > upper_band[i - 1] or closes[i - 1] > upper_band[i - 1]:
                    upper_band[i] = upper_band[i]
                else:
                    upper_band[i] = upper_band[i - 1]

            # Determine direction
            if i == atr_period:
                direction[i] = 1
            elif supertrend[i - 1] == upper_band[i - 1]:
                direction[i] = -1 if closes[i] > upper_band[i] else 1
            else:
                direction[i] = 1 if closes[i] < lower_band[i] else -1

            supertrend[i] = lower_band[i] if direction[i] == -1 else upper_band[i]

        return supertrend, direction

    @staticmethod
    def ichimoku(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        tenkan_period: int = 9,
        kijun_period: int = 26,
        senkou_b_period: int = 52,
    ) -> Dict[str, List[float]]:
        """
        Ichimoku Cloud components:
          - Tenkan-sen (Conversion Line): 9-period mid
          - Kijun-sen (Base Line): 26-period mid
          - Senkou Span A (Leading Span A): avg of tenkan + kijun, shifted +26
          - Senkou Span B (Leading Span B): 52-period mid, shifted +26
          - Chikou Span (Lagging Span): close shifted -26
        """
        n = len(closes)

        def donchian_mid(period: int) -> List[float]:
            out = []
            for i in range(n):
                if i < period - 1:
                    out.append(float('nan'))
                else:
                    h = max(highs[i - period + 1: i + 1])
                    l = min(lows[i - period + 1: i + 1])
                    out.append((h + l) / 2)
            return out

        tenkan = donchian_mid(tenkan_period)
        kijun = donchian_mid(kijun_period)
        senkou_b_raw = donchian_mid(senkou_b_period)

        senkou_a = [float('nan')] * n
        senkou_b = [float('nan')] * n
        chikou = [float('nan')] * n

        for i in range(n):
            # Senkou A/B shifted forward 26 periods (we store current idx)
            if not math.isnan(tenkan[i]) and not math.isnan(kijun[i]):
                senkou_a[i] = (tenkan[i] + kijun[i]) / 2
            if not math.isnan(senkou_b_raw[i]):
                senkou_b[i] = senkou_b_raw[i]
            # Chikou = close shifted back 26
            if i >= kijun_period:
                chikou[i - kijun_period] = closes[i]

        return {
            "tenkan": tenkan,
            "kijun": kijun,
            "senkou_a": senkou_a,
            "senkou_b": senkou_b,
            "chikou": chikou,
        }

    # ---- Momentum indicators ---------------------------------------------

    @staticmethod
    def rsi(closes: List[float], period: int = 14) -> List[float]:
        n = len(closes)
        result = [float('nan')] * n
        if n < period + 1:
            return result

        deltas = [closes[i] - closes[i - 1] for i in range(1, n)]
        gains = [max(d, 0) for d in deltas]
        losses = [max(-d, 0) for d in deltas]

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        if avg_loss == 0:
            result[period] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[period] = 100 - (100 / (1 + rs))

        for i in range(period + 1, n):
            avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
            if avg_loss == 0:
                result[i] = 100.0
            else:
                rs = avg_gain / avg_loss
                result[i] = 100 - (100 / (1 + rs))

        return result

    @staticmethod
    def stoch_rsi(closes: List[float], rsi_period: int = 14, stoch_period: int = 14, k_smooth: int = 3, d_smooth: int = 3) -> Dict[str, List[float]]:
        """Stochastic RSI — smoother momentum oscillator than plain RSI."""
        rsi_vals = IndicatorCalculator.rsi(closes, rsi_period)
        n = len(closes)
        k_raw = [float('nan')] * n

        for i in range(n):
            if i < rsi_period + stoch_period - 2:
                continue
            window = [v for v in rsi_vals[i - stoch_period + 1: i + 1] if not math.isnan(v)]
            if len(window) < stoch_period:
                continue
            lo, hi = min(window), max(window)
            if hi == lo:
                k_raw[i] = 50.0
            else:
                k_raw[i] = 100 * (rsi_vals[i] - lo) / (hi - lo)

        # Smooth K and D
        def smooth_nan(data: List[float], period: int) -> List[float]:
            out = [float('nan')] * len(data)
            buf = []
            for i, v in enumerate(data):
                if math.isnan(v):
                    buf = []
                    continue
                buf.append(v)
                if len(buf) >= period:
                    out[i] = sum(buf[-period:]) / period
            return out

        k_line = smooth_nan(k_raw, k_smooth)
        d_line = smooth_nan(k_line, d_smooth)
        return {"stoch_k": k_line, "stoch_d": d_line}

    @staticmethod
    def macd(
        closes: List[float],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> Dict[str, List[float]]:
        n = len(closes)
        fast_ema = _ema(closes, fast)
        slow_ema = _ema(closes, slow)
        # Align: slow_ema is shorter by (slow-fast) elements
        offset = slow - fast
        macd_line_raw = [f - s for f, s in zip(fast_ema[offset:], slow_ema)]
        signal_line_raw = _ema(macd_line_raw, signal)
        hist_raw = [m - s for m, s in zip(macd_line_raw[signal - 1:], signal_line_raw)]

        pad_macd = [float('nan')] * (n - len(macd_line_raw))
        pad_signal = [float('nan')] * (n - len(signal_line_raw))
        pad_hist = [float('nan')] * (n - len(hist_raw))

        return {
            "macd": pad_macd + macd_line_raw,
            "signal": pad_signal + signal_line_raw,
            "histogram": pad_hist + hist_raw,
        }

    @staticmethod
    def williams_r(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
        """Williams %R — measures overbought/oversold (-80 to -100 = oversold, 0 to -20 = overbought)."""
        n = len(closes)
        out = [float('nan')] * n
        for i in range(period - 1, n):
            h = max(highs[i - period + 1: i + 1])
            l = min(lows[i - period + 1: i + 1])
            if h == l:
                out[i] = -50.0
            else:
                out[i] = -100 * (h - closes[i]) / (h - l)
        return out

    @staticmethod
    def cmf(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float],
        period: int = 20,
    ) -> List[float]:
        """Chaikin Money Flow — positive = buying pressure, negative = selling pressure."""
        n = len(closes)
        mf_volume = []
        for i in range(n):
            hl = highs[i] - lows[i]
            if hl == 0:
                mf_volume.append(0.0)
            else:
                mf_mult = ((closes[i] - lows[i]) - (highs[i] - closes[i])) / hl
                mf_volume.append(mf_mult * volumes[i])

        out = [float('nan')] * n
        for i in range(period - 1, n):
            sum_mfv = sum(mf_volume[i - period + 1: i + 1])
            sum_vol = sum(volumes[i - period + 1: i + 1])
            out[i] = sum_mfv / sum_vol if sum_vol != 0 else 0.0
        return out

    # ---- Volatility indicators -------------------------------------------

    @staticmethod
    def atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
        tr = _true_range(highs, lows, closes)
        atr_raw = _rma(tr, period)
        padding = [float('nan')] * (len(closes) - len(atr_raw))
        return padding + atr_raw

    @staticmethod
    def bollinger_bands(closes: List[float], period: int = 20, std_dev: float = 2.0) -> Dict[str, List[float]]:
        middle = _sma(closes, period)
        std = _stdev(closes, period)
        upper = [m + std_dev * s if not math.isnan(m) else float('nan') for m, s in zip(middle, std)]
        lower = [m - std_dev * s if not math.isnan(m) else float('nan') for m, s in zip(middle, std)]
        bandwidth = [(u - l) / m if not math.isnan(m) and m != 0 else float('nan') for u, l, m in zip(upper, lower, middle)]
        n = len(closes)
        percent_b = [float('nan')] * n
        for i in range(n):
            if not math.isnan(upper[i]) and upper[i] != lower[i]:
                percent_b[i] = (closes[i] - lower[i]) / (upper[i] - lower[i]) * 100
        return {"upper": upper, "middle": middle, "lower": lower, "bandwidth": bandwidth, "percent_b": percent_b}

    @staticmethod
    def keltner_channels(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        ema_period: int = 20,
        atr_period: int = 10,
        multiplier: float = 1.5,
    ) -> Dict[str, List[float]]:
        """Keltner Channels — complements Bollinger Bands for squeeze detection."""
        ema = IndicatorCalculator.ema_series(closes, ema_period)
        atr_vals = IndicatorCalculator.atr(highs, lows, closes, atr_period)
        upper = [e + multiplier * a if not math.isnan(e) and not math.isnan(a) else float('nan')
                 for e, a in zip(ema, atr_vals)]
        lower = [e - multiplier * a if not math.isnan(e) and not math.isnan(a) else float('nan')
                 for e, a in zip(ema, atr_vals)]
        return {"upper": upper, "middle": ema, "lower": lower}

    @staticmethod
    def adx(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Dict[str, List[float]]:
        """ADX with +DI and -DI directional indicators."""
        n = len(closes)
        tr = _true_range(highs, lows, closes)
        plus_dm, minus_dm = [], []
        for i in range(1, n):
            h_diff = highs[i] - highs[i - 1]
            l_diff = lows[i - 1] - lows[i]
            plus_dm.append(h_diff if h_diff > l_diff and h_diff > 0 else 0.0)
            minus_dm.append(l_diff if l_diff > h_diff and l_diff > 0 else 0.0)

        atr_rma = _rma(tr[1:], period)
        plus_di_rma = _rma(plus_dm, period)
        minus_di_rma = _rma(minus_dm, period)

        plus_di = [100 * p / a if a != 0 else 0.0 for p, a in zip(plus_di_rma, atr_rma)]
        minus_di = [100 * m / a if a != 0 else 0.0 for m, a in zip(minus_di_rma, atr_rma)]

        dx = []
        for p, m in zip(plus_di, minus_di):
            s = p + m
            dx.append(100 * abs(p - m) / s if s != 0 else 0.0)

        adx_raw = _rma(dx, period)
        pad = [float('nan')] * (n - len(adx_raw))

        return {
            "adx": pad + adx_raw,
            "plus_di": [float('nan')] * (n - len(plus_di)) + plus_di,
            "minus_di": [float('nan')] * (n - len(minus_di)) + minus_di,
        }

    # ---- Volume indicators -----------------------------------------------

    @staticmethod
    def obv(closes: List[float], volumes: List[float]) -> List[float]:
        """On Balance Volume — cumulative volume-weighted directional pressure."""
        out = [volumes[0]]
        for i in range(1, len(closes)):
            if closes[i] > closes[i - 1]:
                out.append(out[-1] + volumes[i])
            elif closes[i] < closes[i - 1]:
                out.append(out[-1] - volumes[i])
            else:
                out.append(out[-1])
        return out

    @staticmethod
    def vwap(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float],
    ) -> List[float]:
        """Session VWAP — anchored to start of provided data window."""
        typical = [(h + l + c) / 3 for h, l, c in zip(highs, lows, closes)]
        cum_pv = 0.0
        cum_v = 0.0
        out = []
        for tp, vol in zip(typical, volumes):
            cum_pv += tp * vol
            cum_v += vol
            out.append(cum_pv / cum_v if cum_v != 0 else tp)
        return out

    @staticmethod
    def mfi(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float],
        period: int = 14,
    ) -> List[float]:
        """Money Flow Index — volume-weighted RSI."""
        n = len(closes)
        typical = [(h + l + c) / 3 for h, l, c in zip(highs, lows, closes)]
        out = [float('nan')] * n

        for i in range(period, n):
            pos_mf = sum(
                typical[j] * volumes[j]
                for j in range(i - period + 1, i + 1)
                if typical[j] > typical[j - 1]
            )
            neg_mf = sum(
                typical[j] * volumes[j]
                for j in range(i - period + 1, i + 1)
                if typical[j] < typical[j - 1]
            )
            if neg_mf == 0:
                out[i] = 100.0
            else:
                mf_ratio = pos_mf / neg_mf
                out[i] = 100 - (100 / (1 + mf_ratio))

        return out

    # ---- Structure indicators --------------------------------------------

    @staticmethod
    def heikin_ashi(
        opens: List[float],
        highs: List[float],
        lows: List[float],
        closes: List[float],
    ) -> Dict[str, List[float]]:
        """Heikin Ashi candles — smoothed candles that filter noise."""
        n = len(closes)
        ha_close = [(opens[i] + highs[i] + lows[i] + closes[i]) / 4 for i in range(n)]
        ha_open = [float('nan')] * n
        ha_open[0] = (opens[0] + closes[0]) / 2
        for i in range(1, n):
            ha_open[i] = (ha_open[i - 1] + ha_close[i - 1]) / 2
        ha_high = [max(highs[i], ha_open[i], ha_close[i]) for i in range(n)]
        ha_low = [min(lows[i], ha_open[i], ha_close[i]) for i in range(n)]
        return {"open": ha_open, "high": ha_high, "low": ha_low, "close": ha_close}

    @staticmethod
    def pivot_points(
        prev_high: float,
        prev_low: float,
        prev_close: float,
    ) -> Dict[str, float]:
        """
        Classic pivot points + Camarilla levels.
        Used to identify key S/R levels for swing trade entries/exits.
        """
        pp = (prev_high + prev_low + prev_close) / 3
        r1 = 2 * pp - prev_low
        s1 = 2 * pp - prev_high
        r2 = pp + (prev_high - prev_low)
        s2 = pp - (prev_high - prev_low)
        r3 = prev_high + 2 * (pp - prev_low)
        s3 = prev_low - 2 * (prev_high - pp)

        # Camarilla
        rng = prev_high - prev_low
        c_r4 = prev_close + rng * 1.1 / 2
        c_r3 = prev_close + rng * 1.1 / 4
        c_s3 = prev_close - rng * 1.1 / 4
        c_s4 = prev_close - rng * 1.1 / 2

        return {
            "pp": round(pp, 4),
            "r1": round(r1, 4), "r2": round(r2, 4), "r3": round(r3, 4),
            "s1": round(s1, 4), "s2": round(s2, 4), "s3": round(s3, 4),
            "cam_r4": round(c_r4, 4), "cam_r3": round(c_r3, 4),
            "cam_s3": round(c_s3, 4), "cam_s4": round(c_s4, 4),
        }

    # ---- Regime classifiers ----------------------------------------------

    @staticmethod
    def choppiness_index(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14,
    ) -> List[float]:
        """
        Choppiness Index:
          < 38.2 = strongly trending
          > 61.8 = choppy / ranging
          38.2–61.8 = neutral
        """
        n = len(closes)
        tr = _true_range(highs, lows, closes)
        out = [float('nan')] * n

        for i in range(period, n):
            atr_sum = sum(tr[i - period + 1: i + 1])
            h = max(highs[i - period + 1: i + 1])
            l = min(lows[i - period + 1: i + 1])
            if h == l or atr_sum == 0:
                out[i] = 50.0
                continue
            chop = 100 * math.log10(atr_sum / (h - l)) / math.log10(period)
            out[i] = max(0, min(100, chop))

        return out

    @staticmethod
    def market_regime(
        closes: List[float],
        atr_vals: List[float],
        adx_vals: List[float],
        chop_vals: List[float],
    ) -> str:
        """
        Classify current market regime based on multiple signals.
        Returns: 'strong_uptrend' | 'strong_downtrend' | 'weak_uptrend' |
                 'weak_downtrend' | 'ranging' | 'high_volatility_breakout'
        """
        if not closes or len(closes) < 20:
            return 'unknown'

        # Use last valid values
        def last_valid(lst: List[float]) -> Optional[float]:
            for v in reversed(lst):
                if v is not None and not math.isnan(v):
                    return v
            return None

        adx = last_valid(adx_vals) or 25
        chop = last_valid(chop_vals) or 50
        atr_curr = last_valid(atr_vals) or 0
        price = closes[-1]
        atr_pct = atr_curr / price * 100 if price > 0 else 0

        # EMA slope: is 20-bar EMA rising?
        ema20 = _ema(closes, 20)
        ema_slope = (ema20[-1] - ema20[-5]) / ema20[-5] * 100 if len(ema20) >= 5 else 0

        if chop < 38.2 and adx > 25:
            return 'strong_uptrend' if ema_slope > 0 else 'strong_downtrend'
        elif chop < 50 and adx > 20:
            return 'weak_uptrend' if ema_slope > 0 else 'weak_downtrend'
        elif atr_pct > 3 and adx < 25:
            return 'high_volatility_breakout'
        else:
            return 'ranging'

    # ---- Composite calculate_all -----------------------------------------

    @staticmethod
    def calculate_all(ohlcv: List) -> Dict[str, Any]:
        """
        Full institutional indicator suite from OHLCV list.
        Each entry: [timestamp, open, high, low, close, volume]
        Returns latest scalar values + key series (last 20 bars).
        """
        if not ohlcv or len(ohlcv) < 52:
            # Need at least 52 bars for Ichimoku Senkou B
            return {}

        opens   = [c[1] for c in ohlcv]
        highs   = [c[2] for c in ohlcv]
        lows    = [c[3] for c in ohlcv]
        closes  = [c[4] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]

        def last(lst: List[float]) -> Optional[float]:
            for v in reversed(lst):
                if v is not None and not math.isnan(v):
                    return round(v, 6)
            return None

        def tail(lst: List[float], n: int = 20) -> List[Optional[float]]:
            out = []
            for v in lst[-n:]:
                out.append(None if math.isnan(v) else round(v, 6))
            return out

        # --- Trend
        ema9  = IndicatorCalculator.ema_series(closes, 9)
        ema21 = IndicatorCalculator.ema_series(closes, 21)
        ema50 = IndicatorCalculator.ema_series(closes, 50)
        ema200 = IndicatorCalculator.ema_series(closes, 200) if len(closes) >= 200 else [float('nan')] * len(closes)
        st_line, st_dir = IndicatorCalculator.supertrend(highs, lows, closes)
        ichi = IndicatorCalculator.ichimoku(highs, lows, closes)

        # --- Momentum
        rsi14 = IndicatorCalculator.rsi(closes, 14)
        stoch = IndicatorCalculator.stoch_rsi(closes)
        macd_data = IndicatorCalculator.macd(closes)
        wpr = IndicatorCalculator.williams_r(highs, lows, closes)
        cmf_data = IndicatorCalculator.cmf(highs, lows, closes, volumes)

        # --- Volatility
        atr14 = IndicatorCalculator.atr(highs, lows, closes, 14)
        bb = IndicatorCalculator.bollinger_bands(closes)
        kc = IndicatorCalculator.keltner_channels(highs, lows, closes)
        adx_data = IndicatorCalculator.adx(highs, lows, closes)

        # --- Volume
        obv_data = IndicatorCalculator.obv(closes, volumes)
        vwap_data = IndicatorCalculator.vwap(highs, lows, closes, volumes)
        mfi14 = IndicatorCalculator.mfi(highs, lows, closes, volumes)

        # --- Structure
        ha = IndicatorCalculator.heikin_ashi(opens, highs, lows, closes)
        pivots = IndicatorCalculator.pivot_points(highs[-2], lows[-2], closes[-2])

        # --- Regime
        chop_data = IndicatorCalculator.choppiness_index(highs, lows, closes)
        regime = IndicatorCalculator.market_regime(closes, atr14, adx_data["adx"], chop_data)

        # Bollinger squeeze: BB bandwidth < KC bandwidth
        bb_bw = last(bb["bandwidth"]) or 0
        kc_upper = last(kc["upper"]) or 0
        kc_lower = last(kc["lower"]) or 0
        kc_mid = last(kc["middle"]) or 1
        kc_bw = (kc_upper - kc_lower) / kc_mid if kc_mid else 0
        bb_squeeze = bb_bw < kc_bw

        return {
            # Scalars for quick LLM consumption
            "price":         round(closes[-1], 6),
            "regime":        regime,
            "bb_squeeze":    bb_squeeze,

            # Trend
            "ema_9":         last(ema9),
            "ema_21":        last(ema21),
            "ema_50":        last(ema50),
            "ema_200":       last(ema200),
            "ema_stack":     "bullish" if (last(ema9) or 0) > (last(ema21) or 0) > (last(ema50) or 0) else
                             "bearish" if (last(ema9) or 0) < (last(ema21) or 0) < (last(ema50) or 0) else "mixed",
            "supertrend":    last(st_line),
            "supertrend_dir": "bullish" if (st_dir[-1] == -1) else "bearish",
            "ichi_tenkan":   last(ichi["tenkan"]),
            "ichi_kijun":    last(ichi["kijun"]),
            "ichi_senkou_a": last(ichi["senkou_a"]),
            "ichi_senkou_b": last(ichi["senkou_b"]),
            "price_vs_cloud": "above" if closes[-1] > max(last(ichi["senkou_a"]) or 0, last(ichi["senkou_b"]) or 0)
                              else "below" if closes[-1] < min(last(ichi["senkou_a"]) or 0, last(ichi["senkou_b"]) or 0)
                              else "inside",

            # Momentum
            "rsi":           last(rsi14),
            "stoch_k":       last(stoch["stoch_k"]),
            "stoch_d":       last(stoch["stoch_d"]),
            "macd":          last(macd_data["macd"]),
            "macd_signal":   last(macd_data["signal"]),
            "macd_hist":     last(macd_data["histogram"]),
            "macd_cross":    "bullish" if (last(macd_data["histogram"]) or 0) > 0 else "bearish",
            "williams_r":    last(wpr),
            "cmf":           last(cmf_data),

            # Volatility
            "atr":           last(atr14),
            "atr_pct":       round(last(atr14) / closes[-1] * 100, 3) if closes[-1] else None,
            "bb_upper":      last(bb["upper"]),
            "bb_middle":     last(bb["middle"]),
            "bb_lower":      last(bb["lower"]),
            "bb_pct_b":      last(bb["percent_b"]),
            "adx":           last(adx_data["adx"]),
            "plus_di":       last(adx_data["plus_di"]),
            "minus_di":      last(adx_data["minus_di"]),
            "chop":          last(chop_data),

            # Volume
            "obv":           last(obv_data),
            "vwap":          last(vwap_data),
            "mfi":           last(mfi14),
            "volume":        round(volumes[-1], 2),
            "volume_ma20":   round(sum(volumes[-20:]) / 20, 2),
            "volume_ratio":  round(volumes[-1] / (sum(volumes[-20:]) / 20), 3) if volumes else None,

            # Structure
            "ha_close":      last(ha["close"]),
            "ha_open":       last(ha["open"]),
            "ha_bullish":    (last(ha["close"]) or 0) > (last(ha["open"]) or 0),
            "pivots":        pivots,

            # Series (last 20 bars) for trend context
            "rsi_series":    tail(rsi14),
            "macd_hist_series": tail(macd_data["histogram"]),
            "adx_series":    tail(adx_data["adx"]),
        }
