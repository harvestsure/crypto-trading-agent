"""
Market Data and Orders API routes
"""

import uuid
from fastapi import APIRouter, HTTPException
from database import (
    OrderRepository,
    ConversationRepository,
    ActivityLogRepository,
    AgentRepository
)
from logger_config import get_logger
from common.models import OrderRequest
from utils.indicator_calculator import IndicatorCalculator

router = APIRouter(tags=["market", "orders"])
logger = get_logger(__name__)

# These will be injected from the app
exchange_manager = None


def set_exchange_manager(em):
    """Inject exchange manager dependency"""
    global exchange_manager
    exchange_manager = em


@router.get("/api/market/ticker/{exchange_id}/{symbol}")
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


@router.get("/api/market/klines/{exchange_id}/{symbol}/{timeframe}")
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


@router.get("/api/market/indicators/{exchange_id}/{symbol}/{timeframe}")
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


@router.post("/api/orders")
async def create_order(request: OrderRequest):
    agent = AgentRepository.get_by_id(request.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    order_id = f"order_{uuid.uuid4().hex[:8]}"
    
    # Create order record
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
        
        # Record conversation
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
