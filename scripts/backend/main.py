"""
CryptoAgent Backend - Main Entry Point
Python + ccxt.pro for exchange WebSocket connections and REST API

Requirements:
- pip install -r requirements.txt
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from logger_config import init_logging, get_logger
from ai_model_config import get_or_set_base_url
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
from exchange_manager import ExchangeManager
from agent_manager import AgentManager
from routes.agent_conversation_routes import router as conversation_router
from routes.auth_routes import router as auth_router

# Initialize logging
init_logging()
logger = get_logger(__name__)


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
    # Support both new format (api_keys as dict) and legacy format (separate fields)
    api_keys: Optional[Dict[str, str]] = None
    api_key: Optional[str] = None
    secret: Optional[str] = None
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
agent_manager: Optional[AgentManager] = None  # Will be initialized in lifespan


# ============== FastAPI App ==============

@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent_manager
    
    init_database()
    logger.info("Database initialized")
    
    # ============ Step 1: 加载和初始化交易所 ============
    try:
        enabled_exchanges = ExchangeRepository.get_all()
        if enabled_exchanges:
            logger.info(f"从数据库加载 {len(enabled_exchanges)} 个交易所配置")
            for ex in enabled_exchanges:
                success = await exchange_manager.add_exchange({
                    'id': ex['id'],
                    'exchange': ex['exchange'],
                    'api_keys': ex.get('api_keys', {}),
                    'testnet': ex.get('testnet', True)
                })
                
                # 更新数据库中的状态
                if success:
                    ExchangeRepository.update(ex['id'], {'status': 'connected'})
                    logger.info(f"✅ 启动时连接交易所: {ex['name']}")
                else:
                    ExchangeRepository.update(ex['id'], {'status': 'error'})
                    logger.warning(f"❌ 启动时连接交易所失败: {ex['name']}")
        else:
            logger.info("未配置任何交易所")
    except Exception as e:
        logger.error(f"初始化交易所失败: {e}")
    
    # ============ Step 2: 加载和初始化模型 ============
    try:
        enabled_models = AIModelRepository.get_all()
        if enabled_models:
            logger.info(f"从数据库加载 {len(enabled_models)} 个AI模型配置")
            active_models = [m for m in enabled_models if m.get('status') == 'active']
            logger.info(f"其中 {len(active_models)} 个模型处于活跃状态")
        else:
            logger.info("未配置任何AI模型")
    except Exception as e:
        logger.error(f"加载AI模型失败: {e}")
    
    # ============ Step 3: 初始化 AgentManager ============
    try:
        agent_manager = AgentManager(exchange_manager)
        exchange_manager.set_data_event_handler(agent_manager.handle_data_event)
        logger.info("✅ AgentManager 已初始化")
    except Exception as e:
        logger.error(f"初始化 AgentManager 失败: {e}")
        agent_manager = None
    
    # ============ Step 4: 加载和启动Agents ============
    if agent_manager:
        try:
            enabled_agents = AgentRepository.get_all()
            stopped_agents = [a for a in enabled_agents if a.get('status') == 'stopped']
            running_agents = [a for a in enabled_agents if a.get('status') == 'running']
            
            if enabled_agents:
                logger.info(f"从数据库加载 {len(enabled_agents)} 个Agent ({len(running_agents)} 个需要启动)")
            else:
                logger.info("未配置任何Agent")
                enabled_agents = []
            
            # 先创建所有 Agent 实例
            created_agents = []
            for agent in enabled_agents:
                try:
                    logger.info(f"正在创建 Agent: {agent['name']} (ID: {agent['id']})")
                    
                    agent_config = {
                        'max_position_size': agent.get('max_position_size', 1000.0),
                        'risk_per_trade': agent.get('risk_per_trade', 0.02),
                        'default_leverage': agent.get('default_leverage', 1),
                        'decision_interval': 60
                    }
                    
                    await agent_manager.create_agent(
                        agent_id=agent['id'],
                        name=agent['name'],
                        model_id=agent['model_id'],
                        exchange_id=agent['exchange_id'],
                        symbol=agent['symbol'],
                        timeframe=agent['timeframe'],
                        indicators=agent['indicators'],
                        prompt=agent['prompt'],
                        config=agent_config
                    )
                    created_agents.append(agent['id'])
                    logger.info(f"✅ 成功创建 Agent: {agent['name']}")
                except Exception as e:
                    logger.error(f"❌ 创建 Agent {agent['name']} (ID: {agent['id']}) 失败: {e}", exc_info=True)
                    AgentRepository.update(agent['id'], {'status': 'error'})
            
            logger.info(f"成功创建 {len(created_agents)} 个Agent")
            
            # 然后启动之前运行中的 agents
            started_agents = []
            for agent in running_agents:
                try:
                    if agent['id'] not in created_agents:
                        logger.warning(f"Agent {agent['name']} 创建失败，跳过启动")
                        continue
                    
                    logger.info(f"正在启动 Agent: {agent['name']} (ID: {agent['id']})")
                    await agent_manager.start_agent(agent['id'])
                    started_agents.append(agent['id'])
                    logger.info(f"✅ 成功启动 Agent: {agent['name']}")
                except Exception as e:
                    logger.error(f"❌ 启动 Agent {agent['name']} (ID: {agent['id']}) 失败: {e}", exc_info=True)
                    AgentRepository.update(agent['id'], {'status': 'error'})
            
            logger.info(f"成功启动 {len(started_agents)} 个Agent")
        except Exception as e:
            logger.error(f"加载Agents失败: {e}", exc_info=True)
    
    ActivityLogRepository.log('info', 'Backend server started')
    logger.info("=" * 50)
    logger.info("✅ 后端服务启动完成")
    logger.info("=" * 50)
    
    yield
    
    # Cleanup
    logger.info("开始清理资源...")
    if agent_manager:
        await agent_manager.cleanup()
    
    await exchange_manager.close_all()
    ActivityLogRepository.log('info', 'Backend server stopped')


app = FastAPI(title="CryptoAgent API", lifespan=lifespan)

# CORS configuration - allow specific origins when using credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://localhost:3000",
        # Add production frontend URL here if needed
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(conversation_router)
app.include_router(auth_router)

# ============== Health Check ==============

@app.get("/health")
@app.get("/api/health")
async def health_check():
    running_count = len(agent_manager.get_all_agents()) if agent_manager else 0
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_connections": len(connection_manager.active_connections),
        "connected_exchanges": len(exchange_manager.exchanges),
        "running_agents": running_count
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
    
    # Use provided base_url or get default for the provider
    base_url = get_or_set_base_url(config.provider, config.base_url)
    
    model_data = {
        'id': model_id,
        'name': config.name,
        'provider': config.provider,
        'api_key': config.api_key,
        'base_url': base_url,
        'model': config.model,
        'status': 'active'
    }
    result = AIModelRepository.create(model_data)
    ActivityLogRepository.log('info', f"Created AI model: {config.name}", details={'model_id': model_id})
    return result


@app.delete("/api/models/{model_id}")
async def delete_model(model_id: str):
    # 检查是否有agent使用这个model
    agents = AgentRepository.get_by_model_id(model_id)
    if agents:
        agent_names = [agent['name'] for agent in agents]
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete model. It is used by {len(agents)} agent(s): {', '.join(agent_names)}"
        )
    
    if AIModelRepository.delete(model_id):
        ActivityLogRepository.log('info', f"Deleted AI model", details={'model_id': model_id})
        return {"success": True}
    raise HTTPException(status_code=404, detail="Model not found")


@app.get("/api/models/{model_id}/usage")
async def check_model_usage(model_id: str):
    """检查model是否被agent使用"""
    agents = AgentRepository.get_by_model_id(model_id)
    return {
        "isUsed": len(agents) > 0,
        "agents": [{"id": a['id'], "name": a['name'], "status": a['status']} for a in agents]
    }

@app.put("/api/models/{model_id}")
async def update_model(model_id: str, data: dict):
    # Accepts partial updates (e.g., {"status": "inactive"})
    existing = AIModelRepository.get_by_id(model_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Model not found")

    updated = AIModelRepository.update(model_id, data)
    ActivityLogRepository.log('info', f"Updated AI model", details={'model_id': model_id, 'data': data})
    return updated


@app.post("/api/models/{model_id}/test-connection")
async def test_model_connection(model_id: str):
    """测试 LLM 模型连接是否正确"""
    from models.llm_model import LLMModel
    
    model_config = AIModelRepository.get_by_id(model_id)
    if not model_config:
        raise HTTPException(status_code=404, detail="Model not found")
    
    try:
        # 创建模型实例
        llm_model = LLMModel(
            api_key=model_config['api_key'],
            model=model_config['model'],
            base_url=model_config.get('base_url'),
            provider=model_config.get('provider', 'openai'),
        )
        
        # 创建对话
        llm_model.create_conversation("You are a helpful assistant.")
        
        # 测试 API 连接
        response = llm_model.chat_completion("Hello, please respond with a single word.")
        
        return {
            "success": True,
            "message": "Connection successful",
            "config": llm_model.get_config_info(),
            "response": response.get("content", ""),
        }
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Model connection test failed: {error_msg}")
        return {
            "success": False,
            "message": "Connection failed",
            "error": error_msg,
            "config": {
                "provider": model_config.get('provider', 'openai'),
                "model": model_config['model'],
                "base_url": model_config.get('base_url') or "default",
            }
        }


# ============== Exchanges API ==============

@app.get("/api/exchanges")
async def get_exchanges():
    exchanges = ExchangeRepository.get_all()
    # Mask sensitive keys in api_keys
    for ex in exchanges:
        if ex.get('api_keys') and isinstance(ex['api_keys'], dict):
            api_keys = ex['api_keys'].copy()
            # Mask api_key
            if api_keys.get('api_key'):
                api_keys['api_key'] = '***' + api_keys['api_key'][-4:]
            # Mask secret
            if api_keys.get('secret'):
                api_keys['secret'] = '***' + api_keys['secret'][-4:]
            # Mask passphrase
            if api_keys.get('passphrase'):
                api_keys['passphrase'] = '***' + api_keys['passphrase'][-4:] if api_keys['passphrase'] else ''
            ex['api_keys'] = api_keys
    return exchanges


@app.get("/api/exchanges/{exchange_id}/status")
async def get_exchange_status(exchange_id: str):
    """获取交易所连接状态"""
    config = ExchangeRepository.get_by_id(exchange_id)
    if not config:
        raise HTTPException(status_code=404, detail="Exchange not found")
    
    exchange = exchange_manager.get_exchange(exchange_id)
    is_connected = exchange is not None
    
    return {
        'id': exchange_id,
        'name': config['name'],
        'exchange': config['exchange'],
        'connected': is_connected,
        'status': config.get('status', 'disconnected'),
        'testnet': config.get('testnet', False)
    }


@app.post("/api/exchanges")
async def create_exchange(config: ExchangeConfig):
    exchange_id = config.id or f"ex_{uuid.uuid4().hex[:8]}"
    
    # Normalize api_keys: support both new format (api_keys dict) and legacy format (separate fields)
    if config.api_keys:
        api_keys = config.api_keys
    else:
        api_keys = {
            'api_key': config.api_key or '',
            'secret': config.secret or '',
            'passphrase': config.passphrase or ''
        }
    
    # Remove empty values
    api_keys = {k: v for k, v in api_keys.items() if v}
    
    # 保存到数据库
    exchange_data = {
        'id': exchange_id,
        'name': config.name,
        'exchange': config.exchange,
        'api_keys': api_keys,
        'testnet': config.testnet,
        'status': 'disconnected'
    }
    result = ExchangeRepository.create(exchange_data)
    
    # 动态添加到 ExchangeManager
    try:
        success = await exchange_manager.add_exchange({
            'id': exchange_id,
            'exchange': config.exchange,
            'api_keys': api_keys,
            'testnet': config.testnet
        })
        
        if success:
            ExchangeRepository.update(exchange_id, {'status': 'connected'})
            ActivityLogRepository.log('info', f"Created and connected exchange: {config.name}", 
                                     details={'exchange_id': exchange_id})
        else:
            ExchangeRepository.update(exchange_id, {'status': 'error'})
            ActivityLogRepository.log('warning', f"Created exchange but connection failed: {config.name}", 
                                     details={'exchange_id': exchange_id})
    except Exception as e:
        logger.error(f"Failed to add exchange: {e}")
        ExchangeRepository.update(exchange_id, {'status': 'error'})
        ActivityLogRepository.log('error', f"Failed to connect exchange: {e}", 
                                 details={'exchange_id': exchange_id})
    
    return result


@app.put("/api/exchanges/{exchange_id}")
async def update_exchange(exchange_id: str, config: ExchangeConfig):
    """更新交易所配置"""
    existing = ExchangeRepository.get_by_id(exchange_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Exchange not found")
    
    # Normalize api_keys: support both new format (api_keys dict) and legacy format (separate fields)
    if config.api_keys:
        api_keys = config.api_keys
    else:
        api_keys = {
            'api_key': config.api_key or '',
            'secret': config.secret or '',
            'passphrase': config.passphrase or ''
        }
    
    # Remove empty values
    api_keys = {k: v for k, v in api_keys.items() if v}
    
    # 更新数据库
    update_data = {
        'name': config.name,
        'exchange': config.exchange,
        'api_keys': api_keys,
        'testnet': config.testnet,
        'status': 'disconnected'
    }
    result = ExchangeRepository.update(exchange_id, update_data)
    
    # 更新 ExchangeManager
    try:
        success = await exchange_manager.update_exchange(exchange_id, {
            'id': exchange_id,
            'exchange': config.exchange,
            'api_keys': api_keys,
            'testnet': config.testnet
        })
        
        if success:
            ExchangeRepository.update(exchange_id, {'status': 'connected'})
            ActivityLogRepository.log('info', f"Updated exchange: {config.name}", 
                                     details={'exchange_id': exchange_id})
        else:
            ExchangeRepository.update(exchange_id, {'status': 'error'})
            ActivityLogRepository.log('warning', f"Updated exchange but connection failed: {config.name}", 
                                     details={'exchange_id': exchange_id})
    except Exception as e:
        logger.error(f"Failed to update exchange: {e}")
        ExchangeRepository.update(exchange_id, {'status': 'error'})
        ActivityLogRepository.log('error', f"Failed to update exchange connection: {e}", 
                                 details={'exchange_id': exchange_id})
    
    return result


@app.post("/api/exchanges/{exchange_id}/connect")
async def connect_exchange(exchange_id: str):
    """连接交易所"""
    config = ExchangeRepository.get_by_id(exchange_id)
    if not config:
        raise HTTPException(status_code=404, detail="Exchange not found")
    
    try:
        success = await exchange_manager.add_exchange({
            'id': exchange_id,
            'exchange': config['exchange'],
            'api_keys': config.get('api_keys', {}),
            'testnet': config.get('testnet', True)
        })
        
        if success:
            ExchangeRepository.update(exchange_id, {'status': 'connected'})
            ActivityLogRepository.log('info', f"Connected to exchange", details={'exchange_id': exchange_id})
            return {"success": True, "status": "connected"}
        else:
            ExchangeRepository.update(exchange_id, {'status': 'error'})
            raise HTTPException(status_code=500, detail="Failed to connect to exchange")
    except Exception as e:
        logger.error(f"Failed to connect exchange: {e}")
        ExchangeRepository.update(exchange_id, {'status': 'error'})
        raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")


@app.post("/api/exchanges/{exchange_id}/disconnect")
async def disconnect_exchange(exchange_id: str):
    """断开交易所连接"""
    success = await exchange_manager.remove_exchange(exchange_id)
    
    if success:
        ExchangeRepository.update(exchange_id, {'status': 'disconnected'})
        ActivityLogRepository.log('info', f"Disconnected from exchange", details={'exchange_id': exchange_id})
        return {"success": True, "status": "disconnected"}
    
    raise HTTPException(status_code=500, detail="Failed to disconnect")


@app.delete("/api/exchanges/{exchange_id}")
async def delete_exchange(exchange_id: str):
    """删除交易所"""
    # 检查是否有agent使用这个exchange
    agents = AgentRepository.get_by_exchange_id(exchange_id)
    if agents:
        agent_names = [agent['name'] for agent in agents]
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete exchange. It is used by {len(agents)} agent(s): {', '.join(agent_names)}"
        )
    
    await exchange_manager.remove_exchange(exchange_id)
    
    if ExchangeRepository.delete(exchange_id):
        ActivityLogRepository.log('info', f"Deleted exchange", details={'exchange_id': exchange_id})
        return {"success": True}
    
    raise HTTPException(status_code=404, detail="Exchange not found")


@app.get("/api/exchanges/{exchange_id}/usage")
async def check_exchange_usage(exchange_id: str):
    """检查exchange是否被agent使用"""
    agents = AgentRepository.get_by_exchange_id(exchange_id)
    return {
        "isUsed": len(agents) > 0,
        "agents": [{"id": a['id'], "name": a['name'], "status": a['status']} for a in agents]
    }


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
    if not agent_manager:
        raise HTTPException(status_code=500, detail="Agent manager not initialized")
    
    agent_id = config.id or f"agent_{uuid.uuid4().hex[:8]}"
    
    # 保存到数据库
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
    
    # 创建 Agent 实例
    try:
        agent_config = {
            'max_position_size': config.max_position_size,
            'risk_per_trade': config.risk_per_trade,
            'default_leverage': config.default_leverage,
            'decision_interval': 60  # 默认60秒决策一次
        }
        
        await agent_manager.create_agent(
            agent_id=agent_id,
            name=config.name,
            model_id=config.model_id,
            exchange_id=config.exchange_id,
            symbol=config.symbol,
            timeframe=config.timeframe,
            indicators=config.indicators,
            prompt=config.prompt,
            config=agent_config
        )
        
        ActivityLogRepository.log('info', f"Created agent: {config.name}", agent_id=agent_id)
        return result
    except Exception as e:
        # 如果创建失败，从数据库删除
        AgentRepository.delete(agent_id)
        logger.error(f"Failed to create agent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/{agent_id}/start")
async def start_agent(agent_id: str):
    if not agent_manager:
        raise HTTPException(status_code=500, detail="Agent manager not initialized")
    
    agent = AgentRepository.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # 如果 Agent 实例不存在，先创建
    if not agent_manager.get_agent(agent_id):
        agent_config = {
            'max_position_size': agent.get('max_position_size', 1000.0),
            'risk_per_trade': agent.get('risk_per_trade', 0.02),
            'default_leverage': agent.get('default_leverage', 1),
            'decision_interval': 60
        }
        
        await agent_manager.create_agent(
            agent_id=agent_id,
            name=agent['name'],
            model_id=agent['model_id'],
            exchange_id=agent['exchange_id'],
            symbol=agent['symbol'],
            timeframe=agent['timeframe'],
            indicators=agent['indicators'],
            prompt=agent['prompt'],
            config=agent_config
        )
    
    # 启动 Agent
    success = await agent_manager.start_agent(agent_id)
    
    if success:
        ActivityLogRepository.log('info', f"Started agent", agent_id=agent_id)
        return {"success": True, "status": "running"}
    else:
        raise HTTPException(status_code=500, detail="Failed to start agent")


@app.post("/api/agents/{agent_id}/stop")
async def stop_agent(agent_id: str):
    if not agent_manager:
        raise HTTPException(status_code=500, detail="Agent manager not initialized")
    
    success = await agent_manager.stop_agent(agent_id)
    
    if success:
        ActivityLogRepository.log('info', f"Stopped agent", agent_id=agent_id)
        return {"success": True, "status": "stopped"}
    else:
        raise HTTPException(status_code=500, detail="Failed to stop agent")


@app.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: str):
    if not agent_manager:
        raise HTTPException(status_code=500, detail="Agent manager not initialized")
    
    success = await agent_manager.delete_agent(agent_id)
    
    if success:
        ActivityLogRepository.log('info', f"Deleted agent", agent_id=agent_id)
        return {"success": True}
    else:
        raise HTTPException(status_code=404, detail="Agent not found")
        return {"success": True}
    raise HTTPException(status_code=404, detail="Agent not found")


# ============== Agent Data API ==============

@app.get("/api/agents/{agent_id}/positions")
async def get_agent_positions(agent_id: str):
    agent = AgentRepository.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # 尝试从交易所获取实时持仓
    exchange = exchange_manager.get_exchange(agent['exchange_id'])
    if exchange:
        try:
            if hasattr(exchange, 'fetch_positions'):
                live_positions = await exchange.fetch_positions([agent['symbol']])
                if live_positions:
                    return [p for p in live_positions if float(p.get('contracts', 0)) != 0]
        except Exception as e:
            logger.error(f"Error fetching live positions: {e}")
    
    # 降级到数据库持仓
    return PositionRepository.get_open_by_agent(agent_id)


@app.get("/api/agents/{agent_id}/balance")
async def get_agent_balance(agent_id: str):
    """
    获取指定 Agent 的账户余额信息
    
    Returns:
        {
            'total_balance': float,          # 账户总余额
            'available_balance': float,      # 可用余额
            'unrealized_pnl': float,         # 未实现盈亏
            'realized_pnl': float,           # 已实现盈亏
            'timestamp': str                 # ISO格式时间戳
        }
    """
    try:
        # 验证 Agent 存在
        agent = AgentRepository.get_by_id(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
        
        # 获取交易所实例
        exchange = exchange_manager.get_exchange(agent['exchange_id'])
        if not exchange:
            logger.warning(f"Exchange {agent['exchange_id']} not connected for agent {agent_id}")
            raise HTTPException(
                status_code=503,
                detail=f"Exchange {agent['exchange_id']} is not connected"
            )
        
        # 从交易所获取余额数据
        try:
            balance = await exchange.fetch_balance()
        except Exception as e:
            logger.error(f"Failed to fetch balance from exchange {agent['exchange_id']}: {e}")
            raise HTTPException(
                status_code=502,
                detail=f"Failed to fetch balance from exchange: {str(e)}"
            )
        
        if not balance:
            logger.warning(f"Empty balance response from exchange {agent['exchange_id']}")
            raise HTTPException(status_code=502, detail="Exchange returned empty balance")
        
        # 解析余额数据（支持多种币种和交易所格式）
        total = balance.get('total', {})
        free = balance.get('free', {})
        
        # 优先使用 USDT，如果没有则尝试其他币种
        usdt_total = total.get('USDT', 0)
        usdt_free = free.get('USDT', 0)
        
        # 如果 USDT 为 0，尝试其他常见的稳定币
        if not usdt_total and not usdt_free:
            for currency in ['USDC', 'BUSD', 'DAI', 'FDUSD']:
                if currency in total or currency in free:
                    usdt_total = total.get(currency, 0)
                    usdt_free = free.get(currency, 0)
                    break
        
        # 构建响应数据
        balance_data = {
            'total_balance': round(float(usdt_total), 8),
            'available_balance': round(float(usdt_free), 8),
            'unrealized_pnl': 0.0,  # 从 Position 表获取
            'realized_pnl': 0.0,    # 从 Order 表获取
            'timestamp': datetime.now().isoformat()
        }
        
        # 记录余额历史（异步，不阻塞响应）
        try:
            BalanceHistoryRepository.record(agent_id, agent['exchange_id'], balance_data)
            logger.debug(f"Recorded balance history for agent {agent_id}")
        except Exception as e:
            logger.error(f"Failed to record balance history: {e}")
        
        logger.info(f"Successfully fetched balance for agent {agent_id}: {balance_data}")
        return balance_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_agent_balance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/agents/{agent_id}/orders")
async def get_agent_orders(agent_id: str, limit: int = 50):
    return OrderRepository.get_by_agent(agent_id, limit)





@app.get("/api/agents/{agent_id}/profit-history")
async def get_agent_profit_history(agent_id: str, days: int = 30):
    return BalanceHistoryRepository.get_history(agent_id, days)


@app.get("/api/agents/{agent_id}/logs")
async def get_agent_logs(agent_id: str, limit: int = 100):
    return ActivityLogRepository.get_recent(limit, agent_id)


# ============== Market Data API ==============

@app.get("/api/market/ticker/{exchange_id}/{symbol}")
async def get_ticker(exchange_id: str, symbol: str):
    exchange = exchange_manager.get_exchange(exchange_id)
    if not exchange:
        raise HTTPException(status_code=404, detail="Exchange not connected")
    
    try:
        ticker = await exchange.fetch_ticker(symbol)
        return ticker
    except Exception as e:
        logger.error(f"Error fetching ticker: {e}")
        raise HTTPException(status_code=404, detail="Ticker not available")


@app.get("/api/market/klines/{exchange_id}/{symbol}/{timeframe}")
async def get_klines(exchange_id: str, symbol: str, timeframe: str, limit: int = 100):
    exchange = exchange_manager.get_exchange(exchange_id)
    if not exchange:
        raise HTTPException(status_code=404, detail="Exchange not connected")
    
    try:
        klines = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        return klines
    except Exception as e:
        logger.error(f"Error fetching klines: {e}")
        return []


@app.get("/api/market/indicators/{exchange_id}/{symbol}/{timeframe}")
async def get_indicators(exchange_id: str, symbol: str, timeframe: str):
    exchange = exchange_manager.get_exchange(exchange_id)
    if not exchange:
        raise HTTPException(status_code=404, detail="Exchange not connected")
    
    try:
        klines = await exchange.fetch_ohlcv(symbol, timeframe, 100)
        if klines:
            return IndicatorCalculator.calculate_all(klines)
    except Exception as e:
        logger.error(f"Error fetching indicators: {e}")
    
    return {}


# ============== Orders API ==============

@app.post("/api/orders")
async def create_order(request: OrderRequest):
    agent = AgentRepository.get_by_id(request.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    order_id = f"order_{uuid.uuid4().hex[:8]}"
    
    # 创建订单记录
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
    
    # 在交易所执行
    exchange = exchange_manager.get_exchange(agent['exchange_id'])
    if not exchange:
        OrderRepository.update(order_id, {'status': 'failed'})
        raise HTTPException(status_code=500, detail="Exchange not connected")
    
    try:
        if request.order_type == 'market':
            result = await exchange.create_market_order(request.symbol, request.side, request.amount)
        else:
            result = await exchange.create_limit_order(request.symbol, request.side, request.amount, request.price)
        
        OrderRepository.update(order_id, {
            'status': 'filled',
            'exchange_order_id': result.get('id'),
            'filled_amount': result.get('filled', request.amount),
            'filled_price': result.get('average', request.price)
        })
        
        # 记录对话
        ConversationRepository.add_message(
            request.agent_id,
            'tool',
            f"Order executed: {request.side} {request.amount} {request.symbol} @ {result.get('average', 'market')}"
        )
        
        ActivityLogRepository.log('info', f"Order created: {request.side} {request.amount} {request.symbol}", 
                                 details={'order': result})
        
        return {"success": True, "order": result}
    
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        OrderRepository.update(order_id, {'status': 'failed'})
        ActivityLogRepository.log('error', f"Order failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create order: {str(e)}")


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
            
            # 获取交易所实例
            exchange = exchange_manager.get_exchange(exchange_id)
            if not exchange:
                logger.error(f"Exchange {exchange_id} not available for agent {agent_id}")
                await asyncio.sleep(10)
                continue
            
            # 获取市场数据
            try:
                klines = await exchange.fetch_ohlcv(symbol, timeframe, 100)
                if not klines:
                    await asyncio.sleep(10)
                    continue
                
                # 计算指标
                indicators = IndicatorCalculator.calculate_all(klines)
                
                # 记录分析
                ConversationRepository.add_message(
                    agent_id,
                    'system',
                    f"Market analysis: {symbol} @ {indicators.get('current_price', 'N/A')} | RSI: {indicators.get('rsi', 'N/A')} | ADX: {indicators.get('adx', 'N/A')}"
                )
                
                # 广播到 WebSocket 客户端
                await connection_manager.broadcast({
                    'type': 'agent_update',
                    'agent_id': agent_id,
                    'indicators': indicators,
                    'timestamp': datetime.now().isoformat()
                })
            
            except Exception as e:
                logger.error(f"Error analyzing market for agent {agent_id}: {e}")
            
            # 根据 timeframe 调整睡眠时间
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
    uvicorn.run(app, host="127.0.0.1", port=8000)
