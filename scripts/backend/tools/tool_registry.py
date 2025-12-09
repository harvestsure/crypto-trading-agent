"""
工具（Tool）注册和管理系统
"""

import json
import logging
import inspect
from typing import Optional, Dict, Any, List, Callable, Awaitable
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


class ToolStatus(str, Enum):
    """工具执行状态"""
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    type: str  # "string", "number", "integer", "boolean", "object", "array"
    description: str
    required: bool = True
    enum: Optional[List[str]] = None
    default: Optional[Any] = None
    properties: Optional[Dict[str, 'ToolParameter']] = None  # for object type
    items: Optional['ToolParameter'] = None  # for array type


@dataclass
class ToolDefinition:
    """工具定义"""
    name: str
    description: str
    parameters: List[ToolParameter]
    category: str = "general"
    timeout: int = 30  # 超时时间（秒）
    
    def to_openai_format(self) -> Dict[str, Any]:
        """转换为 OpenAI Function Calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        param.name: {
                            "type": param.type,
                            "description": param.description,
                            **({"enum": param.enum} if param.enum else {}),
                            **({"default": param.default} if param.default else {}),
                        }
                        for param in self.parameters
                    },
                    "required": [p.name for p in self.parameters if p.required]
                }
            }
        }


class BaseTool(ABC):
    """工具基类"""
    
    def __init__(self, definition: ToolDefinition):
        self.definition = definition
        self.execution_count = 0
        self.success_count = 0
        self.failed_count = 0
        self.total_execution_time = 0.0
    
    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """
        执行工具
        
        返回: 工具执行结果（JSON 字符串格式）
        """
        pass
    
    async def call(self, **kwargs) -> Dict[str, Any]:
        """调用工具（包含执行跟踪）"""
        import time
        
        self.execution_count += 1
        start_time = time.time()
        
        try:
            result = await self.execute(**kwargs)
            self.success_count += 1
            
            return {
                "status": ToolStatus.SUCCESS.value,
                "result": result,
                "execution_time": time.time() - start_time,
            }
        except Exception as e:
            self.failed_count += 1
            logger.error(f"Tool {self.definition.name} execution failed: {str(e)}")
            
            return {
                "status": ToolStatus.FAILED.value,
                "error": str(e),
                "execution_time": time.time() - start_time,
            }
        finally:
            self.total_execution_time += time.time() - start_time
    
    def get_stats(self) -> Dict[str, Any]:
        """获取工具统计"""
        avg_time = (
            self.total_execution_time / self.execution_count
            if self.execution_count > 0
            else 0
        )
        
        return {
            "name": self.definition.name,
            "execution_count": self.execution_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "average_execution_time": avg_time,
            "total_execution_time": self.total_execution_time,
        }


class ToolRegistry:
    """工具注册表"""
    
    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
        self.definitions: Dict[str, ToolDefinition] = {}
    
    def register(self, tool: BaseTool):
        """注册工具"""
        self.tools[tool.definition.name] = tool
        self.definitions[tool.definition.name] = tool.definition
        logger.info(f"Tool registered: {tool.definition.name}")
    
    def unregister(self, tool_name: str):
        """注销工具"""
        if tool_name in self.tools:
            del self.tools[tool_name]
        if tool_name in self.definitions:
            del self.definitions[tool_name]
        logger.info(f"Tool unregistered: {tool_name}")
    
    def get(self, tool_name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self.tools.get(tool_name)
    
    def get_definition(self, tool_name: str) -> Optional[ToolDefinition]:
        """获取工具定义"""
        return self.definitions.get(tool_name)
    
    def list_all(self) -> List[str]:
        """列出所有工具"""
        return list(self.tools.keys())
    
    def list_by_category(self, category: str) -> List[str]:
        """按类别列出工具"""
        return [
            name for name, tool in self.tools.items()
            if tool.definition.category == category
        ]
    
    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """获取 OpenAI Function Calling 格式的工具定义"""
        return [
            definition.to_openai_format()
            for definition in self.definitions.values()
        ]
    
    async def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """调用工具"""
        tool = self.get(tool_name)
        if not tool:
            return {
                "status": ToolStatus.FAILED.value,
                "error": f"Tool not found: {tool_name}"
            }
        
        return await tool.call(**kwargs)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取所有工具的统计"""
        return {
            "total_tools": len(self.tools),
            "tools": [tool.get_stats() for tool in self.tools.values()]
        }


class ToolExecutor:
    """工具执行器（处理工具调用结果）"""
    
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
    
    async def execute_tool_call(
        self,
        tool_name: str,
        tool_call_id: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        执行工具调用
        
        返回:
        {
            "tool_call_id": "call_xxx",
            "tool_name": "xxx",
            "status": "success" | "failed",
            "result": "...",
            "error": "...",  # 如果失败
        }
        """
        logger.info(f"Executing tool call: {tool_name} (id: {tool_call_id})")
        logger.debug(f"Arguments: {arguments}")
        
        result = await self.registry.call_tool(tool_name, **arguments)
        
        return {
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "status": result["status"],
            "result": result.get("result"),
            "error": result.get("error"),
            "execution_time": result.get("execution_time"),
        }
    
    async def execute_multiple_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],  # [{"id": "...", "function": {"name": "...", "arguments": {...}}}]
    ) -> List[Dict[str, Any]]:
        """执行多个工具调用"""
        results = []
        
        for tool_call in tool_calls:
            tool_call_id = tool_call["id"]
            tool_name = tool_call["function"]["name"]
            arguments = json.loads(tool_call["function"]["arguments"])
            
            result = await self.execute_tool_call(tool_name, tool_call_id, arguments)
            results.append(result)
        
        return results
    
    def format_tool_result_for_llm(self, execution_result: Dict[str, Any]) -> str:
        """格式化工具结果供 LLM 使用"""
        if execution_result["status"] == "success":
            return execution_result["result"]
        else:
            return f"Error: {execution_result['error']}"
