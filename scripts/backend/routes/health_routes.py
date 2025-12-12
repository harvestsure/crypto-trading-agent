"""
Health check and activity logs API routes
"""

from datetime import datetime
from fastapi import APIRouter
from database import ActivityLogRepository
from logger_config import get_logger

router = APIRouter(tags=["health", "activity"])
logger = get_logger(__name__)

# This will be injected from the app
agent_manager = None
connection_manager = None
exchange_manager = None


def set_managers(am, cm, em):
    """Inject managers dependency"""
    global agent_manager, connection_manager, exchange_manager
    agent_manager = am
    connection_manager = cm
    exchange_manager = em


@router.get("/health")
@router.get("/api/health")
async def health_check():
    running_count = len(agent_manager.get_all_agents()) if agent_manager else 0
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_connections": len(connection_manager.active_connections) if connection_manager else 0,
        "connected_exchanges": len(exchange_manager.exchanges) if exchange_manager else 0,
        "running_agents": running_count
    }


@router.get("/api/activity")
async def get_activity(limit: int = 100):
    return ActivityLogRepository.get_recent(limit)
