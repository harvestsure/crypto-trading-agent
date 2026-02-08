# AI Trading Agent - Enhanced Features

## Overview

This crypto trading agent now includes advanced AI-powered trading decisions with comprehensive technical analysis. The system automatically subscribes to kline (candlestick) data, calculates multiple technical indicators, and uses an LLM to generate intelligent trading signals.

## Key Features

### 1. Technical Indicators Engine (`lib/indicators.ts`)

The system calculates 10+ technical indicators in real-time:

#### Momentum Indicators
- **RSI (Relative Strength Index)**: Identifies overbought/oversold conditions (>70 = overbought, <30 = oversold)
- **MACD (Moving Average Convergence Divergence)**: Shows momentum and trend changes
- **Stochastic Oscillator**: Momentum indicator comparing closing price to price range

#### Trend Indicators
- **EMA (Exponential Moving Average)**: Multiple periods (9, 21, 50, 200) for trend identification
- **SMA (Simple Moving Average)**: Standard moving averages (20, 50, 200)
- **ADX (Average Directional Index)**: Measures trend strength (>25 = strong trend)

#### Volatility Indicators
- **Bollinger Bands**: Shows price volatility and potential reversal points
- **ATR (Average True Range)**: Measures market volatility

#### Volume Indicators
- **OBV (On-Balance Volume)**: Volume-based momentum indicator
- **VWAP (Volume Weighted Average Price)**: Average price weighted by volume

### 2. AI-Powered Trading Decisions (`/api/trading/analyze`)

The AI trading engine uses Vercel AI SDK with GPT-4o-mini to analyze market conditions:

**Input:**
- Real-time kline data (last 100+ candles)
- All calculated technical indicators
- Custom trading strategy prompt
- Risk tolerance level (low/medium/high)

**Output:**
```typescript
{
  action: "LONG" | "SHORT" | "CLOSE_LONG" | "CLOSE_SHORT" | "HOLD",
  confidence: 0.0 - 1.0,
  reasoning: "Detailed explanation",
  stopLoss: number,
  takeProfit: number,
  positionSize: 1-100 (percentage)
}
```

### 3. Real-time Data Management

#### Kline Data Hook (`hooks/use-kline-data.ts`)
- Subscribes to WebSocket for real-time price updates
- Maintains 100+ historical candles
- Simulates live data when backend unavailable
- Auto-updates every 2 seconds

#### AI Trading Hook (`hooks/use-ai-trading.ts`)
- Manages AI analysis state
- Calculates indicators client-side
- Tracks analysis history (last 50 analyses)
- Provides signal strength ratings

### 4. Enhanced UI Components

#### AI Decision Panel (`components/agents/ai-decision-panel.tsx`)
Displays:
- Recommended trading action (LONG/SHORT/CLOSE/HOLD)
- Confidence level with visual progress bar
- Position size recommendation
- Stop loss and take profit levels
- Detailed reasoning from AI

#### Live Indicator Panel (`components/agents/live-indicator-panel.tsx`)
Shows real-time indicators:
- RSI with overbought/oversold zones
- MACD with signal line and histogram
- Multiple EMAs (9, 21, 50, 200)
- Bollinger Bands with bandwidth
- ADX with +DI/-DI components
- Stochastic oscillator
- ATR, OBV, and VWAP

#### Action History (`components/agents/action-history.tsx`)
Comprehensive trading action log:
- All AI-generated trading decisions
- Execution status (pending/executed/failed)
- P&L tracking for completed trades
- Confidence levels and reasoning
- Stop loss and take profit levels
- Time-sorted with relative timestamps

### 5. Integration Flow

```
1. Agent starts → Subscribe to kline data (WebSocket)
                ↓
2. Receive real-time candles → Store last 100+ candles
                ↓
3. Calculate technical indicators → RSI, MACD, EMA, etc.
                ↓
4. User clicks "AI Analyze" → Send data to AI endpoint
                ↓
5. AI analyzes market conditions → Generate trading decision
                ↓
6. Display decision in UI → Show in AI Decision Panel
                ↓
7. Log action in history → Track all trading signals
                ↓
8. (Optional) Execute trade → Update P&L
```

## Usage

### On Agent Detail Page

1. **View Real-time Indicators**: The Live Indicator Panel automatically updates as new kline data arrives
2. **Trigger AI Analysis**: Click the "AI Analyze" button to get an AI-powered trading recommendation
3. **Review Decision**: Check the AI Decision Panel for the recommended action, confidence, and reasoning
4. **View Action History**: Switch to the "AI Actions" tab to see all past trading decisions and their outcomes

### API Endpoints

#### POST `/api/trading/analyze`
Analyzes market data and returns trading decision.

**Request Body:**
```json
{
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "klines": [...], // Array of kline data
  "customPrompt": "Optional custom strategy",
  "riskTolerance": "medium"
}
```

**Response:**
```json
{
  "success": true,
  "decision": {
    "action": "LONG",
    "confidence": 0.85,
    "reasoning": "Strong bullish momentum...",
    "stopLoss": 42500,
    "takeProfit": 44000,
    "positionSize": 10
  },
  "indicators": { ... },
  "timestamp": 1234567890
}
```

## Configuration

### Risk Tolerance Levels

- **Low**: 5% position size, conservative signals only
- **Medium**: 10% position size, balanced approach (default)
- **High**: 20% position size, more aggressive signals

### Indicator Settings

All indicators use standard periods:
- RSI: 14 periods
- MACD: 12/26/9
- EMAs: 9, 21, 50, 200
- Bollinger Bands: 20 periods, 2 std dev
- ADX: 14 periods
- Stochastic: 14/3

### AI Model Configuration

The system uses Vercel AI Gateway with zero-config providers:
- Default: OpenAI GPT-4o-mini
- Temperature: 0.3 (for consistent decisions)
- Max tokens: 500

## Best Practices

1. **Wait for Sufficient Data**: AI analysis requires at least 50 candles (preferably 100+)
2. **Monitor Confidence Levels**: Only act on signals with >60% confidence
3. **Use Multiple Timeframes**: Analyze on different timeframes for better context
4. **Set Stop Losses**: Always use the recommended stop loss levels
5. **Track Action History**: Review past decisions to improve strategies
6. **Adjust Risk Tolerance**: Match your risk tolerance with market conditions

## Technical Architecture

### Frontend Stack
- **React 19.2** with Next.js 16
- **Vercel AI SDK 6.0** for LLM integration
- **SWR** for data fetching and caching
- **WebSocket** for real-time updates
- **Zustand** for state management

### Backend Requirements
- Python trading backend (FastAPI recommended)
- WebSocket server for kline streaming
- Exchange API integration (Binance, OKX, etc.)
- Redis for caching (optional)

### Data Flow
- Client subscribes to WebSocket
- Backend streams kline updates
- Frontend calculates indicators
- AI analysis triggered on demand
- Results stored in local state

## Future Enhancements

1. **Automated Trading**: Execute trades based on AI decisions
2. **Backtesting**: Test strategies on historical data
3. **Portfolio Management**: Multi-symbol trading
4. **Risk Management**: Position sizing algorithms
5. **Performance Analytics**: Win rate, Sharpe ratio, drawdown tracking
6. **Strategy Templates**: Pre-configured trading strategies
7. **Alert System**: Push notifications for signals
8. **Machine Learning**: Train models on historical performance

## Troubleshooting

### AI Analysis Not Working
- Ensure at least 50 kline candles are loaded
- Check that Vercel AI Gateway is configured
- Verify network connectivity

### Indicators Not Updating
- Check WebSocket connection status
- Verify exchange API is responding
- Look for errors in browser console

### Action History Empty
- Click "AI Analyze" to generate decisions
- Check that analysis completes successfully
- Verify state is being updated

## Support

For issues or questions, check:
- Browser console for errors
- Network tab for API failures
- WebSocket connection status in UI
