"""
交易 Agent 实现
基于 openai-agents 库，集成 LLM 模型、工具管理和状态跟踪
"""

import json
import asyncio
import logging
import time
from typing import Optional, Dict, Any, List
from datetime import datetime

from agents import Agent, Runner, function_tool, RunContextWrapper

from models.llm_model import LLMModel
from agents.base_agent import BaseAgent, AgentStatus
from tools.tool_registry import ToolRegistry, ToolExecutor

logger = logging.getLogger(__name__)


class TradingAgent(BaseAgent):
    """交易 Agent"""
    
    def __init__(
        self,
        agent_id: str,
        name: str,
        llm_model: LLMModel,
        tool_registry: ToolRegistry,
        system_prompt: str,
    ):
        super().__init__(agent_id, name)
        
        self.llm_model = llm_model
        self.tool_registry = tool_registry
        self.tool_executor = ToolExecutor(tool_registry)
        self.system_prompt = system_prompt
        
        # openai-agents SDK Agent
        self.openai_agent: Optional[Agent] = None
        self.runner: Optional[Runner] = None
        
        # 执行上下文
        self.context: Optional[Dict[str, Any]] = None
        
        # 成本追踪
        self.total_cost = 0.0
    
    async def _on_initialize(self):
        """初始化 Agent"""
        # 初始化对话
        self.llm_model.create_conversation(self.system_prompt)
        
        # 创建 openai-agents Agent
        self._create_openai_agent()
        
        logger.info(f"Trading Agent {self.name} initialized")
    
    async def _on_cleanup(self):
        """清理资源"""
        logger.info(f"Trading Agent {self.name} cleaning up")
    
    def _create_openai_agent(self):
        """创建 OpenAI Agents SDK Agent"""
        # 这里会在 execute 方法中动态创建，因为需要上下文信息
        pass
    
    async def execute(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        执行交易任务
        
        Args:
            task: 任务描述，如 "分析 BTC/USDT 的市场信号"
            context: 执行上下文，如交易所信息、账户信息等
        """
        self.context = context or {}
        self.set_status(AgentStatus.THINKING, task)
        
        try:
            # 调用 LLM 进行思考和规划
            await self._think_and_plan(task)
            
            # 执行规划的操作
            await self._execute_plan()
            
            self.set_status(AgentStatus.IDLE)
        except Exception as e:
            self.set_error(f"Task execution failed: {str(e)}")
            logger.exception("Exception in execute")
    
    async def _think_and_plan(self, task: str):
        """
        第一步：思考和规划
        调用 LLM 分析问题，决定需要调用哪些工具
        """
        self.set_status(AgentStatus.THINKING, task)
        self.add_message("user", task)
        
        # 获取工具定义
        tools_definitions = self.tool_registry.get_openai_tools()
        
        # 调用 LLM
        response = self.llm_model.chat_completion(
            user_message=task,
            tools=tools_definitions if tools_definitions else None,
        )
        
        # 记录成本
        self.total_cost += response["cost"]["total_cost"]
        
        # 添加 LLM 响应到消息历史
        self.add_message(
            "assistant",
            response["content"],
            tool_calls=response.get("tool_calls")
        )
        
        # 保存 tool calls 供下一步执行
        self.pending_tool_calls = response.get("tool_calls", [])
        
        logger.info(
            f"LLM response: {len(self.pending_tool_calls)} tool calls, "
            f"Cost: ${response['cost']['total_cost']:.6f}"
        )
    
    async def _execute_plan(self):
        """
        第二步：执行规划
        执行 LLM 决定的工具调用
        """
        if not self.pending_tool_calls:
            logger.info("No tool calls to execute")
            return
        
        self.set_status(AgentStatus.EXECUTING_TOOL)
        
        # 执行所有工具调用
        execution_results = await self.tool_executor.execute_multiple_tool_calls(
            self.pending_tool_calls
        )
        
        # 记录工具调用
        for result in execution_results:
            self.record_tool_call(
                tool_name=result["tool_name"],
                arguments={},  # TODO: 从 pending_tool_calls 中提取
                result=result.get("result"),
                error=result.get("error"),
                duration_ms=result.get("execution_time", 0) * 1000,
            )
        
        # 将工具结果反馈给 LLM
        for result in execution_results:
            formatted_result = self.tool_executor.format_tool_result_for_llm(result)
            self.llm_model.add_tool_result(result["tool_call_id"], formatted_result)
            self.add_message("tool", formatted_result)
        
        logger.info(f"Executed {len(execution_results)} tool calls")
        
        # 如果 LLM 需要进一步思考，继续对话
        # （可选：实现多轮对话）
    
    def get_agent_info(self) -> Dict[str, Any]:
        """获取 Agent 详细信息"""
        return {
            **self.get_stats(),
            "total_cost": self.total_cost,
            "conversation_stats": self.llm_model.get_conversation_stats(),
            "tool_stats": self.tool_registry.get_stats(),
        }
    
    def export_execution_log(self) -> Dict[str, Any]:
        """导出执行日志"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "total_cost": self.total_cost,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                }
                for msg in self.messages
            ],
            "tool_calls": [
                {
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments,
                    "result": tc.result,
                    "error": tc.error,
                    "duration_ms": tc.duration_ms,
                    "timestamp": tc.timestamp.isoformat(),
                }
                for tc in self.tool_calls
            ],
        }
