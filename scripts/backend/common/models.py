"""
Pydantic models for API configuration
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any


class AIModelConfig(BaseModel):
    """AI Model configuration"""
    id: Optional[str] = None
    name: str
    provider: str
    api_key: str
    base_url: Optional[str] = None
    model: str

    class Config:
        json_schema_extra = {
            "example": {
                "name": "GPT-4",
                "provider": "openai",
                "api_key": "sk-xxx",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4"
            }
        }


class ExchangeConfig(BaseModel):
    """Exchange configuration"""
    id: Optional[str] = None
    name: str
    exchange: str
    api_keys: Optional[Dict[str, str]] = None
    api_key: Optional[str] = None
    secret: Optional[str] = None
    passphrase: Optional[str] = None
    testnet: bool = True

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Binance Account",
                "exchange": "binance",
                "api_key": "xxx",
                "secret": "xxx",
                "testnet": True
            }
        }


class AgentConfig(BaseModel):
    """Trading Agent configuration"""
    id: Optional[str] = None
    name: str
    model_id: str
    exchange_id: str
    symbols: list[str]
    timeframe: str
    indicators: list[str] = []
    prompt: Optional[str] = None
    max_position_size: Optional[float] = 1000.0
    risk_per_trade: Optional[float] = 0.02
    default_leverage: Optional[float] = 1.0

    class Config:
        json_schema_extra = {
            "example": {
                "name": "BTC/USDT Agent",
                "model_id": "model_xxx",
                "exchange_id": "ex_xxx",
                "symbols": ["BTC/USDT"],
                "timeframe": "1h",
                "indicators": ["RSI", "MACD"],
                "prompt": "Trade aggressively on signals",
                "max_position_size": 1000.0,
                "risk_per_trade": 0.02,
                "default_leverage": 1.0
            }
        }


class OrderRequest(BaseModel):
    """Order creation request"""
    agent_id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    order_type: str  # 'market' or 'limit'
    amount: float
    price: Optional[float] = None

    class Config:
        json_schema_extra = {
            "example": {
                "agent_id": "agent_xxx",
                "symbol": "BTC/USDT",
                "side": "buy",
                "order_type": "market",
                "amount": 0.01,
                "price": None
            }
        }
