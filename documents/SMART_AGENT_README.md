# 智能交易Agent实现文档

## 概述

本实现集成了LLM驱动的智能交易Agent，每个Agent对应一个交易所、一个交易对、一个时间框架和多个技术指标。Agent能够：

1. 订阅实时市场数据（K线、Ticker、订单簿、成交）
2. 收集持仓和账户信息
3. 与LLM交互，获取交易决策
4. 执行交易指令（开多/开空/平仓/止盈止损）
5. 使用工具系统扩展功能

## 核心组件

### 1. SmartTradingAgent (`agents/smart_trading_agent.py`)

智能交易Agent的核心实现，负责：

- **数据订阅**: 通过CommonExchange订阅实时市场数据
- **数据收集**: 整理市场、持仓、账户信息
- **LLM交互**: 构建提示词，调用LLM获取决策
- **工具执行**: 执行LLM返回的工具调用
- **决策循环**: 定期执行决策流程

**关键方法**:
- `_load_historical_klines()`: 加载历史K线数据
- `_subscribe_market_data()`: 订阅实时数据流
- `_decision_loop()`: 主决策循环
- `_make_decision()`: 执行单次决策
- `_build_market_context()`: 构建市场上下文
- `_calculate_indicators()`: 计算技术指标

### 2. 交易工具集 (`tools/trading_tools.py`)

提供给LLM调用的交易工具：

- **OpenLongTool**: 开多仓
- **OpenShortTool**: 开空仓
- **ClosePositionTool**: 平仓
- **SetStopLossTool**: 设置止损
- **SetTakeProfitTool**: 设置止盈
- **GetMarketInfoTool**: 获取市场信息
- **CancelOrdersTool**: 取消订单

每个工具都：
- 定义了清晰的参数和描述（供LLM理解）
- 实现了具体的交易逻辑
- 返回JSON格式的执行结果

### 3. AgentManager (`agent_manager.py`)

Agent生命周期管理器：

- **create_agent()**: 创建Agent实例
- **start_agent()**: 启动Agent
- **stop_agent()**: 停止Agent
- **delete_agent()**: 删除Agent
- **get_agent_status()**: 获取Agent状态

### 4. 提示词模板 (`prompts/trading_prompts.py`)

提供不同交易风格的系统提示词：

- **DEFAULT_TRADING_PROMPT**: 默认平衡策略
- **AGGRESSIVE_TRADING_PROMPT**: 激进短线策略
- **CONSERVATIVE_TRADING_PROMPT**: 保守长线策略
- **TREND_FOLLOWING_PROMPT**: 趋势跟随策略
- **MEAN_REVERSION_PROMPT**: 均值回归策略

## 数据流

```
1. Agent启动
   ↓
2. 加载历史K线（fetch_ohlcv）
   ↓
3. 订阅实时数据（WebSocket）
   - K线更新 → _on_kline_update
   - Ticker更新 → _on_ticker_update
   - 订单簿更新 → _on_orderbook_update
   - 持仓更新 → _on_position_update
   - 订单更新 → _on_order_update
   ↓
4. 决策循环（每N秒）
   ↓
5. 收集数据
   - 市场上下文（K线、指标、价格）
   - 持仓上下文（仓位、盈亏、杠杆）
   - 账户上下文（余额、保证金）
   ↓
6. 构建LLM提示词
   ↓
7. 调用LLM（带工具定义）
   ↓
8. 解析LLM响应
   ↓
9. 执行工具调用（如果有）
   - 开仓/平仓
   - 设置止盈止损
   - 查询市场信息
   ↓
10. 记录执行结果
    ↓
11. 返回步骤4（循环）
```

## 使用示例

### 1. 创建Agent

```python
# 通过API创建Agent
POST /api/agents
{
    "name": "BTC趋势跟踪Agent",
    "model_id": "gpt-4o-mini-001",
    "exchange_id": "okx-testnet-001",
    "symbol": "BTC/USDT:USDT",
    "timeframe": "15m",
    "indicators": ["rsi", "ema", "macd", "bb"],
    "prompt": "你是一个专业的BTC交易助手...",
    "max_position_size": 1000.0,
    "risk_per_trade": 0.02,
    "default_leverage": 2
}
```

### 2. 启动Agent

```python
POST /api/agents/{agent_id}/start
```

Agent将：
1. 连接到交易所
2. 加载最近200根K线
3. 订阅实时数据
4. 开始决策循环（默认60秒一次）

### 3. 监控Agent

```python
# 获取Agent状态
GET /api/agents/{agent_id}

# 获取对话历史
GET /api/agents/{agent_id}/conversations

# 获取工具调用记录
GET /api/agents/{agent_id}/tool-calls

# 获取持仓
GET /api/agents/{agent_id}/positions
```

### 4. 停止Agent

```python
POST /api/agents/{agent_id}/stop
```

## 技术指标

Agent自动计算以下指标：

- **RSI (Relative Strength Index)**: 相对强弱指标
- **EMA (Exponential Moving Average)**: 指数移动平均线
- **MACD (Moving Average Convergence Divergence)**: 平滑异同移动平均线
- **BB (Bollinger Bands)**: 布林带
- **ATR (Average True Range)**: 平均真实波动幅度
- **成交量分析**: 当前成交量和平均成交量

## LLM交互示例

### 提示词示例

```
你是一个专业的加密货币交易助手。请根据以下信息分析市场并给出交易建议。

市场数据 (BTC/USDT:USDT @ 15m):
当前价格: 43250.5

最近50根K线数据
最新K线: 开43200, 高43280, 低43150, 收43250.5, 量1234.5

技术指标:
RSI: 58.5
EMA_20: 43180.2
EMA_50: 43050.8
MACD: 45.3
MACD_Signal: 38.7
MACD_Histogram: 6.6
BB_Upper: 43450.0
BB_Middle: 43200.0
BB_Lower: 42950.0
ATR: 125.4
Volume: 1234.5
AvgVolume_20: 980.3

持仓信息:
杠杆倍数: 2x
持仓总价值: 0.00
总浮动盈亏: 0.00

当前持仓: 无持仓

账户信息:
可用保证金: 1000.00
已用保证金: 0.00
保证金率: 0.00%

配置参数:
- 最大持仓规模: 1000.0
- 单笔风险比例: 2.0%
- 默认杠杆: 2x

请分析当前市场状况，并决定下一步操作...
```

### LLM响应示例

```
【市场分析】
- 趋势判断: 上涨
- 关键支撑/阻力: 支撑43150, 阻力43450
- 技术指标综合: 
  * RSI 58.5处于中性偏多区域
  * EMA20在EMA50上方，短期趋势向上
  * MACD金叉且柱状图扩大，多头动能增强
  * 价格接近布林带中轨，未超买
  * 成交量放大，趋势确认

【持仓状态】
- 当前持仓: 无持仓
- 浮动盈亏: 0

【决策建议】
- 操作: 开多
- 理由: 多个技术指标显示上涨趋势，成交量配合良好，适合做多
- 风险评估: 中

【执行计划】
1. 开多仓0.046张（约1000 USDT名义价值，2倍杠杆）
2. 止损设在43100（低于近期低点）
3. 止盈设在43600（阻力位附近）
```

然后LLM会调用工具：

```json
{
  "tool_calls": [
    {
      "function": "open_long",
      "arguments": {
        "amount": 0.046,
        "leverage": 2,
        "stop_loss": 43100,
        "take_profit": 43600
      }
    }
  ]
}
```

## 配置参数

### Agent配置

- **decision_interval**: 决策间隔（秒），默认60
- **max_position_size**: 最大持仓规模（USDT）
- **risk_per_trade**: 单笔风险比例（0-1）
- **default_leverage**: 默认杠杆倍数

### 交易所配置

使用你封装的CommonExchange、BinanceExchange、OkxExchange：

- 支持WebSocket实时数据推送
- 支持REST API历史数据查询
- 统一的订单接口

## 注意事项

1. **API密钥安全**: 确保API密钥保存安全，不要泄露
2. **测试网优先**: 建议先在测试网测试Agent逻辑
3. **风险控制**: 设置合理的最大持仓和风险比例
4. **监控日志**: 密切关注Agent的日志和执行记录
5. **LLM成本**: 频繁调用LLM会产生成本，根据需要调整决策间隔
6. **异常处理**: Agent有完善的错误处理，异常时会自动停止

## 扩展开发

### 添加新的技术指标

在`smart_trading_agent.py`的`_calculate_indicators()`方法中添加：

```python
if 'kdj' in self.indicators:
    indicators['KDJ'] = self._calculate_kdj(highs, lows, closes)
```

### 添加新的交易工具

在`tools/trading_tools.py`中创建新的工具类：

```python
class CustomTool(BaseTool):
    def __init__(self, exchange: CommonExchange, symbol: str):
        definition = ToolDefinition(
            name="custom_action",
            description="自定义操作",
            parameters=[...],
            category="trading"
        )
        super().__init__(definition)
        
    async def execute(self, **kwargs) -> str:
        # 实现工具逻辑
        pass
```

### 自定义提示词

创建自己的交易策略提示词，在`prompts/trading_prompts.py`中添加新模板。

## 故障排查

### Agent无法启动

1. 检查交易所是否已连接
2. 检查LLM模型配置是否正确
3. 查看日志中的错误信息

### 数据未更新

1. 检查WebSocket连接状态
2. 验证symbol格式是否正确
3. 查看交易所是否支持该交易对

### LLM不调用工具

1. 检查提示词是否清晰
2. 验证工具定义是否正确
3. 查看LLM响应内容

### 订单执行失败

1. 检查账户余额是否充足
2. 验证订单参数（价格、数量）是否合法
3. 查看交易所返回的错误信息

## 后续优化方向

1. **多策略支持**: 同一个Agent运行多个子策略
2. **回测功能**: 在历史数据上测试策略
3. **性能监控**: 实时监控Agent性能指标
4. **告警系统**: 异常情况及时通知
5. **策略优化**: 基于历史表现自动优化参数
6. **群体智能**: 多个Agent协同工作
