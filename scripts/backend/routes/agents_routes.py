"""
Agents API routes
"""

import uuid
from fastapi import APIRouter, HTTPException
from datetime import datetime
from database import (
    AgentRepository, 
    AIModelRepository,
    PositionRepository,
    OrderRepository,
    BalanceHistoryRepository,
    ActivityLogRepository
)
from logger_config import get_logger
from common.models import AgentConfig
from exchange_manager import ExchangeManager
from agent_manager import AgentManager
import config

router = APIRouter(prefix="/api/agents", tags=["agents"])
logger = get_logger(__name__)

# These will be injected from the app
agent_manager: AgentManager = None
exchange_manager: ExchangeManager = None


def set_managers(am, em):
    """Inject managers dependency"""
    global agent_manager, exchange_manager
    agent_manager = am
    exchange_manager = em


@router.get("")
async def get_agents():
    return AgentRepository.get_all()


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    agent = AgentRepository.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("")
async def create_agent(config: AgentConfig):
    if not agent_manager:
        raise HTTPException(status_code=500, detail="Agent manager not initialized")
    
    try:
        agent_id = config.id or f"agent_{uuid.uuid4().hex[:8]}"
        
        # Save to database
        agent_data = {
            'id': agent_id,
            'name': config.name,
            'model_id': config.model_id,
            'exchange_id': config.exchange_id,
            'symbols': config.symbols or [],
            'timeframe': config.timeframe,
            'indicators': config.indicators or [],
            'prompt': config.prompt or '',
            'max_position_size': config.max_position_size or 1000.0,
            'risk_per_trade': config.risk_per_trade or 0.02,
            'default_leverage': config.default_leverage or 1.0,
            'status': 'stopped'
        }
        
        try:
            result = AgentRepository.create(agent_data)
        except Exception as db_error:
            logger.error(f"Database error while creating agent: {db_error}", exc_info=True)
            raise Exception(f"Database error: {str(db_error)}")
        
        if not result:
            raise Exception("Agent was created but could not be retrieved from database")
        
        # Create Agent instance
        agent_config = {
            'max_position_size': config.max_position_size or 1000.0,
            'risk_per_trade': config.risk_per_trade or 0.02,
            'default_leverage': config.default_leverage or 1.0,
            'decision_interval': 60
        }
        
        await agent_manager.create_agent(
            agent_id=agent_id,
            name=config.name,
            model_id=config.model_id,
            exchange_id=config.exchange_id,
            symbols=config.symbols or [],
            timeframe=config.timeframe,
            indicators=config.indicators or [],
            prompt=config.prompt or '',
            config=agent_config
        )
        
        ActivityLogRepository.log('info', f"Created agent: {config.name}", agent_id=agent_id)
        logger.info(f"Agent created successfully: {agent_id}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create agent: {e}", exc_info=True)
        # Try to clean up if agent was saved to database
        try:
            if 'agent_id' in locals():
                AgentRepository.delete(agent_id)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to create agent: {str(e)}")


@router.post("/{agent_id}/start")
async def start_agent(agent_id: str):
    if not agent_manager:
        raise HTTPException(status_code=500, detail="Agent manager not initialized")
    
    agent = AgentRepository.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Create Agent instance if it doesn't exist
    if not agent_manager.get_agent(agent_id):
        agent_config = {
            'max_position_size': agent.get('max_position_size', 1000.0),
            'risk_per_trade': agent.get('risk_per_trade', 0.02),
            'default_leverage': agent.get('default_leverage', 1),
            'decision_interval': 60
        }
        symbols = agent.get('symbols') if agent.get('symbols') else []
        await agent_manager.create_agent(
            agent_id=agent_id,
            name=agent['name'],
            model_id=agent['model_id'],
            exchange_id=agent['exchange_id'],
            symbols=symbols,
            timeframe=agent['timeframe'],
            indicators=agent['indicators'],
            prompt=agent['prompt'],
            config=agent_config
        )
    
    # Start Agent
    success = await agent_manager.start_agent(agent_id)
    
    if success:
        ActivityLogRepository.log('info', f"Started agent", agent_id=agent_id)
        return {"success": True, "status": "running"}
    else:
        raise HTTPException(status_code=500, detail="Failed to start agent")


@router.post("/{agent_id}/stop")
async def stop_agent(agent_id: str):
    if not agent_manager:
        raise HTTPException(status_code=500, detail="Agent manager not initialized")
    
    success = await agent_manager.stop_agent(agent_id)
    
    if success:
        ActivityLogRepository.log('info', f"Stopped agent", agent_id=agent_id)
        return {"success": True, "status": "stopped"}
    else:
        raise HTTPException(status_code=500, detail="Failed to stop agent")


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    if not agent_manager:
        raise HTTPException(status_code=500, detail="Agent manager not initialized")
    
    success = await agent_manager.delete_agent(agent_id)
    
    if success:
        ActivityLogRepository.log('info', f"Deleted agent", agent_id=agent_id)
        return {"success": True}
    else:
        raise HTTPException(status_code=404, detail="Agent not found")


@router.get("/{agent_id}/open-positions")
async def get_agent_open_positions(agent_id: str):
    """
    Get open positions for a specific agent
    """
    agent = AgentRepository.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Try to get live positions from exchange
    exchange = exchange_manager.get_exchange(agent['exchange_id'])
    if exchange:
        try:
            if hasattr(exchange, 'fetch_positions'):
                symbols = agent.get('symbols') if agent.get('symbols') else []
                live_positions = await exchange.fetch_positions(symbols)
                if live_positions:
                    # Filter open positions (non-zero contracts)
                    open_positions = [
                        {
                            'symbol': p.get('symbol', ''),
                            'side': p.get('side', 'long'),
                            'size': float(p.get('contracts', 0)),
                            'entryPrice': float(p.get('percentage', 0)),  # Entry price
                            'currentPrice': float(p.get('markPrice', 0)) if p.get('markPrice') else 0,
                            'leverage': int(p.get('leverage', 1)) if p.get('leverage') else exchange.config.get('defaultLeverage', 1),
                            'unrealizedPnl': float(p.get('unrealizedPnl', 0)) if p.get('unrealizedPnl') else 0,
                            'unrealizedPnlPercent': float(p.get('percentage', 0)) if p.get('percentage') else 0,
                            'liquidationPrice': float(p.get('liquidationPrice', 0)) if p.get('liquidationPrice') else 0,
                            'margin': float(p.get('collateral', 0)) if p.get('collateral') else 0,
                            'timestamp': datetime.now().isoformat()
                        }
                        for p in live_positions 
                        if float(p.get('contracts', 0)) != 0
                    ]
                    return {'positions': open_positions}
        except Exception as e:
            logger.error(f"Error fetching live open positions: {e}")
    
    # Fallback to database positions
    db_positions = PositionRepository.get_open_by_agent(agent_id)
    formatted_positions = [
        {
            'symbol': p.get('symbol', ''),
            'side': p.get('side', 'long'),
            'size': float(p.get('size', 0)),
            'entryPrice': float(p.get('entry_price', 0)),
            'currentPrice': float(p.get('current_price', 0)),
            'leverage': int(p.get('leverage', 1)) if p.get('leverage') else exchange.config.get('defaultLeverage', 1),
            'unrealizedPnl': float(p.get('unrealized_pnl', 0)),
            'unrealizedPnlPercent': float(p.get('unrealized_pnl_percent', 0)),
            'liquidationPrice': float(p.get('liquidation_price', 0)),
            'margin': float(p.get('margin', 0)),
            'timestamp': p.get('timestamp', datetime.now().isoformat())
        }
        for p in db_positions
    ]
    return {'positions': formatted_positions}


@router.get("/{agent_id}/balance")
async def get_agent_balance(agent_id: str):
    """
    Get account balance information for specified Agent
    """
    try:
        agent = AgentRepository.get_by_id(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
        
        exchange = exchange_manager.get_exchange(agent['exchange_id'])
        if not exchange:
            logger.warning(f"Exchange {agent['exchange_id']} not connected for agent {agent_id}")
            raise HTTPException(
                status_code=503,
                detail=f"Exchange {agent['exchange_id']} is not connected"
            )
        
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
        
        # Parse balance data
        total = balance.get('total', {})
        free = balance.get('free', {})
        
        # Prefer USDT, fallback to other stablecoins
        usdt_total = total.get('USDT', 0)
        usdt_free = free.get('USDT', 0)
        
        if not usdt_total and not usdt_free:
            for currency in ['USDC', 'BUSD', 'DAI', 'FDUSD']:
                if currency in total or currency in free:
                    usdt_total = total.get(currency, 0)
                    usdt_free = free.get(currency, 0)
                    break
        
        balance_data = {
            'total_balance': round(float(usdt_total), 8),
            'available_balance': round(float(usdt_free), 8),
            'unrealized_pnl': 0.0,
            'realized_pnl': 0.0,
            'timestamp': datetime.now().isoformat()
        }
        
        # Record balance history
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


@router.get("/{agent_id}/orders")
async def get_agent_orders(agent_id: str, limit: int = 50):
    return OrderRepository.get_by_agent(agent_id, limit)


@router.get("/{agent_id}/profit-history")
async def get_agent_profit_history(agent_id: str, days: int = 30):
    return BalanceHistoryRepository.get_history(agent_id, days)


@router.get("/{agent_id}/logs")
async def get_agent_logs(agent_id: str, limit: int = 100):
    return ActivityLogRepository.get_recent(limit, agent_id)


@router.get("/{agent_id}/ticker/{symbol:path}")
async def get_agent_ticker(agent_id: str, symbol: str):
    """
    Get ticker data for a specific symbol using the agent's exchange
    Symbol should be in format like BTC/USDT or BTC-USDT (will be converted to BTC/USDT)
    """
    agent = AgentRepository.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    exchange = exchange_manager.get_exchange(agent['exchange_id'])
    if not exchange:
        raise HTTPException(status_code=404, detail="Exchange not connected")
    
    # Convert symbol format: BTC-USDT -> BTC/USDT
    if '-' in symbol and '/' not in symbol:
        symbol = symbol.replace('-', '/')
    
    try:
        ticker = await exchange.fetch_ticker(symbol)
        return ticker
    except Exception as e:
        logger.error(f"Error fetching ticker for {symbol}: {e}")
        raise HTTPException(status_code=404, detail="Ticker not available")


@router.get("/{agent_id}/klines/{symbol:path}/{timeframe}")
async def get_agent_klines(agent_id: str, symbol: str, timeframe: str, limit: int = 100):
    """
    Get klines (OHLCV) for the agent's exchange. Accepts optional `symbol` query param
    If `symbol` omitted, use the agent's configured primary symbol.
    """
    agent = AgentRepository.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    exchange = exchange_manager.get_exchange(agent['exchange_id'])
    if not exchange:
        raise HTTPException(status_code=404, detail="Exchange not connected")

    use_symbol = symbol
    if not use_symbol:
        raise HTTPException(status_code=400, detail="No symbol specified for klines")

    # Normalize symbol passed with - as separator (keep / in symbol if present)
    if '-' in use_symbol and '/' not in use_symbol:
        use_symbol = use_symbol.replace('-', '/')

    try:
        klines = await exchange.fetch_ohlcv(use_symbol, timeframe, limit=limit)
        return klines
    except Exception as e:
        logger.error(f"Error fetching klines for agent {agent_id}: {e}")
        return []
