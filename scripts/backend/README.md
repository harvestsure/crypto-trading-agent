# CryptoAgent Backend

AI-powered cryptocurrency trading backend using Python, FastAPI, and **OpenAI Agents SDK** for tool-based autonomous trading.

## Features

- **OpenAI Agents SDK** - True AI agent with tool calling capabilities (like Vercel AI SDK's Agent)
- **Exchange Connections** - Connect to multiple exchanges (Binance, OKX, Bybit, etc.) via ccxt.pro
- **WebSocket Streaming** - Real-time kline/candlestick data streaming
- **AI Integration** - Support for OpenAI, Anthropic, DeepSeek, and custom LLM providers
- **Technical Indicators** - RSI, ADX, CHOP, KAMA, EMA, SMA, Bollinger Bands, MACD, ATR, Stochastic RSI
- **Agent Management** - Create and run multiple autonomous trading agents
- **Automated Trading** - AI-driven order execution with stop-loss and take-profit

## Installation

\`\`\`bash
cd scripts/backend
pip install -r requirements.txt
\`\`\`

## Environment Variables

\`\`\`bash
# Required for OpenAI Agents SDK
export OPENAI_API_KEY=sk-...

# Or for custom providers
export ANTHROPIC_API_KEY=...
export DEEPSEEK_API_KEY=...
\`\`\`

## Running the Server

\`\`\`bash
python main.py
\`\`\`

Server runs at `http://localhost:8000`

## Agent Tools

The AI agent has access to these trading tools (similar to Vercel AI SDK's function tools):

| Tool | Description |
|------|-------------|
| `place_market_order` | Execute market buy/sell order |
| `place_limit_order` | Place limit order at specific price |
| `set_stop_loss` | Set stop-loss order to limit losses |
| `set_take_profit` | Set take-profit order to lock gains |
| `get_current_position` | Check open position status |
| `get_open_orders` | List all pending orders |
| `cancel_order` | Cancel an open order |
| `close_position` | Close entire position at market |
| `get_account_balance` | Check account funds |
| `analyze_and_wait` | Record analysis, take no action |

## API Endpoints

### REST API

#### Health
- `GET /` - Service info and version
- `GET /health` - Detailed health status

#### AI Models
- `POST /api/models` - Register AI model
- `GET /api/models` - List all models
- `DELETE /api/models/{model_id}` - Delete AI model

#### Exchanges
- `POST /api/exchanges` - Connect exchange
- `GET /api/exchanges` - List connected exchanges
- `DELETE /api/exchanges/{exchange_id}` - Disconnect exchange

#### Agents
- `POST /api/agents` - Create trading agent
- `GET /api/agents` - List all agents
- `GET /api/agents/{agent_id}` - Get agent status
- `POST /api/agents/{agent_id}/start` - Start agent
- `POST /api/agents/{agent_id}/stop` - Stop agent
- `POST /api/agents/{agent_id}/analyze` - Trigger manual analysis
- `DELETE /api/agents/{agent_id}` - Delete agent

#### Market Data
- `GET /api/ticker/{exchange_id}/{symbol}` - Get current price
- `GET /api/klines/{exchange_id}/{symbol}/{timeframe}` - Fetch kline data
- `GET /api/indicators` - Calculate technical indicators

#### Orders
- `POST /api/orders` - Place order

### WebSocket

Connect to `ws://localhost:8000/ws/{client_id}`

## Example: Create a Trading Agent

\`\`\`python
import httpx

async def setup_agent():
    base = "http://localhost:8000"
    
    # 1. Register AI model
    await httpx.post(f"{base}/api/models", json={
        "id": "gpt4",
        "name": "GPT-4 Turbo",
        "provider": "openai",
        "api_key": "sk-...",
        "model": "gpt-4-turbo"
    })
    
    # 2. Connect exchange
    await httpx.post(f"{base}/api/exchanges", json={
        "id": "binance",
        "name": "Binance Testnet",
        "exchange": "binance",
        "api_key": "...",
        "secret_key": "...",
        "testnet": True
    })
    
    # 3. Create agent with trading rules
    await httpx.post(f"{base}/api/agents", json={
        "id": "btc-agent",
        "name": "BTC Trading Agent",
        "model_id": "gpt4",
        "exchange_id": "binance",
        "symbol": "BTC/USDT",
        "timeframe": "15m",
        "indicators": ["RSI", "ADX", "CHOP", "KAMA", "BOLLINGER"],
        "prompt": """
        You are a conservative crypto trader. Your rules:
        1. Only trade when ADX > 25 (trending market)
        2. Buy when RSI < 30 and CHOP < 40
        3. Sell when RSI > 70 or CHOP > 60
        4. Always set stop-loss at 2% below entry
        5. Set take-profit at 1.5x the risk
        """,
        "max_position_size": 500,
        "risk_per_trade": 0.02
    })
    
    # 4. Start agent
    await httpx.post(f"{base}/api/agents/btc-agent/start")
\`\`\`

## Architecture

\`\`\`
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                    │
└─────────────────────────┬───────────────────────────────┘
                          │ WebSocket / REST
┌─────────────────────────┴───────────────────────────────┐
│                  FastAPI Backend                         │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ Connection  │  │   Exchange   │  │ Indicator      │  │
│  │ Manager     │  │   Manager    │  │ Calculator     │  │
│  └─────────────┘  └──────────────┘  └────────────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │           Agent Manager (OpenAI Agents SDK)       │   │
│  │  ┌─────────────────────────────────────────────┐ │   │
│  │  │         AI Trading Agent                     │ │   │
│  │  │                                              │ │   │
│  │  │  Tools: place_market_order, set_stop_loss,  │ │   │
│  │  │         set_take_profit, close_position...  │ │   │
│  │  └─────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────┘
                          │ ccxt.pro
┌─────────────────────────┴───────────────────────────────┐
│              Exchanges (Binance, OKX, Bybit, etc.)       │
└─────────────────────────────────────────────────────────┘
\`\`\`
