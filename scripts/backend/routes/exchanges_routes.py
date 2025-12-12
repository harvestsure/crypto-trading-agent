"""
Exchanges API routes
"""

import uuid
from fastapi import APIRouter, HTTPException
from database import ExchangeRepository, AgentRepository, ActivityLogRepository
from logger_config import get_logger
from common.models import ExchangeConfig

router = APIRouter(prefix="/api/exchanges", tags=["exchanges"])
logger = get_logger(__name__)

# These will be injected from the app
exchange_manager = None


def set_exchange_manager(em):
    """Inject exchange manager dependency"""
    global exchange_manager
    exchange_manager = em


@router.get("")
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


@router.get("/{exchange_id}/status")
async def get_exchange_status(exchange_id: str):
    """Get exchange connection status"""
    config = ExchangeRepository.get_by_id(exchange_id)
    if not config:
        raise HTTPException(status_code=404, detail="Exchange not found")
    
    ex = exchange_manager.get_exchange(exchange_id)
    is_connected = ex is not None
    
    return {
        'id': exchange_id,
        'name': config['name'],
        'exchange': config['exchange'],
        'connected': is_connected,
        'status': config.get('status', 'disconnected'),
        'testnet': config.get('testnet', False)
    }


@router.post("")
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
    
    # Save to database
    exchange_data = {
        'id': exchange_id,
        'name': config.name,
        'exchange': config.exchange,
        'api_keys': api_keys,
        'testnet': config.testnet,
        'status': 'disconnected'
    }
    result = ExchangeRepository.create(exchange_data)
    
    # Add to ExchangeManager dynamically
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


@router.put("/{exchange_id}")
async def update_exchange(exchange_id: str, config: ExchangeConfig):
    """Update exchange configuration"""
    existing = ExchangeRepository.get_by_id(exchange_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Exchange not found")
    
    # Normalize api_keys
    if config.api_keys:
        api_keys = config.api_keys
    else:
        api_keys = {
            'api_key': config.api_key or '',
            'secret': config.secret or '',
            'passphrase': config.passphrase or ''
        }
    
    api_keys = {k: v for k, v in api_keys.items() if v}
    
    # Update database
    update_data = {
        'name': config.name,
        'exchange': config.exchange,
        'api_keys': api_keys,
        'testnet': config.testnet,
        'status': 'disconnected'
    }
    result = ExchangeRepository.update(exchange_id, update_data)
    
    # Update ExchangeManager
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


@router.post("/{exchange_id}/connect")
async def connect_exchange(exchange_id: str):
    """Connect to exchange"""
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


@router.post("/{exchange_id}/disconnect")
async def disconnect_exchange(exchange_id: str):
    """Disconnect from exchange"""
    success = await exchange_manager.remove_exchange(exchange_id)
    
    if success:
        ExchangeRepository.update(exchange_id, {'status': 'disconnected'})
        ActivityLogRepository.log('info', f"Disconnected from exchange", details={'exchange_id': exchange_id})
        return {"success": True, "status": "disconnected"}
    
    raise HTTPException(status_code=500, detail="Failed to disconnect")


@router.delete("/{exchange_id}")
async def delete_exchange(exchange_id: str):
    """Delete exchange"""
    # Check if exchange is used by agents
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


@router.get("/{exchange_id}/usage")
async def check_exchange_usage(exchange_id: str):
    """Check if exchange is used by agents"""
    agents = AgentRepository.get_by_exchange_id(exchange_id)
    return {
        "isUsed": len(agents) > 0,
        "agents": [{"id": a['id'], "name": a['name'], "status": a['status']} for a in agents]
    }
