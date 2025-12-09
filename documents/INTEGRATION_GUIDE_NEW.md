"""
快速集成指南：如何在现有项目中使用新的架构
"""

# ============================================================================
# 一、环境准备
# ============================================================================
"""
1. 安装缺失的依赖：

pip install tiktoken

（openai 和 openai-agents 已经安装）

2. 验证安装：

python -c "import tiktoken; import openai; from agents import Agent; print('✅ All dependencies installed')"
"""

# ============================================================================
# 二、改造现有的 trading_agent.py（示例）
# ============================================================================

import json
import asyncio
import logging
from typing import Optional, Dict, Any

from models.llm_model import LLMModel
from agents.base_agent import BaseAgent, AgentStatus
from tools.tool_registry import BaseTool, ToolDefinition, ToolParameter, ToolRegistry, ToolExecutor

logger = logging.getLogger(__name__)


class GetMarketDataTool(BaseTool):
    """获取市场数据工具"""
    
    def __init__(self, exchange_manager):
        definition = ToolDefinition(
            name="get_market_data",
            description="获取指定交易对的实时市场数据，包括价格、量、24小时涨跌",
            parameters=[
                ToolParameter(
                    name="symbol",
                    type="string",
                    description="交易对，如 BTC/USDT",
                    required=True,
                ),
                ToolParameter(
                    name="timeframe",
                    type="string",
                    description="K线周期",
                    required=True,
                    enum=["1m", "5m", "15m", "1h", "4h", "1d"],
                ),
            ],
            category="market_data",
            timeout=10,
        )
        super().__init__(definition)
        self.exchange_manager = exchange_manager
    
    async def execute(self, symbol: str, timeframe: str) -> str:
        """获取 K线数据"""
        try:
            ohlcv = await self.exchange_manager.get_ohlcv(symbol, timeframe, limit=20)
            ticker = await self.exchange_manager.fetch_ticker(symbol)
            
            data = {
                "symbol": symbol,
                "timeframe": timeframe,
                "klines": ohlcv[-5:],  # 最近5根K线
                "current_price": ticker.get("last"),
                "bid": ticker.get("bid"),
                "ask": ticker.get("ask"),
                "volume_24h": ticker.get("quoteVolume"),
                "change_24h_percent": ticker.get("percentage"),
            }
            return json.dumps(data)
        except Exception as e:
            raise Exception(f"Failed to get market data: {str(e)}")


class CheckPositionTool(BaseTool):
    """检查持仓工具"""
    
    def __init__(self, position_manager):
        definition = ToolDefinition(
            name="check_position",
            description="检查当前持仓信息，包括大小、方向、入场价格、未实现盈亏",
            parameters=[
                ToolParameter(
                    name="symbol",
                    type="string",
                    description="交易对",
                    required=True,
                ),
            ],
            category="position",
            timeout=5,
        )
        super().__init__(definition)
        self.position_manager = position_manager
    
    async def execute(self, symbol: str) -> str:
        """获取持仓信息"""
        try:
            position = self.position_manager.get_position(symbol)
            if position:
                return json.dumps({
                    "symbol": symbol,
                    "size": position.get("size"),
                    "entry_price": position.get("entry_price"),
                    "current_price": position.get("current_price"),
                    "unrealized_pnl": position.get("unrealized_pnl"),
                    "side": position.get("side"),  # "long", "short", "none"
                })
            else:
                return json.dumps({"symbol": symbol, "side": "none", "size": 0})
        except Exception as e:
            raise Exception(f"Failed to check position: {str(e)}")


class CheckRiskTool(BaseTool):
    """风险检查工具"""
    
    def __init__(self, risk_manager, agent_config):
        definition = ToolDefinition(
            name="check_risk",
            description="在执行交易前检查风险，包括头寸大小、杠杆、止损设置等",
            parameters=[
                ToolParameter(
                    name="symbol",
                    type="string",
                    description="交易对",
                    required=True,
                ),
                ToolParameter(
                    name="order_size_usd",
                    type="number",
                    description="订单大小（美元）",
                    required=True,
                ),
                ToolParameter(
                    name="order_side",
                    type="string",
                    description="订单方向",
                    required=True,
                    enum=["buy", "sell"],
                ),
            ],
            category="risk",
            timeout=5,
        )
        super().__init__(definition)
        self.risk_manager = risk_manager
        self.agent_config = agent_config
    
    async def execute(self, symbol: str, order_size_usd: float, order_side: str) -> str:
        """检查交易风险"""
        try:
            risk_check = self.risk_manager.check_order_risk(
                symbol=symbol,
                size=order_size_usd,
                side=order_side,
                max_position_size=self.agent_config.get("max_position_size", 1000),
                risk_per_trade=self.agent_config.get("risk_per_trade", 0.02),
            )
            
            return json.dumps({
                "symbol": symbol,
                "order_size_usd": order_size_usd,
                "order_side": order_side,
                "is_risk_acceptable": risk_check["is_acceptable"],
                "reasons": risk_check.get("reasons", []),
                "warnings": risk_check.get("warnings", []),
            })
        except Exception as e:
            raise Exception(f"Risk check failed: {str(e)}")


class PlaceOrderTool(BaseTool):
    """下单工具"""
    
    def __init__(self, exchange_manager, order_manager, risk_manager):
        definition = ToolDefinition(
            name="place_order",
            description="在交易所下达订单（买入或卖出）",
            parameters=[
                ToolParameter(
                    name="symbol",
                    type="string",
                    description="交易对，如 BTC/USDT",
                    required=True,
                ),
                ToolParameter(
                    name="side",
                    type="string",
                    description="订单方向",
                    required=True,
                    enum=["buy", "sell"],
                ),
                ToolParameter(
                    name="order_type",
                    type="string",
                    description="订单类型",
                    required=True,
                    enum=["market", "limit"],
                ),
                ToolParameter(
                    name="amount",
                    type="number",
                    description="数量（币数）",
                    required=True,
                ),
                ToolParameter(
                    name="price",
                    type="number",
                    description="价格（限价单时使用，市价单可为 null）",
                    required=False,
                ),
                ToolParameter(
                    name="stop_loss",
                    type="number",
                    description="止损价格（可选）",
                    required=False,
                ),
                ToolParameter(
                    name="take_profit",
                    type="number",
                    description="获利价格（可选）",
                    required=False,
                ),
            ],
            category="trading",
            timeout=15,
        )
        super().__init__(definition)
        self.exchange_manager = exchange_manager
        self.order_manager = order_manager
        self.risk_manager = risk_manager
    
    async def execute(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> str:
        """执行下单"""
        try:
            # 下单
            order = await self.exchange_manager.place_order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                amount=amount,
                price=price,
            )
            
            # 记录订单
            self.order_manager.add_order(order)
            
            # 设置止损/获利
            if stop_loss:
                await self.exchange_manager.place_stop_loss(symbol, stop_loss, side)
            if take_profit:
                await self.exchange_manager.place_take_profit(symbol, take_profit, side)
            
            return json.dumps({
                "success": True,
                "order_id": order.get("id"),
                "symbol": symbol,
                "side": side,
                "amount": amount,
                "price": order.get("price"),
                "timestamp": order.get("timestamp"),
            })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
            })


class ClosePositionTool(BaseTool):
    """平仓工具"""
    
    def __init__(self, exchange_manager, position_manager, order_manager):
        definition = ToolDefinition(
            name="close_position",
            description="平掉指定交易对的所有持仓",
            parameters=[
                ToolParameter(
                    name="symbol",
                    type="string",
                    description="交易对",
                    required=True,
                ),
                ToolParameter(
                    name="reason",
                    type="string",
                    description="平仓原因（用于日志记录）",
                    required=True,
                ),
            ],
            category="trading",
            timeout=15,
        )
        super().__init__(definition)
        self.exchange_manager = exchange_manager
        self.position_manager = position_manager
        self.order_manager = order_manager
    
    async def execute(self, symbol: str, reason: str) -> str:
        """平仓"""
        try:
            position = self.position_manager.get_position(symbol)
            if not position or position.get("size") == 0:
                return json.dumps({
                    "success": True,
                    "message": f"No open position for {symbol}",
                })
            
            # 确定平仓方向
            close_side = "sell" if position.get("side") == "long" else "buy"
            
            # 市价平仓
            order = await self.exchange_manager.place_order(
                symbol=symbol,
                side=close_side,
                order_type="market",
                amount=position.get("size"),
            )
            
            # 记录
            self.order_manager.add_order(order)
            self.position_manager.close_position(symbol)
            
            return json.dumps({
                "success": True,
                "order_id": order.get("id"),
                "symbol": symbol,
                "closed_size": position.get("size"),
                "close_price": order.get("price"),
                "reason": reason,
            })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
            })


# ============================================================================
# 三、在 main.py 中初始化和使用
# ============================================================================

EXAMPLE_MAIN_INTEGRATION = '''
# 在 main.py 中添加以下代码

from models.llm_model import LLMModel
from agents.trading_agent import TradingAgent
from agents.base_agent import AgentManager
from tools.tool_registry import ToolRegistry
from trading_tools_implementation import (  # 上面定义的工具
    GetMarketDataTool,
    CheckPositionTool,
    CheckRiskTool,
    PlaceOrderTool,
    ClosePositionTool,
)

# 全局 Agent 管理器
agent_manager = AgentManager()

# 创建 Agent 的 API 端点
@app.post("/agents")
async def create_agent(agent_config: AgentConfig):
    """创建新的交易 Agent"""
    
    # 从数据库加载模型配置
    model_config = await get_model_config(agent_config.model_id)
    
    # 初始化 LLM
    llm = LLMModel(
        api_key=model_config.api_key,
        model=model_config.model,
        base_url=model_config.base_url,
        provider=model_config.provider,  # 如: 'openai', 'deepseek'
        temperature=0.7,
    )
    
    # 初始化工具
    tool_registry = ToolRegistry()
    tool_registry.register(GetMarketDataTool(exchange_manager))
    tool_registry.register(CheckPositionTool(position_manager))
    tool_registry.register(CheckRiskTool(risk_manager, agent_config.dict()))
    tool_registry.register(PlaceOrderTool(exchange_manager, order_manager, risk_manager))
    tool_registry.register(ClosePositionTool(exchange_manager, position_manager, order_manager))
    
    # 创建 Agent
    system_prompt = f"""你是一个专业的加密货币交易 Agent。
名称: {agent_config.name}
交易对: {agent_config.symbol}
时间周期: {agent_config.timeframe}
最大头寸: ${agent_config.max_position_size}
风险比例: {agent_config.risk_per_trade * 100}%

你的责任：
1. 分析 {agent_config.symbol} 的市场数据和指标
2. 检查当前持仓和风险
3. 根据分析结果做出交易决策
4. 执行交易（买入、卖出、平仓）

始终：
- 遵守风险管理规则
- 在执行交易前检查风险
- 清楚地说明你的交易理由
- 监控未实现的收益/损失
"""
    
    agent = TradingAgent(
        agent_id=agent_config.id,
        name=agent_config.name,
        llm_model=llm,
        tool_registry=tool_registry,
        system_prompt=system_prompt,
    )
    
    await agent.initialize()
    agent_manager.register(agent)
    
    # 保存到数据库
    await save_agent(agent_config)
    
    return {"agent_id": agent.agent_id, "status": "initialized"}


@app.post("/agents/{agent_id}/execute")
async def execute_agent_task(agent_id: str, task: str):
    """执行 Agent 任务"""
    
    agent = agent_manager.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # 获取执行上下文
    exchange_config = await get_exchange_config(agent.context.get("exchange_id"))
    account_info = await exchange_manager.get_account_info()
    
    context = {
        "exchange": exchange_config.exchange,
        "account_balance": account_info["balance"],
        "available_balance": account_info["free"],
    }
    
    # 执行任务（异步）
    asyncio.create_task(
        agent.execute(task=task, context=context)
    )
    
    return {"agent_id": agent_id, "status": "executing"}


@app.get("/agents/{agent_id}/info")
async def get_agent_info(agent_id: str):
    """获取 Agent 信息"""
    
    agent = agent_manager.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return agent.get_agent_info()


@app.get("/agents/{agent_id}/logs")
async def get_agent_logs(agent_id: str):
    """获取 Agent 执行日志"""
    
    agent = agent_manager.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return agent.export_execution_log()
'''

print(EXAMPLE_MAIN_INTEGRATION)

# ============================================================================
# 四、WebSocket 实时更新（可选）
# ============================================================================

WEBSOCKET_INTEGRATION = '''
# 在 WebSocket 连接中添加 Agent 状态推送

@app.websocket("/ws/agent/{agent_id}")
async def websocket_agent_endpoint(websocket: WebSocket, agent_id: str):
    """Agent 实时状态推送"""
    
    await websocket.accept()
    
    agent = agent_manager.get(agent_id)
    if not agent:
        await websocket.close(code=4004, reason="Agent not found")
        return
    
    # 设置回调钩子
    async def on_status_change(status):
        await websocket.send_json({
            "type": "status_change",
            "agent_id": agent_id,
            "status": status.value,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    async def on_tool_call(tool_call):
        await websocket.send_json({
            "type": "tool_call",
            "agent_id": agent_id,
            "tool_call": {
                "id": tool_call.id,
                "name": tool_call.name,
                "arguments": tool_call.arguments,
                "timestamp": tool_call.timestamp.isoformat(),
            },
        })
    
    async def on_error(error_message):
        await websocket.send_json({
            "type": "error",
            "agent_id": agent_id,
            "error": error_message,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    # 注册回调
    agent.on_status_change = on_status_change
    agent.on_tool_call = on_tool_call
    agent.on_error = on_error
    
    try:
        while True:
            # 保持连接打开
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # 清理回调
        agent.on_status_change = None
        agent.on_tool_call = None
        agent.on_error = None
'''

print(WEBSOCKET_INTEGRATION)

# ============================================================================
# 五、配置数据库存储（可选但推荐）
# ============================================================================

DATABASE_INTEGRATION = '''
# 添加到 database.py

from sqlalchemy import Column, String, Float, DateTime, JSON, Text
from datetime import datetime

class AIAgentRecord(Base):
    """AI Agent 记录"""
    __tablename__ = "ai_agents"
    
    id = Column(String(50), primary_key=True)
    name = Column(String(100))
    model_id = Column(String(50), ForeignKey("ai_models.id"))
    exchange_id = Column(String(50), ForeignKey("exchanges.id"))
    system_prompt = Column(Text)
    total_cost = Column(Float, default=0)
    status = Column(String(20))  # idle, running, error
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentExecutionLog(Base):
    """Agent 执行日志"""
    __tablename__ = "agent_execution_logs"
    
    id = Column(String(50), primary_key=True)
    agent_id = Column(String(50), ForeignKey("ai_agents.id"))
    task = Column(Text)
    messages = Column(JSON)  # 对话历史
    tool_calls = Column(JSON)  # 工具调用记录
    total_cost = Column(Float)
    status = Column(String(20))  # success, failed, error
    created_at = Column(DateTime, default=datetime.utcnow)
'''

print(DATABASE_INTEGRATION)
