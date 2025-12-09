"""
架构集成指南和使用示例
"""

# ============================================================================
# 1. 架构总结
# ============================================================================
"""
┌─────────────────────────────────────────────────────────────────────────┐
│                         交易 Agent 架构                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────┐         ┌──────────────┐      ┌──────────────┐        │
│  │  LLM Model   │         │  Trading     │      │ Tool         │        │
│  │  (OpenAI)    │◄────────┤  Agent       │──────►│ Registry     │        │
│  │              │         │              │      │              │        │
│  │ - 对话管理    │         │ - 思考规划    │      │ - 工具定义    │        │
│  │ - Token计算   │         │ - 执行工具    │      │ - 工具执行    │        │
│  │ - Cost追踪   │         │ - 状态管理    │      │ - 执行记录    │        │
│  │ - History    │         │              │      │              │        │
│  └──────────────┘         └──────────────┘      └──────────────┘        │
│       ▲                           ▲                    ▲                 │
│       │                           │                    │                 │
│       └───────────────────────────┼────────────────────┘                 │
│                                   │                                      │
│                           ┌───────▼────────┐                             │
│                           │ Exchange Mgr   │                             │
│                           │                │                             │
│                           │ - 连接交易所    │                             │
│                           │ - 获取市场数据  │                             │
│                           │ - 执行订单      │                             │
│                           └────────────────┘                             │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
"""

# ============================================================================
# 2. 核心模块说明
# ============================================================================
"""
a) LLMModel (models/llm_model.py)
   ├─ TokenCounter: Token 计数和成本计算
   ├─ ConversationHistory: 对话历史管理（带时间戳）
   └─ LLMModel: OpenAI 对话包装
       ├─ 同步/异步对话接口
       ├─ Tool calling 支持
       └─ 成本追踪

b) BaseAgent (agents/base_agent.py)
   ├─ 状态管理（IDLE, THINKING, EXECUTING, ERROR）
   ├─ 消息历史记录
   ├─ 工具调用记录
   ├─ 回调钩子（status change, tool call, error）
   └─ 统计信息

c) TradingAgent (agents/trading_agent.py)
   ├─ 继承 BaseAgent
   ├─ 集成 LLMModel
   ├─ 集成 ToolRegistry
   ├─ 两阶段执行：思考 → 执行
   └─ 完整日志导出

d) ToolRegistry (tools/tool_registry.py)
   ├─ BaseTool: 工具基类
   ├─ ToolDefinition: 工具定义（转换为 OpenAI 格式）
   ├─ ToolRegistry: 工具管理
   ├─ ToolExecutor: 工具执行和结果处理
   └─ 自动转换为 Function Calling 格式
"""

# ============================================================================
# 3. 使用示例
# ============================================================================

"""
# Step 1: 定义交易工具
from tools.tool_registry import BaseTool, ToolDefinition, ToolParameter, ToolRegistry

class GetMarketDataTool(BaseTool):
    '''获取市场数据工具'''
    
    def __init__(self, exchange_manager):
        definition = ToolDefinition(
            name="get_market_data",
            description="获取指定交易对的最新市场数据（价格、量、变化等）",
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
                    description="时间周期",
                    required=True,
                    enum=["1m", "5m", "15m", "1h", "4h", "1d"],
                ),
            ],
            category="market_data",
        )
        super().__init__(definition)
        self.exchange_manager = exchange_manager
    
    async def execute(self, symbol: str, timeframe: str) -> str:
        '''执行工具'''
        data = await self.exchange_manager.get_ohlcv(symbol, timeframe)
        return json.dumps(data)


class PlaceOrderTool(BaseTool):
    '''下单工具'''
    
    def __init__(self, exchange_manager):
        definition = ToolDefinition(
            name="place_order",
            description="在交易所下单",
            parameters=[
                ToolParameter(name="symbol", type="string", description="交易对"),
                ToolParameter(name="side", type="string", description="方向", enum=["buy", "sell"]),
                ToolParameter(name="amount", type="number", description="数量"),
                ToolParameter(name="price", type="number", description="价格（市价单传 0）"),
            ],
            category="trading",
            timeout=10,
        )
        super().__init__(definition)
        self.exchange_manager = exchange_manager
    
    async def execute(self, symbol: str, side: str, amount: float, price: float) -> str:
        '''执行工具'''
        order = await self.exchange_manager.place_order(symbol, side, amount, price)
        return json.dumps(order)
# Step 2: 初始化 Agent
from models.llm_model import LLMModel
from agents.trading_agent import TradingAgent

# 初始化 LLM 模型
llm = LLMModel(
    api_key="your-api-key",
    model="gpt-44-mini",  # 或其他模型
    base_url="https://api.openai.com/v1",  # 或 https://api.deepseek.com 等
    provider="openai",  # 或 'deepseek', 等
    temperature=0.7,
)

# 初始化工具注册表
tools_registry = ToolRegistry()
tools_registry.register(GetMarketDataTool(exchange_manager))
tools_registry.register(PlaceOrderTool(exchange_manager))

# 创建 Agent
system_prompt = '''你是一个专业的加密货币交易 Agent。
你可以：
1. 分析市场数据
2. 根据技术指标做出交易决策
3. 执行买卖操作

始终遵守风险管理规则。'''

agent = TradingAgent(
    agent_id="agent_001",
    name="BTC Trader",
    llm_model=llm,
    tool_registry=tools_registry,
    system_prompt=system_prompt,
)

# Step 3: 执行任务
await agent.initialize()

context = {
    "exchange": "binance",
    "account_balance": 10000,
    "symbol": "BTC/USDT",
}

await agent.execute(
    task="分析 BTC/USDT 在 1h 时间周期的行情，如果出现金叉信号就买入",
    context=context
)

# Step 4: 获取执行结果
info = agent.get_agent_info()
print(f"Agent 成本: ${info['total_cost']:.6f}")
print(f"工具调用: {info['total_tool_calls']}")
print(f"成功: {info['successful_tool_calls']}, 失败: {info['failed_tool_calls']}")

# Step 5: 导出完整日志
logs = agent.export_execution_log()
with open(f"agent_logs/{agent.agent_id}.json", "w") as f:
    json.dump(logs, f, indent=2)

await agent.cleanup()
"""

# ============================================================================
# 4. 与现有代码的整合建议
# ============================================================================
"""
当前已有的文件应该这样集成：

a) exchange_manager.py
   └─ 包装为工具：GetMarketDataTool, PlaceOrderTool, GetPositionTool 等

b) order_manager.py
   └─ 在 Tool 执行中调用 order_manager 的方法

c) position_manager.py
   └─ 在 Tool 执行中调用 position_manager 的方法

d) risk_manager.py
   └─ 创建 RiskCheckTool，在执行交易前检查风险

e) main.py (FastAPI 应用)
   └─ 添加 API 端点来创建和管理 Agent
       POST /agents - 创建新 Agent
       POST /agents/{id}/execute - 执行任务
       GET /agents/{id}/info - 获取 Agent 信息
       GET /agents/{id}/logs - 获取执行日志
"""

# ============================================================================
# 5. 与 openai-agents 库的关系
# ============================================================================
"""
openai-agents 库的作用:
✅ 直接使用:
   - @function_tool decorator 定义工具（比手写 JSON 简洁）
   - Agent & Runner 类（虽然我们也可以用自己的 BaseAgent）
   - RunContextWrapper 传递执行上下文

我们的设计的作用:
✅ 补充:
   - Token 计数和成本追踪
   - 完整的对话历史管理
   - Agent 状态管理和回调系统
   - 工具执行的统计和日志
   - 交易特定的错误处理和重试逻辑

整合方式:
Option A: 完全替换 openai-agents
   └─ 使用我们的 TradingAgent，调用 openai 库的 ChatCompletion

Option B: 混合使用（推荐）
   ├─ openai-agents 用于 Tool 定义（@function_tool）
   ├─ 我们的 Agent 用于高级编排和状态管理
   └─ 两者无冲突

Option C: 进阶（后续优化）
   └─ 使用 openai-agents 的 Agent & Runner
   ├─ 在上面包装我们的状态和成本追踪
   └─ 充分利用 openai-agents 的高级功能
"""

# ============================================================================
# 6. 下一步任务
# ============================================================================
"""
1. 安装缺失的依赖
   pip install tiktoken

2. 创建交易工具实现
   - 在 tools/trading_tools.py 中实现具体的工具类
   - 将 exchange_manager 的方法包装成工具

3. 创建 API 端点
   - POST /agents - 创建 Agent
   - POST /agents/{id}/execute - 执行任务
   - GET /agents - 列出所有 Agent
   - GET /agents/{id}/info - Agent 信息

4. 数据库存储
   - 存储 Agent 配置
   - 存储执行日志和成本信息
   - 存储对话历史

5. WebSocket 实时更新
   - Agent 状态变化时推送更新
   - Tool 执行时推送进度

6. 错误处理和重试
   - Tool 执行失败重试逻辑
   - LLM 调用的超时处理
   - 交易特定的验证和确认
"""

# ============================================================================
# 7. 关键设计决策
# ============================================================================
"""
Q: 为什么要再加一层 BaseAgent，不直接用 openai-agents 的 Agent？
A: 
  1. openai-agents 主要关注工具的定义和调用，缺少交易业务逻辑
  2. 我们需要自己的状态管理、成本追踪、错误处理
  3. BaseAgent 是可复用的，不仅用于交易，也可用于其他 Agent（分析、风险等）
  4. 完全控制 Agent 的生命周期和行为

Q: Token 计算的精确度够吗？
A:
  1. tiktoken 是 OpenAI 官方的计数库，精度 >99%
  2. 建议定期与实际消费对比，调整价格参数
  3. openai 库的 response.usage 是准确的，用于最终对账

Q: 工具执行是异步的，如何保证顺序？
A:
  1. 当前设计 execute_multiple_tool_calls 是顺序执行（await）
  2. 可以改为并发（asyncio.gather）如果工具无依赖
  3. 对于交易，顺序通常很重要（先检查风险，再下单）

Q: 如何处理 LLM 的幻觉（调用不存在的工具）？
A:
  1. ToolExecutor 会返回 "Tool not found" 错误
  2. 反馈给 LLM，让它重新思考
  3. 可以在 tool_choice 参数中限制 LLM 只能用特定工具
"""
