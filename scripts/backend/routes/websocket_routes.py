"""
WebSocket endpoint
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from logger_config import get_logger

router = APIRouter(tags=["websocket"])
logger = get_logger(__name__)

# This will be injected from the app
connection_manager = None


def set_connection_manager(cm):
    """Inject connection manager dependency"""
    global connection_manager
    connection_manager = cm


@router.websocket("/ws/{client_id}")
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
