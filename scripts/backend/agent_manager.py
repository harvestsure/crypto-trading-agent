"""
Agent 管理器
负责创建、启动、停止和管理所有交易 Agent
"""

import asyncio
import logging
from typing import Dict, Optional, Any
from datetime import datetime

from agents.smart_trading_agent import SmartTradingAgent
from models.llm_model import LLMModel
from common.data_types import DataEvent, DataEventType
from tools.tool_registry import ToolRegistry
from tools.trading_tools import create_trading_tools
from exchanges.common_exchange import CommonExchange
from exchange_manager import ExchangeManager
from database import AIModelRepository, AgentRepository

logger = logging.getLogger(__name__)


class AgentManager:
    """
    Agent 管理器
    
    负责:
    1. 创建和配置 Agent
    2. 启动和停止 Agent
    3. 管理 Agent 生命周期
    4. 提供 Agent 状态查询
    """
    
    def __init__(self, exchange_manager: ExchangeManager):
        self.exchange_manager = exchange_manager
        self.agents: Dict[str, SmartTradingAgent] = {}
        self.agent_tasks: Dict[str, asyncio.Task] = {}
        
        logger.info("AgentManager initialized")
    
    async def create_agent(
        self,
        agent_id: str,
        name: str,
        model_id: str,
        exchange_id: str,
        symbol: str,
        timeframe: str,
        indicators: list,
        prompt: str,
        config: Dict[str, Any] = None
    ) -> SmartTradingAgent:
        """
        创建新的 Agent
        
        Args:
            agent_id: Agent ID
            name: Agent 名称
            model_id: LLM 模型 ID
            exchange_id: 交易所 ID
            symbol: 交易对
            timeframe: 时间框架
            indicators: 技术指标列表
            prompt: 系统提示词
            config: 配置参数
        
        Returns:
            创建的 Agent 实例
        """
        try:
            # 1. 获取交易所实例
            exchange = self.exchange_manager.get_exchange(exchange_id)
            if not exchange:
                raise ValueError(f"Exchange {exchange_id} not found or not initialized")
            
            # 2. 获取 LLM 模型配置
            model_config = AIModelRepository.get_by_id(model_id)
            if not model_config:
                raise ValueError(f"Model {model_id} not found")
            
            # 3. 创建 LLM 模型实例
            llm_model = LLMModel(
                api_key=model_config['api_key'],
                model=model_config['model'],
                base_url=model_config.get('base_url'),
                provider=model_config.get('provider', 'openai'),
                temperature=0.7,
                agent_id=agent_id,
                agent_name=name,
                enable_cache=True,
            )
            
            # 4. 创建工具注册表
            tool_registry = ToolRegistry()
            
            # 5. 注册交易工具
            trading_tools = create_trading_tools(exchange, symbol)
            for tool in trading_tools:
                tool_registry.register(tool)
            
            logger.info(f"Registered {len(trading_tools)} trading tools for agent {name}")
            
            # 6. 创建 Agent
            agent = SmartTradingAgent(
                agent_id=agent_id,
                name=name,
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                indicators=indicators,
                llm_model=llm_model,
                tool_registry=tool_registry,
                system_prompt=prompt,
                config=config or {}
            )
            
            # 7. 保存到管理器
            self.agents[agent_id] = agent
            
            logger.info(f"✅ Agent {name} ({agent_id}) created successfully")
            return agent
            
        except Exception as e:
            logger.error(f"❌ Failed to create agent {name}: {e}", exc_info=True)
            raise
    
    async def start_agent(self, agent_id: str) -> bool:
        """
        启动或恢复 Agent
        
        Args:
            agent_id: Agent ID
        
        Returns:
            是否成功启动
        """
        try:
            agent = self.agents.get(agent_id)
            if not agent:
                logger.error(f"Agent {agent_id} not found")
                return False
            
            # 检查是否已经在运行
            if agent_id in self.agent_tasks and not self.agent_tasks[agent_id].done():
                # 如果是暂停状态，恢复运行
                from agents.base_agent import AgentStatus
                if agent.status == AgentStatus.PAUSED:
                    agent.set_status(AgentStatus.IDLE, "Agent resumed by user")
                    # 更新数据库状态
                    AgentRepository.update(agent_id, {'status': 'running'})
                    logger.info(f"✅ Agent {agent.name} ({agent_id}) resumed from pause")
                    return True
                else:
                    logger.warning(f"Agent {agent_id} is already running")
                    return True
            
            # 初始化 Agent
            await agent.initialize()
            
            # 创建运行任务
            task = asyncio.create_task(
                self._run_agent(agent),
                name=f"agent_{agent_id}"
            )
            self.agent_tasks[agent_id] = task
            
            # 更新数据库状态
            AgentRepository.update(agent_id, {
                'status': 'running'
            })
            
            logger.info(f"✅ Agent {agent.name} ({agent_id}) started")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start agent {agent_id}: {e}", exc_info=True)
            AgentRepository.update(agent_id, {'status': 'error'})
            return False
    
    async def stop_agent(self, agent_id: str) -> bool:
        """
        暂停 Agent（不完全停止，只是暂停决策循环）
        
        Args:
            agent_id: Agent ID
        
        Returns:
            是否成功暂停
        """
        try:
            agent = self.agents.get(agent_id)
            if not agent:
                logger.error(f"Agent {agent_id} not found")
                return False
            
            # 设置 Agent 状态为 PAUSED（决策循环会检查此状态）
            from agents.base_agent import AgentStatus
            agent.set_status(AgentStatus.PAUSED, "Agent paused by user")
            
            # 更新数据库状态
            AgentRepository.update(agent_id, {
                'status': 'paused'
            })
            
            logger.info(f"✅ Agent {agent.name} ({agent_id}) paused")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to stop agent {agent_id}: {e}", exc_info=True)
            return False
    
    async def delete_agent(self, agent_id: str) -> bool:
        """
        删除 Agent
        
        Args:
            agent_id: Agent ID
        
        Returns:
            是否成功删除
        """
        try:
            # 先停止 Agent
            await self.stop_agent(agent_id)
            
            # 从管理器中移除
            if agent_id in self.agents:
                del self.agents[agent_id]
            
            # 从数据库中删除
            AgentRepository.delete(agent_id)
            
            logger.info(f"✅ Agent {agent_id} deleted")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to delete agent {agent_id}: {e}", exc_info=True)
            return False
    
    async def _run_agent(self, agent: SmartTradingAgent):
        """
        运行 Agent 的主循环
        
        Args:
            agent: Agent 实例
        """
        try:
            logger.info(f"Agent {agent.name} main loop started")
            
            # Agent 内部已经有决策循环，这里只需要等待
            while True:
                # 定期检查 Agent 状态
                await asyncio.sleep(60)
                
                # 可以在这里添加健康检查
                if agent.status.value == 'error':
                    logger.error(f"Agent {agent.name} is in error state, stopping...")
                    break
                    
        except asyncio.CancelledError:
            logger.info(f"Agent {agent.name} task cancelled")
        except Exception as e:
            logger.error(f"Agent {agent.name} error: {e}", exc_info=True)
            agent.set_error(str(e))
            AgentRepository.update(agent.agent_id, {'status': 'error'})
    
    def get_agent(self, agent_id: str) -> Optional[SmartTradingAgent]:
        """
        获取 Agent 实例
        
        Args:
            agent_id: Agent ID
        
        Returns:
            Agent 实例或 None
        """
        return self.agents.get(agent_id)
    
    def get_all_agents(self) -> Dict[str, SmartTradingAgent]:
        """
        获取所有 Agent
        
        Returns:
            Agent 字典
        """
        return self.agents.copy()
    
    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        获取 Agent 状态
        
        Args:
            agent_id: Agent ID
        
        Returns:
            状态信息字典
        """
        agent = self.agents.get(agent_id)
        if not agent:
            return None
        
        return {
            'agent_id': agent_id,
            'name': agent.name,
            'status': agent.status.value,
            'current_task': agent.current_task,
            'error': agent.error,
            'is_running': agent_id in self.agent_tasks and not self.agent_tasks[agent_id].done(),
            'stats': agent.get_stats(),
            'info': agent.get_agent_info()
        }
    
    async def stop_all_agents(self):
        """停止所有 Agent"""
        logger.info("Stopping all agents...")
        
        tasks = []
        for agent_id in list(self.agents.keys()):
            tasks.append(self.stop_agent(agent_id))
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("All agents stopped")
    
    async def cleanup(self):
        """清理所有资源"""
        await self.stop_all_agents()
        self.agents.clear()
        self.agent_tasks.clear()
        logger.info("AgentManager cleaned up")

    # === 统一数据事件处理接口 ===
    
    async def handle_data_event(self, event: DataEvent):
        """
        处理数据事件并分发到相应的策略实例
        
        Args:
            event: 数据事件对象
        """
        try:
            exchange_id = event.exchange_id
            symbol = event.symbol
            
            # 处理持仓事件
            if event.event_type == DataEventType.POSITION:
                if self.position_manager:
                    await self.position_manager.update_position_from_event(
                        exchange_id, symbol, event.data
                    )
            
            # 处理订单事件 (可选：同步订单状态到 order_manager)
            elif event.event_type == DataEventType.ORDER:
                # 这里可以添加订单状态同步逻辑
                pass
            
            tasks = []
            # 对于全局事件（如余额），分发到该交易所的所有策略
            if not symbol or event.event_type in [DataEventType.BALANCE, DataEventType.CONNECTION_STATUS]:
                for agent in self.agents.values():
                    if agent.exchange.exchange_id == exchange_id:
                        tasks.append(asyncio.create_task(agent.on_data_event(event)))
            else:
                # 分发到特定的策略实例
                for agent in self.agents.values():
                    if agent.exchange.exchange_id == exchange_id and agent.symbol == symbol:
                        tasks.append(asyncio.create_task(agent.on_data_event(event)))
                                                    
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                    
        except Exception as e:
            logging.error(f"处理数据事件失败: {e}", exc_info=False)
