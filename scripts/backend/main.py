"""
CryptoAgent Backend - Main Entry Point
Python + ccxt.pro for exchange WebSocket connections and REST API

Requirements:
- pip install -r requirements.txt
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============== Pydantic Models ==============

class AIModelConfig(BaseModel):
    id: str
    name: str
    provider: str  # openai, anthropic, deepseek, custom
    api_key: str
    base_url: Optional[str] = None
    model: str


class ExchangeConfig(BaseModel):
    id: str
    name: str
    exchange: str  # binance, okx, bybit, bitget, gate
    api_key: str
    secret_key: str
    passphrase: Optional[str] = None
    testnet: bool = True


class AgentConfig(BaseModel):
    id: str
    name: str
    model_id: str
    exchange_id: str
    symbol: str
    timeframe: str
    indicators: List[str]
    prompt: str
    max_position_size: float = 1000.0  # USD
    risk_per_trade: float = 0.02  # 2%
    default_leverage: int = 1


class TradingSignal(BaseModel):
    action: str  # buy, sell, hold
    reason: str
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None


class OrderRequest(BaseModel):
    agent_id: str
    symbol: str
    side: str  # buy, sell
    order_type: str  # market, limit
    amount: float
    price: Optional[float] = None


# ============== Manager Classes ==============

class ConnectionManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"Client {client_id} connected")
    
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"Client {client_id} disconnected")
    
    async def broadcast(self, message: dict):
        disconnected = []
        for client_id, connection in self.active_connections.items():
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to {client_id}: {e}")
                disconnected.append(client_id)
        for client_id in disconnected:
            self.disconnect(client_id)
    
    async def send_to_client(self, client_id: str, message: dict):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)


class ExchangeManager:
    """Manages exchange connections using ccxt.pro"""
    
    def __init__(self):
        self.exchanges: Dict[str, Any] = {}
        self.kline_tasks: Dict[str, asyncio.Task] = {}
    
    async def connect_exchange(self, config: ExchangeConfig) -> bool:
        """Connect to an exchange"""
        try:
            import ccxt.pro as ccxtpro
            
            exchange_class = getattr(ccxtpro, config.exchange, None)
            if not exchange_class:
                logger.error(f"Exchange {config.exchange} not supported")
                return False
            
            exchange_config = {
                'apiKey': config.api_key,
                'secret': config.secret_key,
                'enableRateLimit': True,
            }
            
            if config.passphrase:
                exchange_config['password'] = config.passphrase
            
            if config.testnet:
                exchange_config['sandbox'] = True
            
            exchange = exchange_class(exchange_config)
            self.exchanges[config.id] = exchange
            
            await exchange.load_markets()
            logger.info(f"Connected to {config.exchange}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to {config.exchange}: {e}")
            return False
    
    async def disconnect_exchange(self, exchange_id: str):
        """Disconnect from an exchange"""
        if exchange_id in self.exchanges:
            await self.exchanges[exchange_id].close()
            del self.exchanges[exchange_id]
    
    async def get_ticker(self, exchange_id: str, symbol: str) -> dict:
        """Get current ticker/price info"""
        if exchange_id not in self.exchanges:
            return {}
        try:
            ticker = await self.exchanges[exchange_id].fetch_ticker(symbol)
            return {
                'last': ticker.get('last', 0),
                'bid': ticker.get('bid', 0),
                'ask': ticker.get('ask', 0),
                'volume': ticker.get('baseVolume', 0),
                'change': ticker.get('percentage', 0)
            }
        except Exception as e:
            logger.error(f"Failed to get ticker: {e}")
            return {}
    
    async def get_balance(self, exchange_id: str) -> dict:
        """Get account balance"""
        if exchange_id not in self.exchanges:
            return {}
        try:
            balance = await self.exchanges[exchange_id].fetch_balance()
            usdt = balance.get('USDT', {})
            return {
                'total': usdt.get('total', 0),
                'free': usdt.get('free', 0),
                'used': usdt.get('used', 0)
            }
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return {}
    
    async def place_stop_order(
        self,
        exchange_id: str,
        symbol: str,
        side: str,
        amount: float,
        stop_price: float
    ) -> dict:
        """Place a stop order"""
        if exchange_id not in self.exchanges:
            raise HTTPException(status_code=404, detail="Exchange not found")
        
        exchange = self.exchanges[exchange_id]
        try:
            order = await exchange.create_order(
                symbol, 'stop', side, amount, stop_price,
                params={'stopPrice': stop_price}
            )
            return order
        except Exception as e:
            logger.error(f"Stop order error: {e}")
            # Fallback: some exchanges use different methods
            try:
                order = await exchange.create_order(
                    symbol, 'stop_market', side, amount, None,
                    params={'stopPrice': stop_price}
                )
                return order
            except:
                raise HTTPException(status_code=500, detail=str(e))
    
    async def cancel_order(self, exchange_id: str, order_id: str, symbol: str) -> dict:
        """Cancel an order"""
        if exchange_id not in self.exchanges:
            raise HTTPException(status_code=404, detail="Exchange not found")
        
        exchange = self.exchanges[exchange_id]
        try:
            result = await exchange.cancel_order(order_id, symbol)
            return result
        except Exception as e:
            logger.error(f"Cancel order error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def fetch_ohlcv(
        self,
        exchange_id: str,
        symbol: str,
        timeframe: str,
        limit: int = 100
    ) -> List[dict]:
        """Fetch historical OHLCV data"""
        if exchange_id not in self.exchanges:
            return []
        
        try:
            exchange = self.exchanges[exchange_id]
            ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return [
                {
                    'timestamp': k[0],
                    'open': k[1],
                    'high': k[2],
                    'low': k[3],
                    'close': k[4],
                    'volume': k[5]
                } for k in ohlcv
            ]
        except Exception as e:
            logger.error(f"Failed to fetch OHLCV: {e}")
            return []
    
    async def place_order(
        self,
        exchange_id: str,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: Optional[float] = None
    ) -> dict:
        """Place an order on the exchange"""
        if exchange_id not in self.exchanges:
            raise HTTPException(status_code=404, detail="Exchange not found")
        
        exchange = self.exchanges[exchange_id]
        
        try:
            if order_type == 'market':
                order = await exchange.create_market_order(symbol, side, amount)
            else:
                if price is None:
                    raise HTTPException(status_code=400, detail="Price required for limit orders")
                order = await exchange.create_limit_order(symbol, side, amount, price)
            
            return order
        except Exception as e:
            logger.error(f"Order error: {e}")
            raise HTTPException(status_code=500, detail=str(e))


class IndicatorCalculator:
    """Calculate technical indicators"""
    
    @staticmethod
    def calculate_rsi(closes: List[float], period: int = 14) -> float:
        if len(closes) < period + 1:
            return 50.0
        
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def calculate_adx(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """Average Directional Index"""
        if len(closes) < period * 2:
            return 25.0
        
        tr_list = []
        plus_dm_list = []
        minus_dm_list = []
        
        for i in range(1, len(closes)):
            high_diff = highs[i] - highs[i-1]
            low_diff = lows[i-1] - lows[i]
            
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            tr_list.append(tr)
            
            plus_dm = high_diff if high_diff > low_diff and high_diff > 0 else 0
            minus_dm = low_diff if low_diff > high_diff and low_diff > 0 else 0
            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)
        
        atr = sum(tr_list[-period:]) / period
        plus_di = 100 * (sum(plus_dm_list[-period:]) / period) / atr if atr > 0 else 0
        minus_di = 100 * (sum(minus_dm_list[-period:]) / period) / atr if atr > 0 else 0
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) > 0 else 0
        return dx
    
    @staticmethod
    def calculate_chop(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """Choppiness Index"""
        import math
        
        if len(closes) < period + 1:
            return 50.0
        
        tr_sum = 0
        for i in range(1, period + 1):
            idx = -period - 1 + i
            tr = max(
                highs[idx] - lows[idx],
                abs(highs[idx] - closes[idx-1]),
                abs(lows[idx] - closes[idx-1])
            )
            tr_sum += tr
        
        highest_high = max(highs[-period:])
        lowest_low = min(lows[-period:])
        
        if highest_high - lowest_low == 0:
            return 50.0
        
        chop = 100 * math.log10(tr_sum / (highest_high - lowest_low)) / math.log10(period)
        return max(0, min(100, chop))
    
    @staticmethod
    def calculate_kama(closes: List[float], period: int = 10, fast: int = 2, slow: int = 30) -> float:
        """Kaufman Adaptive Moving Average"""
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
    def calculate_ema(closes: List[float], period: int = 20) -> float:
        """Exponential Moving Average"""
        if not closes:
            return 0
        multiplier = 2 / (period + 1)
        ema = closes[0]
        for price in closes[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        return ema
    
    @staticmethod
    def calculate_bollinger(closes: List[float], period: int = 20, std_dev: float = 2) -> dict:
        """Bollinger Bands"""
        if len(closes) < period:
            return {'upper': 0, 'middle': 0, 'lower': 0}
        
        sma = sum(closes[-period:]) / period
        variance = sum((x - sma) ** 2 for x in closes[-period:]) / period
        std = variance ** 0.5
        
        return {
            'upper': sma + std_dev * std,
            'middle': sma,
            'lower': sma - std_dev * std
        }
    
    @staticmethod
    def calculate_macd(closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
        """MACD Indicator"""
        if len(closes) < slow:
            return {'macd': 0, 'signal': 0, 'histogram': 0}
        
        def ema(data, period):
            multiplier = 2 / (period + 1)
            result = data[0]
            for price in data[1:]:
                result = (price * multiplier) + (result * (1 - multiplier))
            return result
        
        fast_ema = ema(closes, fast)
        slow_ema = ema(closes, slow)
        macd_line = fast_ema - slow_ema
        signal_line = macd_line * 0.9
        
        return {
            'macd': round(macd_line, 2),
            'signal': round(signal_line, 2),
            'histogram': round(macd_line - signal_line, 2)
        }
    
    @staticmethod
    def calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """Average True Range"""
        if len(closes) < period + 1:
            return 0
        
        tr_list = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            tr_list.append(tr)
        
        return sum(tr_list[-period:]) / period
    
    @staticmethod
    def calculate_stoch_rsi(closes: List[float], period: int = 14) -> dict:
        """Stochastic RSI"""
        if len(closes) < period * 2:
            return {'k': 50, 'd': 50}
        
        # Calculate RSI values
        rsi_values = []
        for i in range(period, len(closes)):
            subset = closes[i-period:i+1]
            rsi = IndicatorCalculator.calculate_rsi(subset, period)
            rsi_values.append(rsi)
        
        if len(rsi_values) < period:
            return {'k': 50, 'd': 50}
        
        recent_rsi = rsi_values[-period:]
        lowest_rsi = min(recent_rsi)
        highest_rsi = max(recent_rsi)
        
        if highest_rsi - lowest_rsi == 0:
            stoch_k = 50
        else:
            stoch_k = ((rsi_values[-1] - lowest_rsi) / (highest_rsi - lowest_rsi)) * 100
        
        stoch_d = sum(rsi_values[-3:]) / 3 if len(rsi_values) >= 3 else stoch_k
        
        return {'k': round(stoch_k, 2), 'd': round(stoch_d, 2)}
    
    @classmethod
    def calculate_all(cls, kline_data: List[dict], indicators: List[str]) -> dict:
        """Calculate all requested indicators"""
        if not kline_data:
            return {}
        
        closes = [k['close'] for k in kline_data]
        highs = [k['high'] for k in kline_data]
        lows = [k['low'] for k in kline_data]
        
        result = {}
        
        if 'RSI' in indicators:
            result['rsi'] = round(cls.calculate_rsi(closes), 2)
        
        if 'ADX' in indicators:
            result['adx'] = round(cls.calculate_adx(highs, lows, closes), 2)
        
        if 'CHOP' in indicators:
            result['chop'] = round(cls.calculate_chop(highs, lows, closes), 2)
        
        if 'KAMA' in indicators:
            result['kama'] = round(cls.calculate_kama(closes), 2)
        
        if 'EMA' in indicators:
            result['ema_20'] = round(cls.calculate_ema(closes, 20), 2)
            result['ema_50'] = round(cls.calculate_ema(closes, 50), 2)
        
        if 'SMA' in indicators:
            result['sma_20'] = round(sum(closes[-20:]) / min(20, len(closes)), 2)
            result['sma_50'] = round(sum(closes[-50:]) / min(50, len(closes)), 2)
        
        if 'BOLLINGER' in indicators:
            bb = cls.calculate_bollinger(closes)
            result['bb_upper'] = round(bb['upper'], 2)
            result['bb_middle'] = round(bb['middle'], 2)
            result['bb_lower'] = round(bb['lower'], 2)
        
        if 'MACD' in indicators:
            macd = cls.calculate_macd(closes)
            result['macd'] = macd['macd']
            result['macd_signal'] = macd['signal']
            result['macd_histogram'] = macd['histogram']
        
        if 'ATR' in indicators:
            result['atr'] = round(cls.calculate_atr(highs, lows, closes), 4)
        
        if 'STOCH_RSI' in indicators:
            stoch = cls.calculate_stoch_rsi(closes)
            result['stoch_k'] = stoch['k']
            result['stoch_d'] = stoch['d']
        
        # Always include current price info
        result['current_price'] = closes[-1] if closes else 0
        result['price_change_1h'] = round(((closes[-1] / closes[-4]) - 1) * 100, 2) if len(closes) >= 4 else 0
        result['price_change_24h'] = round(((closes[-1] / closes[-24]) - 1) * 100, 2) if len(closes) >= 24 else 0
        
        return result


# ============== FastAPI App ==============

connection_manager = ConnectionManager()
exchange_manager = ExchangeManager()

agent_manager = None
ai_models: Dict[str, AIModelConfig] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent_manager
    logger.info("Starting CryptoAgent Backend...")
    
    try:
        from trading_agent import AgentManager
        agent_manager = AgentManager(exchange_manager, connection_manager)
        logger.info("AgentManager initialized with OpenAI Agents SDK")
    except ImportError as e:
        logger.warning(f"Could not import AgentManager: {e}")
        logger.info("Running in basic mode without OpenAI Agents SDK")
    
    yield
    
    logger.info("Shutting down...")
    for exchange_id in list(exchange_manager.exchanges.keys()):
        await exchange_manager.disconnect_exchange(exchange_id)

app = FastAPI(
    title="CryptoAgent Backend",
    description="AI-powered cryptocurrency trading backend with OpenAI Agents SDK",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== REST API Endpoints ==============

@app.get("/")
async def root():
    return {
        "status": "running",
        "service": "CryptoAgent Backend",
        "version": "2.0.0",
        "features": ["OpenAI Agents SDK", "Tool-based Trading", "Multi-Exchange Support"]
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "exchanges_connected": len(exchange_manager.exchanges),
        "models_registered": len(ai_models),
        "agents_running": len([a for a in agent_manager.agents.values() if a.is_running]) if agent_manager else 0,
        "websocket_clients": len(connection_manager.active_connections)
    }


# AI Models
@app.post("/api/models")
async def register_model(config: AIModelConfig):
    ai_models[config.id] = config
    return {"status": "success", "model_id": config.id}


@app.get("/api/models")
async def list_models():
    return {
        "models": [
            {"id": m.id, "name": m.name, "provider": m.provider, "model": m.model}
            for m in ai_models.values()
        ]
    }


@app.delete("/api/models/{model_id}")
async def delete_model(model_id: str):
    if model_id in ai_models:
        del ai_models[model_id]
    return {"status": "success"}


# Exchanges
@app.post("/api/exchanges")
async def connect_exchange(config: ExchangeConfig):
    success = await exchange_manager.connect_exchange(config)
    return {"status": "success" if success else "failed", "exchange_id": config.id}


@app.get("/api/exchanges")
async def list_exchanges():
    return {"exchanges": list(exchange_manager.exchanges.keys())}


@app.delete("/api/exchanges/{exchange_id}")
async def disconnect_exchange(exchange_id: str):
    await exchange_manager.disconnect_exchange(exchange_id)
    return {"status": "success"}


@app.post("/api/agents")
async def create_agent(config: AgentConfig):
    if not agent_manager:
        raise HTTPException(status_code=503, detail="AgentManager not available")
    
    if config.model_id not in ai_models:
        raise HTTPException(status_code=404, detail="Model not found")
    
    if config.exchange_id not in exchange_manager.exchanges:
        raise HTTPException(status_code=404, detail="Exchange not connected")
    
    try:
        from trading_agent import TradingContext
        
        trading_context = TradingContext(
            exchange_id=config.exchange_id,
            symbol=config.symbol,
            timeframe=config.timeframe,
            max_position_size=config.max_position_size,
            risk_per_trade=config.risk_per_trade,
            default_leverage=config.default_leverage
        )
        
        model_config = ai_models[config.model_id]
        
        agent_manager.create_agent(
            agent_id=config.id,
            model_config={
                'model': model_config.model,
                'api_key': model_config.api_key,
                'provider': model_config.provider
            },
            trading_context=trading_context,
            system_prompt=config.prompt
        )
        
        return {"status": "success", "agent_id": config.id}
        
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents")
async def list_agents():
    if not agent_manager:
        return {"agents": []}
    return {"agents": agent_manager.get_all_status()}


@app.post("/api/agents/{agent_id}/start")
async def start_agent(agent_id: str, interval: int = 60):
    if not agent_manager:
        raise HTTPException(status_code=503, detail="AgentManager not available")
    
    # Calculate interval based on timeframe if agent exists
    agent = agent_manager.get_agent(agent_id)
    if agent:
        timeframe = agent.trading_context.timeframe
        intervals = {'1m': 60, '5m': 300, '15m': 900, '30m': 1800, '1h': 3600, '4h': 14400, '1d': 86400}
        interval = intervals.get(timeframe, interval)
    
    success = await agent_manager.start_agent(agent_id, interval)
    return {"status": "success" if success else "failed"}


@app.post("/api/agents/{agent_id}/stop")
async def stop_agent(agent_id: str):
    if not agent_manager:
        raise HTTPException(status_code=503, detail="AgentManager not available")
    
    agent_manager.stop_agent(agent_id)
    return {"status": "success"}


@app.get("/api/agents/{agent_id}")
async def get_agent_status(agent_id: str):
    if not agent_manager:
        raise HTTPException(status_code=503, detail="AgentManager not available")
    
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return {
        "agent_id": agent_id,
        "is_running": agent.is_running,
        "symbol": agent.trading_context.symbol,
        "timeframe": agent.trading_context.timeframe,
        "max_position_size": agent.trading_context.max_position_size,
        "last_analysis": agent.last_analysis
    }


@app.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: str):
    if agent_manager:
        agent_manager.remove_agent(agent_id)
    return {"status": "success"}


@app.post("/api/agents/{agent_id}/analyze")
async def trigger_analysis(agent_id: str):
    """Manually trigger an analysis cycle for testing"""
    if not agent_manager:
        raise HTTPException(status_code=503, detail="AgentManager not available")
    
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    try:
        # Fetch market data
        klines = await exchange_manager.fetch_ohlcv(
            agent.trading_context.exchange_id,
            agent.trading_context.symbol,
            agent.trading_context.timeframe,
            100
        )
        
        # Calculate indicators
        indicators = IndicatorCalculator.calculate_all(
            klines,
            ['RSI', 'ADX', 'CHOP', 'KAMA', 'BOLLINGER', 'MACD', 'ATR', 'EMA', 'STOCH_RSI']
        )
        
        # Run analysis
        result = await agent.analyze({
            'klines': klines,
            'indicators': indicators
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Manual analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Orders
@app.post("/api/orders")
async def place_order(order: OrderRequest):
    result = await exchange_manager.place_order(
        order.agent_id,
        order.symbol,
        order.side,
        order.order_type,
        order.amount,
        order.price
    )
    return result


# Market Data
@app.get("/api/ticker/{exchange_id}/{symbol}")
async def get_ticker(exchange_id: str, symbol: str):
    ticker = await exchange_manager.get_ticker(exchange_id, symbol)
    return {"ticker": ticker}


@app.get("/api/klines/{exchange_id}/{symbol}/{timeframe}")
async def get_klines(exchange_id: str, symbol: str, timeframe: str, limit: int = 100):
    klines = await exchange_manager.fetch_ohlcv(exchange_id, symbol, timeframe, limit)
    return {"klines": klines}


@app.get("/api/indicators")
async def calculate_indicators(
    exchange_id: str,
    symbol: str,
    timeframe: str,
    indicators: str = "RSI,ADX,CHOP,KAMA,BOLLINGER,MACD,ATR"
):
    klines = await exchange_manager.fetch_ohlcv(exchange_id, symbol, timeframe, 100)
    indicator_list = [i.strip().upper() for i in indicators.split(',')]
    result = IndicatorCalculator.calculate_all(klines, indicator_list)
    return {"indicators": result}


# Agent Details
@app.get("/api/agents/{agent_id}/positions")
async def get_agent_positions(agent_id: str):
    """Get open positions for an agent"""
    if not agent_manager:
        raise HTTPException(status_code=503, detail="AgentManager not available")
    
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    exchange_id = agent.trading_context.exchange_id
    if exchange_id not in exchange_manager.exchanges:
        return {"positions": []}
    
    try:
        exchange = exchange_manager.exchanges[exchange_id]
        positions = await exchange.fetch_positions()
        
        result = []
        for pos in positions:
            if float(pos.get('contracts', 0)) > 0:
                entry_price = float(pos.get('entryPrice', 0))
                current_price = float(pos.get('markPrice', entry_price))
                size = float(pos.get('contracts', 0))
                side = pos.get('side', 'long')
                leverage = int(pos.get('leverage', 1))
                
                # Calculate PnL
                if side == 'long':
                    unrealized_pnl = (current_price - entry_price) * size
                    pnl_percent = ((current_price - entry_price) / entry_price) * 100 * leverage
                else:
                    unrealized_pnl = (entry_price - current_price) * size
                    pnl_percent = ((entry_price - current_price) / entry_price) * 100 * leverage
                
                result.append({
                    "symbol": pos.get('symbol', ''),
                    "side": side,
                    "size": size,
                    "entryPrice": entry_price,
                    "currentPrice": current_price,
                    "leverage": leverage,
                    "unrealizedPnl": unrealized_pnl,
                    "unrealizedPnlPercent": pnl_percent,
                    "liquidationPrice": float(pos.get('liquidationPrice', 0)),
                    "margin": float(pos.get('initialMargin', 0)),
                    "timestamp": pos.get('timestamp', datetime.now().isoformat())
                })
        
        return {"positions": result}
        
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        return {"positions": [], "error": str(e)}


@app.get("/api/agents/{agent_id}/balance")
async def get_agent_balance(agent_id: str):
    """Get account balance for an agent's exchange"""
    if not agent_manager:
        raise HTTPException(status_code=503, detail="AgentManager not available")
    
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    exchange_id = agent.trading_context.exchange_id
    balance = await exchange_manager.get_balance(exchange_id)
    
    # Get positions for margin calculation
    positions_data = await get_agent_positions(agent_id)
    positions = positions_data.get("positions", [])
    
    total_margin = sum(p.get("margin", 0) for p in positions)
    total_unrealized_pnl = sum(p.get("unrealizedPnl", 0) for p in positions)
    
    return {
        "totalBalance": balance.get('total', 0),
        "availableBalance": balance.get('free', 0),
        "usedMargin": total_margin,
        "unrealizedPnl": total_unrealized_pnl,
        "realizedPnl": 0,  # Would need trade history to calculate
        "todayPnl": 0,
        "weekPnl": 0,
        "monthPnl": 0
    }


@app.get("/api/agents/{agent_id}/conversations")
async def get_agent_conversations(agent_id: str, limit: int = 50):
    """Get conversation history for an agent"""
    if not agent_manager:
        raise HTTPException(status_code=503, detail="AgentManager not available")
    
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Return stored conversation history
    conversations = getattr(agent, 'conversation_history', [])
    return {"conversations": conversations[-limit:]}


@app.get("/api/agents/{agent_id}/tool-calls")
async def get_agent_tool_calls(agent_id: str, limit: int = 50):
    """Get tool call history for an agent"""
    if not agent_manager:
        raise HTTPException(status_code=503, detail="AgentManager not available")
    
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Return stored tool call history
    tool_calls = getattr(agent, 'tool_call_history', [])
    return {"toolCalls": tool_calls[-limit:]}


@app.get("/api/agents/{agent_id}/orders")
async def get_agent_orders(agent_id: str, limit: int = 50):
    """Get order history for an agent"""
    if not agent_manager:
        raise HTTPException(status_code=503, detail="AgentManager not available")
    
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    exchange_id = agent.trading_context.exchange_id
    symbol = agent.trading_context.symbol
    
    if exchange_id not in exchange_manager.exchanges:
        return {"orders": []}
    
    try:
        exchange = exchange_manager.exchanges[exchange_id]
        
        # Get open orders
        open_orders = await exchange.fetch_open_orders(symbol)
        
        # Get closed orders (last 50)
        closed_orders = await exchange.fetch_closed_orders(symbol, limit=limit)
        
        all_orders = []
        for order in open_orders + closed_orders:
            all_orders.append({
                "id": order.get('id', ''),
                "symbol": order.get('symbol', ''),
                "side": order.get('side', ''),
                "type": order.get('type', ''),
                "amount": float(order.get('amount', 0)),
                "price": float(order.get('price', 0)) if order.get('price') else None,
                "filled": float(order.get('filled', 0)),
                "status": order.get('status', ''),
                "timestamp": order.get('timestamp', 0)
            })
        
        # Sort by timestamp descending
        all_orders.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        
        return {"orders": all_orders[:limit]}
        
    except Exception as e:
        logger.error(f"Failed to get orders: {e}")
        return {"orders": [], "error": str(e)}


@app.get("/api/agents/{agent_id}/profit-history")
async def get_agent_profit_history(agent_id: str, days: int = 30):
    """Get profit history for chart display"""
    if not agent_manager:
        raise HTTPException(status_code=503, detail="AgentManager not available")
    
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Return stored profit history or empty
    profit_history = getattr(agent, 'profit_history', [])
    return {"profitHistory": profit_history[-days:]}


@app.get("/api/agents/{agent_id}/signals")
async def get_agent_signals(agent_id: str, limit: int = 50):
    """Get signal history for an agent"""
    if not agent_manager:
        raise HTTPException(status_code=503, detail="AgentManager not available")
    
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Return stored signals
    signals = getattr(agent, 'signal_history', [])
    return {"signals": signals[-limit:]}


@app.get("/api/agents/{agent_id}/logs")
async def get_agent_logs(agent_id: str, limit: int = 100):
    """Get log entries for an agent"""
    if not agent_manager:
        raise HTTPException(status_code=503, detail="AgentManager not available")
    
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Return stored logs
    logs = getattr(agent, 'logs', [])
    return {"logs": logs[-limit:]}


# ============== WebSocket Endpoint ==============

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await connection_manager.connect(websocket, client_id)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            if data['type'] == 'subscribe_kline':
                # Start streaming kline data
                exchange_id = data['exchange_id']
                symbol = data['symbol']
                timeframe = data['timeframe']
                
                async def send_klines():
                    while client_id in connection_manager.active_connections:
                        klines = await exchange_manager.fetch_ohlcv(
                            exchange_id, symbol, timeframe, 100
                        )
                        indicators = IndicatorCalculator.calculate_all(
                            klines, ['RSI', 'ADX', 'CHOP', 'KAMA', 'EMA', 'BOLLINGER', 'MACD']
                        )
                        await connection_manager.send_to_client(client_id, {
                            'type': 'kline_update',
                            'symbol': symbol,
                            'timeframe': timeframe,
                            'klines': klines[-50:],
                            'indicators': indicators
                        })
                        await asyncio.sleep(10)  # Update every 10 seconds
                
                asyncio.create_task(send_klines())
                await websocket.send_json({
                    'type': 'subscribed',
                    'symbol': symbol,
                    'timeframe': timeframe
                })
            
            elif data['type'] == 'ping':
                await websocket.send_json({'type': 'pong'})
    
    except WebSocketDisconnect:
        connection_manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        connection_manager.disconnect(client_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
