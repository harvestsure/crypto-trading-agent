"""
LLM 模型包装类
处理 OpenAI 接口、Token计算、Cost追踪
"""

import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from openai import OpenAI, AsyncOpenAI
import tiktoken

logger = logging.getLogger(__name__)


class TokenCounter:
    """Token 计算工具"""
    
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # 如果模型不在 tiktoken 中，使用 cl100k_base
            self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def count_tokens(self, text: str) -> int:
        """计算文本的 token 数"""
        return len(self.encoding.encode(text))
    
    def count_messages_tokens(self, messages: List[Dict[str, str]]) -> int:
        """计算消息列表的 token 数（包括系统开销）"""
        total = 0
        for message in messages:
            # 每条消息固定 4 token 开销
            total += 4
            for key, value in message.items():
                if isinstance(value, str):
                    total += self.count_tokens(value)
        # 加上对话结束的 token
        total += 2
        return total
    
    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        pricing: Optional[Dict[str, float]] = None
    ) -> Dict[str, float]:
        """
        估计成本
        
        pricing 格式: {"input": 0.003, "output": 0.006}  # per 1K tokens
        """
        if pricing is None:
            # 默认 gpt-4o-mini 价格
            pricing = {
                "gpt-4o-mini": {"input": 0.15 / 1000, "output": 0.6 / 1000},
                "gpt-4o": {"input": 2.5 / 1000, "output": 10 / 1000},
            }
            pricing = pricing.get(self.model, {"input": 0.0, "output": 0.0})
        
        input_cost = input_tokens * pricing["input"]
        output_cost = output_tokens * pricing["output"]
        
        return {
            "input_cost": round(input_cost, 6),
            "output_cost": round(output_cost, 6),
            "total_cost": round(input_cost + output_cost, 6),
        }


class ConversationHistory:
    """对话历史管理"""
    
    def __init__(self, model: str = "gpt-4o-mini", max_history: int = 20):
        self.model = model
        self.max_history = max_history
        self.messages: List[Dict[str, Any]] = []
        self.token_counter = TokenCounter(model)
        self.created_at = datetime.utcnow()
        self.total_tokens = 0
        self.total_cost = 0.0
    
    def add_system_message(self, content: str):
        """添加系统消息"""
        self.messages.append({
            "role": "system",
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.total_tokens += self.token_counter.count_tokens(content)
    
    def add_user_message(self, content: str):
        """添加用户消息"""
        self.messages.append({
            "role": "user",
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.total_tokens += self.token_counter.count_tokens(content)
    
    def add_assistant_message(self, content: str, tool_calls: Optional[List[Dict]] = None):
        """添加助手消息"""
        msg = {
            "role": "assistant",
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }
        if tool_calls:
            msg["tool_calls"] = tool_calls
        
        self.messages.append(msg)
        self.total_tokens += self.token_counter.count_tokens(content)
    
    def add_tool_result(self, tool_call_id: str, result: str):
        """添加工具执行结果"""
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result,
            "timestamp": datetime.utcnow().isoformat()
        })
        self.total_tokens += self.token_counter.count_tokens(result)
    
    def get_messages_for_api(self) -> List[Dict[str, Any]]:
        """获取用于 API 调用的消息格式（不包括时间戳）"""
        return [
            {k: v for k, v in msg.items() if k != "timestamp"}
            for msg in self.messages
        ]
    
    def trim_history(self):
        """保持历史在指定大小内（保留最近的 max_history 条消息）"""
        if len(self.messages) > self.max_history:
            # 保留系统消息 + 最近的消息
            system_msgs = [m for m in self.messages if m["role"] == "system"]
            other_msgs = [m for m in self.messages if m["role"] != "system"]
            self.messages = system_msgs + other_msgs[-self.max_history:]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取对话统计"""
        return {
            "total_messages": len(self.messages),
            "total_tokens": self.total_tokens,
            "total_cost": round(self.total_cost, 6),
            "created_at": self.created_at.isoformat(),
            "duration_seconds": (datetime.utcnow() - self.created_at).total_seconds(),
        }


class LLMModel:
    """LLM 模型包装类 - 支持多个 LLM 提供商"""
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
        provider: str = "openai",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ):
        """
        初始化 LLM 模型
        
        Args:
            api_key: API Key
            model: 模型名称
            base_url: 自定义 API 端点（支持兼容 OpenAI 的服务，如 DeepSeek）
            provider: 提供商名称 ('openai', 'deepseek', 等)
            temperature: 温度参数
            max_tokens: 最大输出 token 数
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.provider = provider
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # 初始化同步和异步客户端
        client_kwargs = {
            "api_key": api_key,
        }
        if base_url:
            client_kwargs["base_url"] = base_url
        
        self.client = OpenAI(**client_kwargs)
        self.async_client = AsyncOpenAI(**client_kwargs)
        
        self.token_counter = TokenCounter(model)
        self.conversation = None
        
        # 记录配置信息
        logger.info(
            f"LLMModel initialized - Provider: {provider}, Model: {model}, "
            f"Base URL: {base_url or 'default'}"
        )
    
    def create_conversation(self, system_prompt: str) -> ConversationHistory:
        """创建新的对话"""
        self.conversation = ConversationHistory(self.model)
        self.conversation.add_system_message(system_prompt)
        return self.conversation
    
    def _build_request_params(self, tools: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """构建 API 请求参数"""
        params = {
            "model": self.model,
            "messages": self.conversation.get_messages_for_api(),
            "temperature": self.temperature,
        }
        
        if self.max_tokens:
            params["max_tokens"] = self.max_tokens
        
        if tools:
            params["tools"] = tools
        
        return params
    
    def chat_completion(
        self,
        user_message: str,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        同步对话调用
        
        返回格式:
        {
            "content": "消息内容",
            "tool_calls": [...],
            "input_tokens": 123,
            "output_tokens": 45,
            "cost": 0.000123
        }
        """
        if not self.conversation:
            raise ValueError("未初始化对话，请先调用 create_conversation")
        
        # 添加用户消息
        self.conversation.add_user_message(user_message)
        
        # 构建请求
        params = self._build_request_params(tools)
        if tool_choice:
            params["tool_choice"] = tool_choice
        
        # 调用 API
        response = self.client.chat.completions.create(**params)
        
        # 解析响应
        assistant_message = response.choices[0].message
        
        # 计算 token 和成本
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        cost_info = self.token_counter.estimate_cost(input_tokens, output_tokens)
        
        self.conversation.total_cost += cost_info["total_cost"]
        
        # 添加助手消息
        tool_calls = None
        if assistant_message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                }
                for tc in assistant_message.tool_calls
            ]
        
        content = assistant_message.content or ""
        self.conversation.add_assistant_message(content, tool_calls)
        
        result = {
            "content": content,
            "tool_calls": tool_calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost": cost_info,
        }
        
        logger.info(f"LLM Response - Tokens: {input_tokens + output_tokens}, Cost: ${cost_info['total_cost']:.6f}")
        
        return result
    
    async def chat_completion_async(
        self,
        user_message: str,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
    ) -> Dict[str, Any]:
        """异步对话调用"""
        if not self.conversation:
            raise ValueError("未初始化对话，请先调用 create_conversation")
        
        # 添加用户消息
        self.conversation.add_user_message(user_message)
        
        # 构建请求
        params = self._build_request_params(tools)
        if tool_choice:
            params["tool_choice"] = tool_choice
        
        # 调用 API
        response = await self.async_client.chat.completions.create(**params)
        
        # 解析响应
        assistant_message = response.choices[0].message
        
        # 计算 token 和成本
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        cost_info = self.token_counter.estimate_cost(input_tokens, output_tokens)
        
        self.conversation.total_cost += cost_info["total_cost"]
        
        # 添加助手消息
        tool_calls = None
        if assistant_message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                }
                for tc in assistant_message.tool_calls
            ]
        
        content = assistant_message.content or ""
        self.conversation.add_assistant_message(content, tool_calls)
        
        result = {
            "content": content,
            "tool_calls": tool_calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost": cost_info,
        }
        
        logger.info(f"LLM Response - Tokens: {input_tokens + output_tokens}, Cost: ${cost_info['total_cost']:.6f}")
        
        return result
    
    def add_tool_result(self, tool_call_id: str, result: str) -> str:
        """添加工具结果到对话"""
        self.conversation.add_tool_result(tool_call_id, result)
        logger.info(f"Tool result added for call {tool_call_id}")
        return tool_call_id
    
    def get_conversation_stats(self) -> Dict[str, Any]:
        """获取对话统计"""
        if not self.conversation:
            return {}
        return self.conversation.get_stats()
    
    def reset_conversation(self, system_prompt: str):
        """重置对话"""
        self.conversation = ConversationHistory(self.model)
        self.conversation.add_system_message(system_prompt)
        logger.info("Conversation reset")
    
    def export_conversation(self) -> Dict[str, Any]:
        """导出对话记录"""
        if not self.conversation:
            return {}
        
        return {
            "model": self.model,
            "messages": self.conversation.get_messages_for_api(),
            "stats": self.conversation.get_stats(),
        }
    
    def get_config_info(self) -> Dict[str, Any]:
        """获取当前模型配置信息（用于调试）"""
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url or "default",
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
