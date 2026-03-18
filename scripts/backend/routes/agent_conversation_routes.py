"""
Agent 对话 API
处理 Agent 与 LLM 的交互、对话历史等
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from agent_manager import AgentManager
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Request
from pydantic import BaseModel

from database import (
    AgentRepository,
    ConversationRepository,
    ToolCallRepository,
    SignalRepository
)

logger = logging.getLogger(__name__)

# 辅助函数：从 Request 中获取 agent_manager
def get_agent_manager_from_request(request: Request)->AgentManager:
    """从 FastAPI request 中获取 agent_manager"""
    agent_manager = getattr(request.app.state, 'agent_manager', None)
    if not agent_manager:
        raise HTTPException(status_code=500, detail="Agent manager not initialized")
    return agent_manager


# ============== Pydantic Models ==============

class ConversationQuery(BaseModel):
    """对话查询请求"""
    agent_id: str
    limit: int = 50


class SignalQuery(BaseModel):
    """信号查询请求"""
    agent_id: str
    limit: int = 50


class TriggerDecisionRequest(BaseModel):
    """手动触发决策请求"""
    agent_id: str
    prompt: Optional[str] = None


# ============== Router ==============

router = APIRouter(prefix="/api/agents", tags=["agents"])


# ============== Conversation API ==============

@router.get("/{agent_id}/conversations")
async def get_agent_conversations(agent_id: str, limit: int = 100):
    """获取Agent的对话历史"""
    agent = AgentRepository.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    try:
        conversations = ConversationRepository.get_by_agent(agent_id, limit)
        
        # Format output with camelCase fields for frontend compatibility
        formatted = []
        for conv in conversations:
            tool_call_raw = conv.get('tool_call')
            tool_call = None
            if tool_call_raw:
                tool_call = {
                    "id": tool_call_raw.get('id', ''),
                    "name": tool_call_raw.get('name', tool_call_raw.get('tool_name', '')),
                    "arguments": tool_call_raw.get('arguments', {}),
                    "result": tool_call_raw.get('result'),
                    "status": tool_call_raw.get('status', 'success'),
                }
            formatted.append({
                "id": conv.get('id'),
                "role": conv.get('role'),
                "content": conv.get('content'),
                "timestamp": conv.get('created_at'),
                "toolCall": tool_call,
            })
        
        return {
            "agent_id": agent_id,
            "conversations": formatted,
            "count": len(formatted)
        }
    except Exception as e:
        logger.error(f"Error getting conversations for agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/tool-calls")
async def get_agent_tool_calls(agent_id: str, limit: int = 50):
    """获取Agent的工具调用记录"""
    agent = AgentRepository.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    try:
        tool_calls = ToolCallRepository.get_by_agent(agent_id, limit)
        
        # Format with camelCase for frontend compatibility
        formatted = []
        for tc in tool_calls:
            formatted.append({
                "id": tc.get('id'),
                "agentId": tc.get('agent_id'),
                "name": tc.get('name'),
                "arguments": tc.get('arguments'),
                "result": tc.get('result'),
                "status": tc.get('status'),
                "timestamp": tc.get('created_at'),
            })
        
        return {
            "agent_id": agent_id,
            "toolCalls": formatted,
            "count": len(formatted)
        }
    except Exception as e:
        logger.error(f"Error getting tool calls for agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/signals")
async def get_agent_signals(agent_id: str, limit: int = 50):
    """获取Agent的交易信号历史"""
    agent = AgentRepository.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    try:
        signals = SignalRepository.get_by_agent(agent_id, limit)
        
        # 格式化输出
        formatted = []
        for signal in signals:
            formatted.append({
                "id": signal.get('id'),
                "agent_id": signal.get('agent_id'),
                "symbol": signal.get('symbol'),
                "action": signal.get('action'),  # LONG, SHORT, CLOSE, HOLD
                "confidence": signal.get('confidence'),  # 0-1
                "reason": signal.get('reason'),
                "recommended_entry": signal.get('recommended_entry'),
                "recommended_exit": signal.get('recommended_exit'),
                "risk_level": signal.get('risk_level'),
                "timestamp": signal.get('created_at'),
            })
        
        return {
            "agent_id": agent_id,
            "signals": formatted,
            "count": len(formatted)
        }
    except Exception as e:
        logger.error(f"Error getting signals for agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}/decision")
async def trigger_manual_decision(agent_id: str, request: TriggerDecisionRequest, http_request: Request):
    """手动触发Agent的决策（用于测试）"""
    if not request.agent_id == agent_id:
        raise HTTPException(status_code=400, detail="Agent ID mismatch")
    
    agent_manager = get_agent_manager_from_request(http_request)
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found or not initialized")
    
    try:
        logger.info(f"Manual decision triggered for agent {agent_id}")
        
        # 触发决策（在后台异步执行）
        asyncio.create_task(agent._make_decision())
        
        return {
            "success": True,
            "message": "Decision triggered",
            "agent_id": agent_id,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error triggering decision for agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== WebSocket API ==============

class ConnectionManager:
    """WebSocket连接管理器"""
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, agent_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[agent_id] = websocket
        logger.info(f"WebSocket connected for agent {agent_id}")
    
    def disconnect(self, agent_id: str):
        if agent_id in self.active_connections:
            del self.active_connections[agent_id]
            logger.info(f"WebSocket disconnected for agent {agent_id}")
    
    async def broadcast_to_agent(self, agent_id: str, message: Dict[str, Any]):
        """广播消息到Agent的所有连接"""
        if agent_id in self.active_connections:
            try:
                await self.active_connections[agent_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to agent {agent_id}: {e}")
                self.disconnect(agent_id)


agent_ws_manager = ConnectionManager()


@router.websocket("/ws/{agent_id}/stream")
async def websocket_agent_stream(websocket: WebSocket, agent_id: str):
    """
    WebSocket 实时流
    
    消息类型:
    - conversation: 对话消息
    - indicator: 技术指标更新
    - position: 持仓更新
    - balance: 余额更新
    - signal: 交易信号
    - order: 订单更新
    - error: 错误消息
    """
    await agent_ws_manager.connect(agent_id, websocket)
    
    try:
        while True:
            # 接收客户端消息（用于心跳或控制命令）
            data = await websocket.receive_json()
            
            if data.get("type") == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })
            elif data.get("type") == "subscribe":
                # 订阅特定的数据类型
                logger.info(f"Agent {agent_id} subscribed to {data.get('channel')}")
            
    except WebSocketDisconnect:
        agent_ws_manager.disconnect(agent_id)
        logger.info(f"Agent {agent_id} WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for agent {agent_id}: {e}")
        agent_ws_manager.disconnect(agent_id)


# ============== Agent Status API ==============

@router.get("/{agent_id}/status")
async def get_agent_status(agent_id: str, request: Request):
    """获取Agent的实时状态"""
    agent_manager = get_agent_manager_from_request(request)
    
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        # 尝试从数据库获取
        db_agent = AgentRepository.get_by_id(agent_id)
        if not db_agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return {
            "id": agent_id,
            "status": db_agent.get('status'),
            "is_running": False,
            "message": "Agent not initialized"
        }
    
    return agent_manager.get_agent_status(agent_id)


@router.get("/{agent_id}/market-info")
async def get_agent_market_info(agent_id: str, request: Request):
    """获取Agent当前的市场信息"""
    agent_manager = get_agent_manager_from_request(request)
    
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not initialized")
    
    try:
        return {
            "agent_id": agent_id,
            "symbol": agent.symbol,
            "timeframe": agent.timeframe,
            "current_price": agent.current_ticker.get('last') if agent.current_ticker else None,
            "bid": agent.current_ticker.get('bid') if agent.current_ticker else None,
            "ask": agent.current_ticker.get('ask') if agent.current_ticker else None,
            "high_24h": agent.current_ticker.get('high') if agent.current_ticker else None,
            "low_24h": agent.current_ticker.get('low') if agent.current_ticker else None,
            "volume_24h": agent.current_ticker.get('volume') if agent.current_ticker else None,
            "change_percent_24h": agent.current_ticker.get('percentage') if agent.current_ticker else None,
            "klines_count": len(agent.klines_history),
            "indicators": agent._calculate_indicators(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting market info for agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}/indicators")
async def get_agent_indicators(agent_id: str, request: Request):
    """获取Agent的技术指标"""
    agent_manager = get_agent_manager_from_request(request)
    
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not initialized")
    
    try:
        indicators = agent._calculate_indicators()
        
        return {
            "agent_id": agent_id,
            "symbol": agent.symbol,
            "timeframe": agent.timeframe,
            "indicators": indicators,
            "klines_count": len(agent.klines_history),
            "last_kline_time": agent.klines_history[-1][0] if agent.klines_history else None,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting indicators for agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
