# INTEGRATION_GUIDE.md
# 后端模块集成指南

## 概述

本指南说明如何将新的管理器类（ExchangeManager、OrderManager、PositionManager）集成到现有的FastAPI后端中。

## 新增模块

### 1. **config.py** - 全局配置
存储所有配置参数：
- 启用的交易所列表
- API密钥（从环境变量读取）
- 交易所设置（杠杆等）
- 风险管理参数
- 通知配置

**使用示例：**
```python
from config import ENABLED_EXCHANGES, API_KEYS, EXCHANGE_SETTINGS
```

### 2. **bot_notifier.py** - 通知系统
用于发送交易信号、风险警告等：
- 支持Telegram通知
- 交易通知、警告、错误通知
- 全局单例模式

**使用示例：**
```python
from bot_notifier import get_notifier
notifier = get_notifier()
await notifier.notify_trade(agent_id, symbol, side, quantity, price)
```

### 3. **exchange_manager.py** - 交易所管理
统一管理多个交易所的连接：
- 动态导入和初始化交易所
- 统一的数据事件接口
- 灵活的数据类型订阅

**主要方法：**
```python
# 初始化所有交易所
await exchange_manager.initialize_all(
    enabled_exchanges=['binance', 'okx'],
    api_keys=API_KEYS,
    exchange_settings=EXCHANGE_SETTINGS
)

# 更新监听的交易对
await exchange_manager.update_watched_symbols(
    active_symbols={'binance': ['BTC/USDT']},
    exchange_settings=EXCHANGE_SETTINGS
)

# 订阅额外的数据类型
await exchange_manager.subscribe_additional_data_types(
    exchange_id='binance',
    data_types=[DataEventType.BALANCE, DataEventType.ORDER],
    symbols=['BTC/USDT']
)

# 关闭所有连接
await exchange_manager.close_all()
```

### 4. **position_manager.py** - 持仓管理
管理多个交易所、多个symbol的持仓：
- 持仓追踪
- 持仓同步
- 持仓更新

**主要方法：**
```python
# 同步所有持仓
await position_manager.sync_positions()

# 获取持仓
position = await position_manager.get_position(
    exchange_id='binance',
    symbol='BTC/USDT',
    side=PositionSide.LONG
)

# 更新持仓
await position_manager.update_position_from_trade(
    exchange_id='binance',
    symbol='BTC/USDT',
    side=OrderSide.BUY,
    quantity=1.0,
    price=45000.0,
    pos_side=PositionSide.LONG
)

# 获取持仓摘要
summary = await position_manager.get_position_summary()
```

### 5. **order_manager.py** - 订单管理
管理多个symbol的订单：
- 订单创建、查询、取消
- 订单分组管理
- 风险约束检查

**主要方法：**
```python
# 创建订单
order = await order_manager.create_order_advanced(
    exchange_id='binance',
    symbol='BTC/USDT',
    order_type=OrderType.LIMIT,
    action=OrderAction.OPEN_LONG,
    amount=1.0,
    price=45000.0
)

# 取消订单
await order_manager.cancel_order(order_id='123456')

# 获取订单
order = await order_manager.get_order(order_id='123456')

# 获取未平仓订单
open_orders = await order_manager.get_open_orders(
    exchange_id='binance',
    symbol='BTC/USDT'
)
```

## 集成到FastAPI

### 步骤1：导入必要的模块

```python
from config import ENABLED_EXCHANGES, API_KEYS, EXCHANGE_SETTINGS
from shared_state import SharedState
from exchange_manager import ExchangeManager
from position_manager import PositionManager
from order_manager import OrderManager
from risk_manager import RiskManager
from bot_notifier import get_notifier
```

### 步骤2：在lifespan事件中初始化

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化
    notifier = get_notifier()
    shared_state = SharedState(notifier=notifier)
    
    exchange_manager = ExchangeManager(shared_state=shared_state)
    await exchange_manager.initialize_all(
        enabled_exchanges=ENABLED_EXCHANGES,
        api_keys=API_KEYS,
        exchange_settings=EXCHANGE_SETTINGS
    )
    
    risk_manager = RiskManager()
    position_manager = PositionManager(exchange_manager, shared_state)
    order_manager = OrderManager(exchange_manager, risk_manager, shared_state, position_manager)
    
    shared_state.start_background_updater()
    await position_manager.sync_positions()
    
    # 注入到app的state中
    app.state.shared_state = shared_state
    app.state.exchange_manager = exchange_manager
    app.state.position_manager = position_manager
    app.state.order_manager = order_manager
    
    yield
    
    # 清理
    await exchange_manager.close_all()
```

### 步骤3：在路由中使用

```python
@app.get("/api/positions")
async def get_positions(request: Request):
    position_manager = request.app.state.position_manager
    summary = await position_manager.get_position_summary()
    return summary

@app.post("/api/orders")
async def create_order(request: Request, order_data: dict):
    order_manager = request.app.state.order_manager
    order = await order_manager.create_order_advanced(
        exchange_id=order_data['exchange_id'],
        symbol=order_data['symbol'],
        order_type=order_data.get('order_type'),
        action=order_data.get('action'),
        amount=order_data['amount'],
        price=order_data.get('price')
    )
    return order.to_dict()
```

## 环境变量配置

在`.env`文件中配置：

```bash
# 交易所API密钥
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
BINANCE_TESTNET=false

OKX_API_KEY=your_key
OKX_API_SECRET=your_secret
OKX_PASSPHRASE=your_passphrase
OKX_TESTNET=false

# 通知配置
NOTIFICATIONS_ENABLED=true
TELEGRAM_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id

# 日志和服务器配置
LOG_LEVEL=INFO
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
```

## 完整示例

参考 `integration_example.py` 了解如何创建一个完整的TradingBackend类。

## 数据流

```
交易所数据事件
    ↓
ExchangeManager (统一事件处理)
    ↓
SharedState (状态管理和缓存)
    ↓
PositionManager (持仓管理)
OrderManager (订单管理)
    ↓
FastAPI路由
    ↓
WebSocket 推送 → 前端UI
```

## 常见问题

### Q: 如何处理多个交易所？
A: ExchangeManager支持多个交易所，在initialize_all时传入所有启用的交易所ID。

### Q: 如何订阅实时数据？
A: 使用exchange_manager.subscribe_data()或exchange_manager.subscribe_additional_data_types()方法。

### Q: 如何处理订单状态更新？
A: PositionManager和OrderManager都有watch loop处理交易所事件，自动更新本地状态。

### Q: 如何集成风险管理？
A: RiskManager用于计算仓位大小和风险检查，在OrderManager中使用。

## 最佳实践

1. **总是使用async/await**：所有方法都是异步的
2. **使用共享状态**：利用SharedState缓存数据，避免频繁查询交易所
3. **错误处理**：使用try-except处理可能的网络和API错误
4. **日志记录**：使用logging记录重要事件
5. **通知提醒**：使用BotNotifier发送重要事件通知

## 故障排除

### 问题：交易所连接失败
- 检查API密钥是否正确
- 检查网络连接
- 检查交易所是否在线

### 问题：订单创建失败
- 检查余额是否足够
- 检查杠杆设置
- 检查订单参数是否有效

### 问题：持仓同步不成功
- 检查是否有未平仓头寸
- 检查账户权限设置
- 查看日志了解具体错误
