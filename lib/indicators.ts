/**
 * Technical Indicators Library
 * Calculates various trading indicators from kline data
 */

export interface KlineData {
  timestamp: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface IndicatorResults {
  rsi?: number
  macd?: {
    macd: number
    signal: number
    histogram: number
  }
  ema?: {
    ema9: number
    ema21: number
    ema50: number
    ema200: number
  }
  sma?: {
    sma20: number
    sma50: number
    sma200: number
  }
  bollinger?: {
    upper: number
    middle: number
    lower: number
    bandwidth: number
  }
  atr?: number
  adx?: {
    adx: number
    plusDI: number
    minusDI: number
  }
  stochastic?: {
    k: number
    d: number
  }
  obv?: number
  vwap?: number
}

/**
 * Calculate RSI (Relative Strength Index)
 */
export function calculateRSI(closes: number[], period: number = 14): number | undefined {
  if (closes.length < period + 1) return undefined

  let gains = 0
  let losses = 0

  // Calculate initial average gains and losses
  for (let i = 1; i <= period; i++) {
    const change = closes[i] - closes[i - 1]
    if (change > 0) gains += change
    else losses += Math.abs(change)
  }

  let avgGain = gains / period
  let avgLoss = losses / period

  // Calculate subsequent values using smoothed averages
  for (let i = period + 1; i < closes.length; i++) {
    const change = closes[i] - closes[i - 1]
    const gain = change > 0 ? change : 0
    const loss = change < 0 ? Math.abs(change) : 0

    avgGain = (avgGain * (period - 1) + gain) / period
    avgLoss = (avgLoss * (period - 1) + loss) / period
  }

  if (avgLoss === 0) return 100
  const rs = avgGain / avgLoss
  const rsi = 100 - 100 / (1 + rs)

  return Math.round(rsi * 100) / 100
}

/**
 * Calculate MACD (Moving Average Convergence Divergence)
 */
export function calculateMACD(
  closes: number[],
  fastPeriod: number = 12,
  slowPeriod: number = 26,
  signalPeriod: number = 9,
): { macd: number; signal: number; histogram: number } | undefined {
  if (closes.length < slowPeriod + signalPeriod) return undefined

  const fastEMA = calculateEMA(closes, fastPeriod)
  const slowEMA = calculateEMA(closes, slowPeriod)

  if (!fastEMA || !slowEMA) return undefined

  const macdLine = fastEMA - slowEMA

  // Calculate signal line (EMA of MACD line)
  // For this we need historical MACD values
  const macdValues: number[] = []
  for (let i = slowPeriod - 1; i < closes.length; i++) {
    const fast = calculateEMAAtIndex(closes.slice(0, i + 1), fastPeriod)
    const slow = calculateEMAAtIndex(closes.slice(0, i + 1), slowPeriod)
    if (fast !== undefined && slow !== undefined) {
      macdValues.push(fast - slow)
    }
  }

  const signalLine = calculateEMA(macdValues, signalPeriod) ?? 0
  const histogram = macdLine - signalLine

  return {
    macd: Math.round(macdLine * 100) / 100,
    signal: Math.round(signalLine * 100) / 100,
    histogram: Math.round(histogram * 100) / 100,
  }
}

/**
 * Calculate EMA (Exponential Moving Average)
 */
export function calculateEMA(values: number[], period: number): number | undefined {
  return calculateEMAAtIndex(values, period)
}

function calculateEMAAtIndex(values: number[], period: number): number | undefined {
  if (values.length < period) return undefined

  const multiplier = 2 / (period + 1)
  let ema = values.slice(0, period).reduce((sum, val) => sum + val, 0) / period

  for (let i = period; i < values.length; i++) {
    ema = (values[i] - ema) * multiplier + ema
  }

  return Math.round(ema * 100) / 100
}

/**
 * Calculate multiple EMAs at once
 */
export function calculateEMAs(
  closes: number[],
  periods: number[] = [9, 21, 50, 200],
): { [key: string]: number } | undefined {
  const result: { [key: string]: number } = {}

  for (const period of periods) {
    const ema = calculateEMA(closes, period)
    if (ema === undefined) return undefined
    result[`ema${period}`] = ema
  }

  return result
}

/**
 * Calculate SMA (Simple Moving Average)
 */
export function calculateSMA(values: number[], period: number): number | undefined {
  if (values.length < period) return undefined

  const sum = values.slice(-period).reduce((acc, val) => acc + val, 0)
  return Math.round((sum / period) * 100) / 100
}

/**
 * Calculate multiple SMAs at once
 */
export function calculateSMAs(
  closes: number[],
  periods: number[] = [20, 50, 200],
): { [key: string]: number } | undefined {
  const result: { [key: string]: number } = {}

  for (const period of periods) {
    const sma = calculateSMA(closes, period)
    if (sma === undefined) return undefined
    result[`sma${period}`] = sma
  }

  return result
}

/**
 * Calculate Bollinger Bands
 */
export function calculateBollingerBands(
  closes: number[],
  period: number = 20,
  stdDev: number = 2,
): { upper: number; middle: number; lower: number; bandwidth: number } | undefined {
  if (closes.length < period) return undefined

  const sma = calculateSMA(closes, period)
  if (sma === undefined) return undefined

  const slicedCloses = closes.slice(-period)
  const squaredDiffs = slicedCloses.map((close) => Math.pow(close - sma, 2))
  const variance = squaredDiffs.reduce((sum, val) => sum + val, 0) / period
  const standardDeviation = Math.sqrt(variance)

  const upper = sma + stdDev * standardDeviation
  const lower = sma - stdDev * standardDeviation
  const bandwidth = ((upper - lower) / sma) * 100

  return {
    upper: Math.round(upper * 100) / 100,
    middle: Math.round(sma * 100) / 100,
    lower: Math.round(lower * 100) / 100,
    bandwidth: Math.round(bandwidth * 100) / 100,
  }
}

/**
 * Calculate ATR (Average True Range)
 */
export function calculateATR(klines: KlineData[], period: number = 14): number | undefined {
  if (klines.length < period + 1) return undefined

  const trueRanges: number[] = []

  for (let i = 1; i < klines.length; i++) {
    const high = klines[i].high
    const low = klines[i].low
    const prevClose = klines[i - 1].close

    const tr = Math.max(high - low, Math.abs(high - prevClose), Math.abs(low - prevClose))

    trueRanges.push(tr)
  }

  // Calculate ATR as smoothed average
  let atr = trueRanges.slice(0, period).reduce((sum, tr) => sum + tr, 0) / period

  for (let i = period; i < trueRanges.length; i++) {
    atr = (atr * (period - 1) + trueRanges[i]) / period
  }

  return Math.round(atr * 100) / 100
}

/**
 * Calculate ADX (Average Directional Index)
 */
export function calculateADX(
  klines: KlineData[],
  period: number = 14,
): { adx: number; plusDI: number; minusDI: number } | undefined {
  if (klines.length < period * 2) return undefined

  const plusDM: number[] = []
  const minusDM: number[] = []
  const tr: number[] = []

  // Calculate +DM, -DM, and TR
  for (let i = 1; i < klines.length; i++) {
    const highDiff = klines[i].high - klines[i - 1].high
    const lowDiff = klines[i - 1].low - klines[i].low

    plusDM.push(highDiff > lowDiff && highDiff > 0 ? highDiff : 0)
    minusDM.push(lowDiff > highDiff && lowDiff > 0 ? lowDiff : 0)

    const high = klines[i].high
    const low = klines[i].low
    const prevClose = klines[i - 1].close
    tr.push(Math.max(high - low, Math.abs(high - prevClose), Math.abs(low - prevClose)))
  }

  // Calculate smoothed +DM, -DM, and TR
  let smoothedPlusDM = plusDM.slice(0, period).reduce((sum, val) => sum + val, 0)
  let smoothedMinusDM = minusDM.slice(0, period).reduce((sum, val) => sum + val, 0)
  let smoothedTR = tr.slice(0, period).reduce((sum, val) => sum + val, 0)

  for (let i = period; i < plusDM.length; i++) {
    smoothedPlusDM = smoothedPlusDM - smoothedPlusDM / period + plusDM[i]
    smoothedMinusDM = smoothedMinusDM - smoothedMinusDM / period + minusDM[i]
    smoothedTR = smoothedTR - smoothedTR / period + tr[i]
  }

  // Calculate +DI and -DI
  const plusDI = (smoothedPlusDM / smoothedTR) * 100
  const minusDI = (smoothedMinusDM / smoothedTR) * 100

  // Calculate DX
  const dx = (Math.abs(plusDI - minusDI) / (plusDI + minusDI)) * 100

  // Calculate ADX (smoothed DX)
  const dxValues: number[] = []
  for (let i = period - 1; i < plusDM.length; i++) {
    let sPlusDM = plusDM.slice(i - period + 1, i + 1).reduce((sum, val) => sum + val, 0)
    let sMinusDM = minusDM.slice(i - period + 1, i + 1).reduce((sum, val) => sum + val, 0)
    let sTR = tr.slice(i - period + 1, i + 1).reduce((sum, val) => sum + val, 0)

    const pDI = (sPlusDM / sTR) * 100
    const mDI = (sMinusDM / sTR) * 100
    dxValues.push((Math.abs(pDI - mDI) / (pDI + mDI)) * 100)
  }

  const adx = calculateSMA(dxValues, period) ?? dx

  return {
    adx: Math.round(adx * 100) / 100,
    plusDI: Math.round(plusDI * 100) / 100,
    minusDI: Math.round(minusDI * 100) / 100,
  }
}

/**
 * Calculate Stochastic Oscillator
 */
export function calculateStochastic(
  klines: KlineData[],
  kPeriod: number = 14,
  dPeriod: number = 3,
): { k: number; d: number } | undefined {
  if (klines.length < kPeriod + dPeriod) return undefined

  const recentKlines = klines.slice(-kPeriod)
  const highestHigh = Math.max(...recentKlines.map((k) => k.high))
  const lowestLow = Math.min(...recentKlines.map((k) => k.low))
  const currentClose = klines[klines.length - 1].close

  const k = ((currentClose - lowestLow) / (highestHigh - lowestLow)) * 100

  // Calculate %D (SMA of %K)
  const kValues: number[] = []
  for (let i = kPeriod - 1; i < klines.length; i++) {
    const slice = klines.slice(i - kPeriod + 1, i + 1)
    const high = Math.max(...slice.map((k) => k.high))
    const low = Math.min(...slice.map((k) => k.low))
    const close = klines[i].close
    kValues.push(((close - low) / (high - low)) * 100)
  }

  const d = calculateSMA(kValues, dPeriod) ?? k

  return {
    k: Math.round(k * 100) / 100,
    d: Math.round(d * 100) / 100,
  }
}

/**
 * Calculate OBV (On-Balance Volume)
 */
export function calculateOBV(klines: KlineData[]): number | undefined {
  if (klines.length < 2) return undefined

  let obv = 0

  for (let i = 1; i < klines.length; i++) {
    if (klines[i].close > klines[i - 1].close) {
      obv += klines[i].volume
    } else if (klines[i].close < klines[i - 1].close) {
      obv -= klines[i].volume
    }
  }

  return Math.round(obv)
}

/**
 * Calculate VWAP (Volume Weighted Average Price)
 */
export function calculateVWAP(klines: KlineData[]): number | undefined {
  if (klines.length === 0) return undefined

  let totalVolumePrice = 0
  let totalVolume = 0

  for (const kline of klines) {
    const typicalPrice = (kline.high + kline.low + kline.close) / 3
    totalVolumePrice += typicalPrice * kline.volume
    totalVolume += kline.volume
  }

  if (totalVolume === 0) return undefined

  return Math.round((totalVolumePrice / totalVolume) * 100) / 100
}

/**
 * Calculate all indicators
 */
export function calculateAllIndicators(klines: KlineData[]): IndicatorResults {
  const closes = klines.map((k) => k.close)

  const results: IndicatorResults = {}

  // Calculate RSI
  const rsi = calculateRSI(closes, 14)
  if (rsi !== undefined) results.rsi = rsi

  // Calculate MACD
  const macd = calculateMACD(closes, 12, 26, 9)
  if (macd !== undefined) results.macd = macd

  // Calculate EMAs
  const emas = calculateEMAs(closes, [9, 21, 50, 200])
  if (emas !== undefined) {
    results.ema = {
      ema9: emas.ema9,
      ema21: emas.ema21,
      ema50: emas.ema50,
      ema200: emas.ema200,
    }
  }

  // Calculate SMAs
  const smas = calculateSMAs(closes, [20, 50, 200])
  if (smas !== undefined) {
    results.sma = {
      sma20: smas.sma20,
      sma50: smas.sma50,
      sma200: smas.sma200,
    }
  }

  // Calculate Bollinger Bands
  const bollinger = calculateBollingerBands(closes, 20, 2)
  if (bollinger !== undefined) results.bollinger = bollinger

  // Calculate ATR
  const atr = calculateATR(klines, 14)
  if (atr !== undefined) results.atr = atr

  // Calculate ADX
  const adx = calculateADX(klines, 14)
  if (adx !== undefined) results.adx = adx

  // Calculate Stochastic
  const stochastic = calculateStochastic(klines, 14, 3)
  if (stochastic !== undefined) results.stochastic = stochastic

  // Calculate OBV
  const obv = calculateOBV(klines)
  if (obv !== undefined) results.obv = obv

  // Calculate VWAP
  const vwap = calculateVWAP(klines)
  if (vwap !== undefined) results.vwap = vwap

  return results
}

/**
 * Generate market analysis text for AI prompt
 */
export function generateMarketAnalysis(klines: KlineData[], indicators: IndicatorResults): string {
  const currentPrice = klines[klines.length - 1].close
  const previousPrice = klines[klines.length - 2]?.close ?? currentPrice
  const priceChange = ((currentPrice - previousPrice) / previousPrice) * 100

  let analysis = `## Market Analysis\n\n`
  analysis += `**Current Price:** $${currentPrice.toFixed(2)} (${priceChange >= 0 ? '+' : ''}${priceChange.toFixed(2)}%)\n\n`

  // RSI Analysis
  if (indicators.rsi !== undefined) {
    const rsiLevel =
      indicators.rsi > 70 ? 'overbought' : indicators.rsi < 30 ? 'oversold' : 'neutral'
    analysis += `**RSI(14):** ${indicators.rsi.toFixed(2)} - ${rsiLevel}\n`
  }

  // MACD Analysis
  if (indicators.macd) {
    const macdTrend = indicators.macd.histogram > 0 ? 'bullish' : 'bearish'
    analysis += `**MACD:** ${indicators.macd.macd.toFixed(2)} (Signal: ${indicators.macd.signal.toFixed(2)}) - ${macdTrend} momentum\n`
  }

  // EMA Analysis
  if (indicators.ema) {
    analysis += `**EMAs:** EMA9: ${indicators.ema.ema9.toFixed(2)}, EMA21: ${indicators.ema.ema21.toFixed(2)}, EMA50: ${indicators.ema.ema50.toFixed(2)}\n`
  }

  // Bollinger Bands
  if (indicators.bollinger) {
    const bbPosition =
      currentPrice > indicators.bollinger.upper
        ? 'above upper band'
        : currentPrice < indicators.bollinger.lower
        ? 'below lower band'
        : 'within bands'
    analysis += `**Bollinger Bands:** ${bbPosition} (Bandwidth: ${indicators.bollinger.bandwidth.toFixed(2)}%)\n`
  }

  // ADX Analysis
  if (indicators.adx) {
    const trendStrength = indicators.adx.adx > 25 ? 'strong' : 'weak'
    const trendDirection =
      indicators.adx.plusDI > indicators.adx.minusDI ? 'bullish' : 'bearish'
    analysis += `**ADX:** ${indicators.adx.adx.toFixed(2)} - ${trendStrength} ${trendDirection} trend\n`
  }

  // Stochastic
  if (indicators.stochastic) {
    const stochLevel =
      indicators.stochastic.k > 80
        ? 'overbought'
        : indicators.stochastic.k < 20
        ? 'oversold'
        : 'neutral'
    analysis += `**Stochastic:** %K: ${indicators.stochastic.k.toFixed(2)}, %D: ${indicators.stochastic.d.toFixed(2)} - ${stochLevel}\n`
  }

  // ATR
  if (indicators.atr !== undefined) {
    analysis += `**ATR(14):** ${indicators.atr.toFixed(2)} - volatility measure\n`
  }

  return analysis
}
