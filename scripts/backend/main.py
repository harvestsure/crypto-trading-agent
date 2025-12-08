"""
CryptoAgent Backend - Main Entry Point
Python + ccxt.pro for exchange WebSocket connections and REST API

Requirements:
- pip install -r requirements.txt
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import (
    init_database,
    AIModelRepository,
    ExchangeRepository,
    AgentRepository,
    OrderRepository,
    PositionRepository,
    ConversationRepository,
    ToolCallRepository,
    SignalRepository,
    BalanceHistoryRepository,
    ActivityLogRepository
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============== Pydantic Models ==============

class AIModelConfig(BaseModel):
    id: Optional[str] = None
    name: str
    provider: str
    api_key: str
    base_url: Optional[str] = None
    model: str


class ExchangeConfig(BaseModel):
    id: Optional[str] = None
    name: str
    exchange: str
    api_key: str
    secret_key: str
    passphrase: Optional[str] = None
    testnet: bool = True


class AgentConfig(BaseModel):
    id: Optional[str] = None
    name: str
    model_id: str
    exchange_id: str
    symbol: str
    timeframe: str
    indicators: List[str]
    prompt: str
    max_position_size: float = 1000.0
    risk_per_trade: float = 0.02
    default_leverage: int = 1


class OrderRequest(BaseModel):
    agent_id: str
    symbol: str
    side: str
    order_type: str
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
    
    async def connect_exchange(self, config: dict) -> bool:
        """Connect to an exchange"""
        try:
            import ccxt.pro as ccxtpro
            
            exchange_name = config['exchange']
            exchange_class = getattr(ccxtpro, exchange_name, None)
            if not exchange_class:
                logger.error(f"Exchange {exchange_name} not supported")
                return False
            
            exchange_config = {
                'apiKey': config['api_key'],
                'secret': config['secret_key'],
                'enableRateLimit': True,
            }
            
            if config.get('passphrase'):
                exchange_config['password'] = config['passphrase']
            
            if config.get('testnet'):
                exchange_config['sandbox'] = True
            
            exchange = exchange_class(exchange_config)
            self.exchanges[config['id']] = exchange
            
            await exchange.load_markets()
            
            # Update exchange status in database
            ExchangeRepository.update(config['id'], {'status': 'connected'})
            ActivityLogRepository.log('info', f"Connected to {exchange_name}", details={'exchange_id': config['id']})
            
            logger.info(f"Connected to {exchange_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to exchange: {e}")
            ExchangeRepository.update(config['id'], {'status': 'error'})
            ActivityLogRepository.log('error', f"Failed to connect to exchange: {e}", details={'exchange_id': config['id']})
            return False
    
    async def disconnect_exchange(self, exchange_id: str):
        """Disconnect from an exchange"""
        if exchange_id in self.exchanges:
            try:
                await self.exchanges[exchange_id].close()
            except:
                pass
            del self.exchanges[exchange_id]
            ExchangeRepository.update(exchange_id, {'status': 'disconnected'})
            logger.info(f"Disconnected from exchange {exchange_id}")
    
    async def get_ticker(self, exchange_id: str, symbol: str) -> Optional[dict]:
        """Get current ticker data"""
        if exchange_id not in self.exchanges:
            return None
        try:
            ticker = await self.exchanges[exchange_id].fetch_ticker(symbol)
            return ticker
        except Exception as e:
            logger.error(f"Error fetching ticker: {e}")
            return None
    
    async def get_balance(self, exchange_id: str) -> Optional[dict]:
        """Get account balance"""
        if exchange_id not in self.exchanges:
            return None
        try:
            balance = await self.exchanges[exchange_id].fetch_balance()
            return balance
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return None
    
    async def get_positions(self, exchange_id: str, symbol: Optional[str] = None) -> List[dict]:
        """Get open positions"""
        if exchange_id not in self.exchanges:
            return []
        try:
            exchange = self.exchanges[exchange_id]
            if hasattr(exchange, 'fetch_positions'):
                positions = await exchange.fetch_positions([symbol] if symbol else None)
                return [p for p in positions if float(p.get('contracts', 0)) != 0]
            return []
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []
    
    async def get_klines(self, exchange_id: str, symbol: str, timeframe: str, limit: int = 100) -> List:
        """Get OHLCV data"""
        if exchange_id not in self.exchanges:
            return []
        try:
            ohlcv = await self.exchanges[exchange_id].fetch_ohlcv(symbol, timeframe, limit=limit)
            return ohlcv
        except Exception as e:
            logger.error(f"Error fetching klines: {e}")
            return []
    
    async def create_order(self, exchange_id: str, symbol: str, order_type: str, 
                          side: str, amount: float, price: Optional[float] = None) -> Optional[dict]:
        """Create an order"""
        if exchange_id not in self.exchanges:
            return None
        try:
            exchange = self.exchanges[exchange_id]
            if order_type == 'market':
                order = await exchange.create_market_order(symbol, side, amount)
            else:
                order = await exchange.create_limit_order(symbol, side, amount, price)
            
            ActivityLogRepository.log('info', f"Order created: {side} {amount} {symbol}", 
                                     details={'order': order})
            return order
        except Exception as e:
            logger.error(f"Error creating order: {e}")
            ActivityLogRepository.log('error', f"Order failed: {e}")
            return None
    
    async def cancel_order(self, exchange_id: str, order_id: str, symbol: str) -> bool:
        """Cancel an order"""
        if exchange_id not in self.exchanges:
            return False
        try:
            await self.exchanges[exchange_id].cancel_order(order_id, symbol)
            return True
        except Exception as e:
            logger.error(f"Error canceling order: {e}")
            return False


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
        
        import math
        
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


# ============== Global Instances ==============

connection_manager = ConnectionManager()
exchange_manager = ExchangeManager()
running_agents: Dict[str, asyncio.Task] = {}


# ============== FastAPI App ==============

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    logger.info("Database initialized")
    ActivityLogRepository.log('info', 'Backend server started')
    yield
    # Cleanup
    for agent_id, task in running_agents.items():
        task.cancel()
    for exchange_id in list(exchange_manager.exchanges.keys()):
        await exchange_manager.disconnect_exchange(exchange_id)
    ActivityLogRepository.log('info', 'Backend server stopped')


app = FastAPI(title="CryptoAgent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Health Check ==============

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_connections": len(connection_manager.active_connections),
        "connected_exchanges": len(exchange_manager.exchanges),
        "running_agents": len(running_agents)
    }


# ============== AI Models API ==============

@app.get("/api/models")
async def get_models():
    models = AIModelRepository.get_all()
    # Mask API keys
    for model in models:
        model['api_key'] = '***' + model['api_key'][-4:] if model.get('api_key') else ''
    return models


@app.post("/api/models")
async def create_model(config: AIModelConfig):
    model_id = config.id or f"model_{uuid.uuid4().hex[:8]}"
    model_data = {
        'id': model_id,
        'name': config.name,
        'provider': config.provider,
        'api_key': config.api_key,
        'base_url': config.base_url,
        'model': config.model,
        'status': 'active'
    }
    result = AIModelRepository.create(model_data)
    ActivityLogRepository.log('info', f"Created AI model: {config.name}", details={'model_id': model_id})
    return result


@app.delete("/api/models/{model_id}")
async def delete_model(model_id: str):
    if AIModelRepository.delete(model_id):
        ActivityLogRepository.log('info', f"Deleted AI model", details={'model_id': model_id})
        return {"success": True}
    raise HTTPException(status_code=404, detail="Model not found")


# ============== Exchanges API ==============

@app.get("/api/exchanges")
async def get_exchanges():
    exchanges = ExchangeRepository.get_all()
    # Mask keys
    for ex in exchanges:
        ex['api_key'] = '***' + ex['api_key'][-4:] if ex.get('api_key') else ''
        ex['secret_key'] = '***' + ex['secret_key'][-4:] if ex.get('secret_key') else ''
    return exchanges


@app.post("/api/exchanges")
async def create_exchange(config: ExchangeConfig):
    exchange_id = config.id or f"ex_{uuid.uuid4().hex[:8]}"
    exchange_data = {
        'id': exchange_id,
        'name': config.name,
        'exchange': config.exchange,
        'api_key': config.api_key,
        'secret_key': config.secret_key,
        'passphrase': config.passphrase,
        'testnet': config.testnet,
        'status': 'disconnected'
    }
    result = ExchangeRepository.create(exchange_data)
    ActivityLogRepository.log('info', f"Created exchange: {config.name}", details={'exchange_id': exchange_id})
    return result


@app.post("/api/exchanges/{exchange_id}/connect")
async def connect_exchange(exchange_id: str):
    config = ExchangeRepository.get_by_id(exchange_id)
    if not config:
        raise HTTPException(status_code=404, detail="Exchange not found")
    
    success = await exchange_manager.connect_exchange(config)
    if success:
        return {"success": True, "status": "connected"}
    raise HTTPException(status_code=500, detail="Failed to connect to exchange")


@app.post("/api/exchanges/{exchange_id}/disconnect")
async def disconnect_exchange(exchange_id: str):
    await exchange_manager.disconnect_exchange(exchange_id)
    return {"success": True, "status": "disconnected"}


@app.delete("/api/exchanges/{exchange_id}")
async def delete_exchange(exchange_id: str):
    await exchange_manager.disconnect_exchange(exchange_id)
    if ExchangeRepository.delete(exchange_id):
        ActivityLogRepository.log('info', f"Deleted exchange", details={'exchange_id': exchange_id})
        return {"success": True}
    raise HTTPException(status_code=404, detail="Exchange not found")


# ============== Agents API ==============

@app.get("/api/agents")
async def get_agents():
    return AgentRepository.get_all()


@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str):
    agent = AgentRepository.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.post("/api/agents")
async def create_agent(config: AgentConfig):
    agent_id = config.id or f"agent_{uuid.uuid4().hex[:8]}"
    agent_data = {
        'id': agent_id,
        'name': config.name,
        'model_id': config.model_id,
        'exchange_id': config.exchange_id,
        'symbol': config.symbol,
        'timeframe': config.timeframe,
        'indicators': config.indicators,
        'prompt': config.prompt,
        'max_position_size': config.max_position_size,
        'risk_per_trade': config.risk_per_trade,
        'default_leverage': config.default_leverage,
        'status': 'stopped'
    }
    result = AgentRepository.create(agent_data)
    ActivityLogRepository.log('info', f"Created agent: {config.name}", agent_id=agent_id)
    return result


@app.post("/api/agents/{agent_id}/start")
async def start_agent(agent_id: str):
    agent = AgentRepository.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if agent_id in running_agents:
        return {"success": True, "status": "already_running"}
    
    # Start agent task
    task = asyncio.create_task(run_agent_loop(agent_id))
    running_agents[agent_id] = task
    
    AgentRepository.update(agent_id, {'status': 'running'})
    ActivityLogRepository.log('info', f"Started agent", agent_id=agent_id)
    
    return {"success": True, "status": "running"}


@app.post("/api/agents/{agent_id}/stop")
async def stop_agent(agent_id: str):
    if agent_id in running_agents:
        running_agents[agent_id].cancel()
        del running_agents[agent_id]
    
    AgentRepository.update(agent_id, {'status': 'stopped'})
    ActivityLogRepository.log('info', f"Stopped agent", agent_id=agent_id)
    
    return {"success": True, "status": "stopped"}


@app.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: str):
    if agent_id in running_agents:
        running_agents[agent_id].cancel()
        del running_agents[agent_id]
    
    if AgentRepository.delete(agent_id):
        ActivityLogRepository.log('info', f"Deleted agent", agent_id=agent_id)
        return {"success": True}
    raise HTTPException(status_code=404, detail="Agent not found")


# ============== Agent Data API ==============

@app.get("/api/agents/{agent_id}/positions")
async def get_agent_positions(agent_id: str):
    agent = AgentRepository.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Try to get live positions from exchange
    if agent['exchange_id'] in exchange_manager.exchanges:
        live_positions = await exchange_manager.get_positions(agent['exchange_id'], agent['symbol'])
        if live_positions:
            return live_positions
    
    # Fall back to database positions
    return PositionRepository.get_open_by_agent(agent_id)


@app.get("/api/agents/{agent_id}/balance")
async def get_agent_balance(agent_id: str):
    agent = AgentRepository.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if agent['exchange_id'] in exchange_manager.exchanges:
        balance = await exchange_manager.get_balance(agent['exchange_id'])
        if balance:
            total = balance.get('total', {})
            free = balance.get('free', {})
            usdt_total = total.get('USDT', 0)
            usdt_free = free.get('USDT', 0)
            
            balance_data = {
                'total_balance': usdt_total,
                'available_balance': usdt_free,
                'unrealized_pnl': 0,
                'realized_pnl': 0
            }
            
            # Record balance history
            BalanceHistoryRepository.record(agent_id, agent['exchange_id'], balance_data)
            
            return balance_data
    
    return {
        'total_balance': 0,
        'available_balance': 0,
        'unrealized_pnl': 0,
        'realized_pnl': 0
    }


@app.get("/api/agents/{agent_id}/orders")
async def get_agent_orders(agent_id: str, limit: int = 50):
    return OrderRepository.get_by_agent(agent_id, limit)


@app.get("/api/agents/{agent_id}/conversations")
async def get_agent_conversations(agent_id: str, limit: int = 100):
    return ConversationRepository.get_by_agent(agent_id, limit)


@app.get("/api/agents/{agent_id}/tool-calls")
async def get_agent_tool_calls(agent_id: str, limit: int = 50):
    return ToolCallRepository.get_by_agent(agent_id, limit)


@app.get("/api/agents/{agent_id}/signals")
async def get_agent_signals(agent_id: str, limit: int = 50):
    return SignalRepository.get_by_agent(agent_id, limit)


@app.get("/api/agents/{agent_id}/profit-history")
async def get_agent_profit_history(agent_id: str, days: int = 30):
    return BalanceHistoryRepository.get_history(agent_id, days)


@app.get("/api/agents/{agent_id}/logs")
async def get_agent_logs(agent_id: str, limit: int = 100):
    return ActivityLogRepository.get_recent(limit, agent_id)


# ============== Market Data API ==============

@app.get("/api/market/ticker/{exchange_id}/{symbol}")
async def get_ticker(exchange_id: str, symbol: str):
    ticker = await exchange_manager.get_ticker(exchange_id, symbol)
    if ticker:
        return ticker
    raise HTTPException(status_code=404, detail="Ticker not available")


@app.get("/api/market/klines/{exchange_id}/{symbol}/{timeframe}")
async def get_klines(exchange_id: str, symbol: str, timeframe: str, limit: int = 100):
    klines = await exchange_manager.get_klines(exchange_id, symbol, timeframe, limit)
    return klines


@app.get("/api/market/indicators/{exchange_id}/{symbol}/{timeframe}")
async def get_indicators(exchange_id: str, symbol: str, timeframe: str):
    klines = await exchange_manager.get_klines(exchange_id, symbol, timeframe, 100)
    if klines:
        return IndicatorCalculator.calculate_all(klines)
    return {}


# ============== Orders API ==============

@app.post("/api/orders")
async def create_order(request: OrderRequest):
    agent = AgentRepository.get_by_id(request.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    order_id = f"order_{uuid.uuid4().hex[:8]}"
    
    # Create order in database
    order_data = {
        'id': order_id,
        'agent_id': request.agent_id,
        'symbol': request.symbol,
        'side': request.side,
        'order_type': request.order_type,
        'amount': request.amount,
        'price': request.price,
        'status': 'pending'
    }
    OrderRepository.create(order_data)
    
    # Execute on exchange
    result = await exchange_manager.create_order(
        agent['exchange_id'],
        request.symbol,
        request.order_type,
        request.side,
        request.amount,
        request.price
    )
    
    if result:
        OrderRepository.update(order_id, {
            'status': 'filled',
            'exchange_order_id': result.get('id'),
            'filled_amount': result.get('filled', request.amount),
            'filled_price': result.get('average', request.price)
        })
        
        # Log conversation
        ConversationRepository.add_message(
            request.agent_id,
            'tool',
            f"Order executed: {request.side} {request.amount} {request.symbol} @ {result.get('average', 'market')}"
        )
        
        return {"success": True, "order": result}
    else:
        OrderRepository.update(order_id, {'status': 'failed'})
        raise HTTPException(status_code=500, detail="Failed to create order")


# ============== Activity Logs API ==============

@app.get("/api/activity")
async def get_activity(limit: int = 100):
    return ActivityLogRepository.get_recent(limit)


# ============== WebSocket ==============

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await connection_manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_json()
            
            if data.get('type') == 'subscribe_agent':
                agent_id = data.get('agent_id')
                # Handle agent subscription
                await websocket.send_json({
                    'type': 'subscribed',
                    'agent_id': agent_id
                })
            
            elif data.get('type') == 'ping':
                await websocket.send_json({'type': 'pong'})
                
    except WebSocketDisconnect:
        connection_manager.disconnect(client_id)


# ============== Agent Loop ==============

async def run_agent_loop(agent_id: str):
    """Main agent loop that monitors market and makes trading decisions"""
    logger.info(f"Starting agent loop for {agent_id}")
    
    try:
        while True:
            agent = AgentRepository.get_by_id(agent_id)
            if not agent or agent['status'] != 'running':
                break
            
            exchange_id = agent['exchange_id']
            symbol = agent['symbol']
            timeframe = agent['timeframe']
            
            # Get market data
            klines = await exchange_manager.get_klines(exchange_id, symbol, timeframe, 100)
            if not klines:
                await asyncio.sleep(10)
                continue
            
            # Calculate indicators
            indicators = IndicatorCalculator.calculate_all(klines)
            
            # Log analysis
            ConversationRepository.add_message(
                agent_id,
                'system',
                f"Market analysis: {symbol} @ {indicators.get('current_price', 'N/A')} | RSI: {indicators.get('rsi', 'N/A')} | ADX: {indicators.get('adx', 'N/A')}"
            )
            
            # Broadcast to WebSocket clients
            await connection_manager.broadcast({
                'type': 'agent_update',
                'agent_id': agent_id,
                'indicators': indicators,
                'timestamp': datetime.now().isoformat()
            })
            
            # Sleep based on timeframe
            sleep_map = {'1m': 60, '5m': 300, '15m': 900, '30m': 1800, '1h': 3600, '4h': 14400, '1d': 86400}
            await asyncio.sleep(sleep_map.get(timeframe, 60))
            
    except asyncio.CancelledError:
        logger.info(f"Agent {agent_id} stopped")
    except Exception as e:
        logger.error(f"Agent {agent_id} error: {e}")
        ActivityLogRepository.log('error', f"Agent error: {e}", agent_id=agent_id)
        AgentRepository.update(agent_id, {'status': 'stopped'})


# ============== Main ==============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
