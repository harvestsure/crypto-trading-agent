"""
Agent 基类和管理器
"""

import json
import asyncio
import logging
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
from uuid import uuid4

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """Agent 状态"""
    IDLE = "idle"
    RUNNING = "running"
    THINKING = "thinking"
    EXECUTING_TOOL = "executing_tool"
    ERROR = "error"
    PAUSED = "paused"


class ToolCall(BaseModel):
    """工具调用记录"""
    id: str
    name: str
    arguments: Dict[str, Any]
    result: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    timestamp: datetime


class AgentMessage(BaseModel):
    """Agent 消息"""
    role: str  # "user", "assistant", "system"
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    timestamp: datetime


class AgentState(BaseModel):
    """Agent 状态快照"""
    agent_id: str
    status: AgentStatus
    current_task: Optional[str] = None
    last_update: datetime
    error_message: Optional[str] = None


class BaseAgent(ABC):
    """Agent 基类"""
    
    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id
        self.name = name
        self.status = AgentStatus.IDLE
        self.current_task: Optional[str] = None
        self.error_message: Optional[str] = None
        self.created_at = datetime.utcnow()
        self.last_update = datetime.utcnow()
        
        self.messages: List[AgentMessage] = []
        self.tool_calls: List[ToolCall] = []
        
        # 回调钩子
        self.on_status_change: Optional[Callable[[AgentStatus], None]] = None
        self.on_tool_call: Optional[Callable[[ToolCall], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
    
    async def initialize(self):
        """初始化 Agent"""
        await self._on_initialize()
        logger.info(f"Agent {self.name} initialized")
    
    async def cleanup(self):
        """清理资源"""
        await self._on_cleanup()
        logger.info(f"Agent {self.name} cleaned up")
    
    def add_message(self, role: str, content: str, tool_calls: Optional[List] = None):
        """添加消息到历史"""
        msg = AgentMessage(
            role=role,
            content=content,
            tool_calls=tool_calls,
            timestamp=datetime.utcnow()
        )
        self.messages.append(msg)
    
    def record_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Optional[str] = None,
        error: Optional[str] = None,
        duration_ms: Optional[float] = None,
    ) -> ToolCall:
        """记录工具调用"""
        tool_call = ToolCall(
            id=str(uuid4()),
            name=tool_name,
            arguments=arguments,
            result=result,
            error=error,
            duration_ms=duration_ms,
            timestamp=datetime.utcnow()
        )
        self.tool_calls.append(tool_call)
        
        if self.on_tool_call:
            self.on_tool_call(tool_call)
        
        logger.info(f"Tool call recorded: {tool_name}")
        return tool_call
    
    def set_status(self, status: AgentStatus, current_task: Optional[str] = None):
        """设置 Agent 状态"""
        self.status = status
        self.current_task = current_task
        self.last_update = datetime.utcnow()
        
        if self.on_status_change:
            self.on_status_change(status)
        
        logger.info(f"Agent {self.name} status: {status.value}")
    
    def set_error(self, error_message: str):
        """设置错误状态"""
        self.error_message = error_message
        self.set_status(AgentStatus.ERROR)
        
        if self.on_error:
            self.on_error(error_message)
        
        logger.error(f"Agent {self.name} error: {error_message}")
    
    def get_state(self) -> AgentState:
        """获取当前状态快照"""
        return AgentState(
            agent_id=self.agent_id,
            status=self.status,
            current_task=self.current_task,
            last_update=self.last_update,
            error_message=self.error_message,
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "last_update": self.last_update.isoformat(),
            "total_messages": len(self.messages),
            "total_tool_calls": len(self.tool_calls),
            "successful_tool_calls": len([tc for tc in self.tool_calls if tc.error is None]),
            "failed_tool_calls": len([tc for tc in self.tool_calls if tc.error is not None]),
        }
    
    @abstractmethod
    async def execute(self, task: str, context: Optional[Dict[str, Any]] = None):
        """执行任务（由子类实现）"""
        pass
    
    @abstractmethod
    async def _on_initialize(self):
        """初始化钩子（由子类实现）"""
        pass
    
    @abstractmethod
    async def _on_cleanup(self):
        """清理钩子（由子类实现）"""
        pass


class AgentManager:
    """Agent 管理器"""
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
    
    def register(self, agent: BaseAgent):
        """注册 Agent"""
        self.agents[agent.agent_id] = agent
        logger.info(f"Agent {agent.name} registered")
    
    def unregister(self, agent_id: str):
        """注销 Agent"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            logger.info(f"Agent {agent_id} unregistered")
    
    def get(self, agent_id: str) -> Optional[BaseAgent]:
        """获取 Agent"""
        return self.agents.get(agent_id)
    
    def list_all(self) -> List[BaseAgent]:
        """列出所有 Agent"""
        return list(self.agents.values())
    
    def get_stats(self) -> Dict[str, Any]:
        """获取所有 Agent 的统计"""
        return {
            "total_agents": len(self.agents),
            "agents": [agent.get_stats() for agent in self.agents.values()]
        }
    
    async def initialize_all(self):
        """初始化所有 Agent"""
        for agent in self.agents.values():
            await agent.initialize()
    
    async def cleanup_all(self):
        """清理所有 Agent"""
        for agent in self.agents.values():
            await agent.cleanup()
