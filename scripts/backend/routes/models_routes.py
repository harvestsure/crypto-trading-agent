"""
AI Models API routes
"""

import uuid
from fastapi import APIRouter, HTTPException
from database import AIModelRepository, AgentRepository
from ai_model_config import get_or_set_base_url
from logger_config import get_logger
from common.models import AIModelConfig
from database import ActivityLogRepository

router = APIRouter(prefix="/api/models", tags=["models"])
logger = get_logger(__name__)


@router.get("")
async def get_models():
    models = AIModelRepository.get_all()
    # Mask API keys
    for model in models:
        model['api_key'] = '***' + model['api_key'][-4:] if model.get('api_key') else ''
    return models


@router.post("")
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


@router.delete("/{model_id}")
async def delete_model(model_id: str):
    # Check if model is used by agents
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


@router.get("/{model_id}/usage")
async def check_model_usage(model_id: str):
    """Check if model is used by agents"""
    agents = AgentRepository.get_by_model_id(model_id)
    return {
        "isUsed": len(agents) > 0,
        "agents": [{"id": a['id'], "name": a['name'], "status": a['status']} for a in agents]
    }


@router.put("/{model_id}")
async def update_model(model_id: str, data: dict):
    # Accepts partial updates (e.g., {"status": "inactive"})
    existing = AIModelRepository.get_by_id(model_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Model not found")

    updated = AIModelRepository.update(model_id, data)
    ActivityLogRepository.log('info', f"Updated AI model", details={'model_id': model_id, 'data': data})
    return updated


@router.post("/{model_id}/test-connection")
async def test_model_connection(model_id: str):
    """Test LLM model connection"""
    from models.llm_model import LLMModel
    
    model_config = AIModelRepository.get_by_id(model_id)
    if not model_config:
        raise HTTPException(status_code=404, detail="Model not found")
    
    try:
        # Create model instance
        llm_model = LLMModel(
            api_key=model_config['api_key'],
            model=model_config['model'],
            base_url=model_config.get('base_url'),
            provider=model_config.get('provider', 'openai'),
        )
        
        # Create conversation
        llm_model.create_conversation("You are a helpful assistant.")
        
        # Test API connection
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
