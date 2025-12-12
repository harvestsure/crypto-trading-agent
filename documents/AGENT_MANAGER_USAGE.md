# agent_manager 使用指南

## 概述

`agent_manager` 是一个全局的 `AgentManager` 实例，负责创建、启动、停止和管理所有交易 Agent。它在 FastAPI 应用启动时初始化，并在应用关闭时清理。

## 定义位置

- **定义类**：[scripts/backend/agent_manager.py](agent_manager.py)
- **初始化位置**：[scripts/backend/main.py](main.py#L326) 中的 `lifespan()` 函数
- **存储位置**：`app.state.agent_manager`

## main.py 中的定义

```python
# 行 275: 全局变量声明
agent_manager: Optional[AgentManager] = None  # Will be initialized in lifespan

# 行 326: 在 lifespan 启动事件中初始化
agent_manager = AgentManager(
    exchange_manager=exchange_manager,
    order_manager=order_manager,
    position_manager=position_manager
)

# 行 411: 将其存储到 app.state 中供路由使用
app.state.agent_manager = agent_manager
```

## 在路由中正确使用

### ✅ 推荐方式（使用 FastAPI Request）

```python
from fastapi import APIRouter, Request, HTTPException

# 辅助函数
def get_agent_manager_from_request(request: Request):
    """从 FastAPI request 中获取 agent_manager"""
    agent_manager = getattr(request.app.state, 'agent_manager', None)
    if not agent_manager:
        raise HTTPException(status_code=500, detail="Agent manager not initialized")
    return agent_manager

# 在路由中使用
@router.get("/{agent_id}/status")
async def get_agent_status(agent_id: str, request: Request):
    """获取Agent的实时状态"""
    agent_manager = get_agent_manager_from_request(request)
    
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return agent_manager.get_agent_status(agent_id)
```

### ❌ 不推荐方式

```python
# ❌ 错误：这会导入类而不是实例
from agent_manager import agent_manager

# ❌ 错误：使用全局变量需要在模块级别设置，容易导致循环导入
import sys
main_module = sys.modules.get('main')
agent_manager = getattr(main_module, 'agent_manager', None)
```

## 关键概念

### 1. 生命周期管理

- **初始化**：应用启动时在 `lifespan()` 中创建
- **运行**：应用运行期间可用
- **清理**：应用关闭时自动清理资源

### 2. 状态管理

agent_manager 管理以下状态：

```python
{
    "agents": Dict[str, SmartTradingAgent],     # 所有 Agent 实例
    "agent_tasks": Dict[str, asyncio.Task],     # 运行中的 Agent 任务
    "exchange_manager": ExchangeManager,        # 交易所管理器
    "order_manager": OrderManager,              # 订单管理器
    "position_manager": PositionManager         # 持仓管理器
}
```

## 常用方法

```python
# 获取指定 Agent
agent = agent_manager.get_agent(agent_id)

# 获取 Agent 状态
status = agent_manager.get_agent_status(agent_id)

# 启动 Agent
await agent_manager.start_agent(agent_id)

# 停止 Agent
await agent_manager.stop_agent(agent_id)

# 创建新 Agent
await agent_manager.create_agent(
    agent_id=agent_id,
    name=name,
    model_id=model_id,
    exchange_id=exchange_id,
    symbols=symbols,
    timeframe=timeframe,
    indicators=indicators,
    prompt=prompt,
    config=config
)
```

## 错误处理

```python
@router.get("/{agent_id}/status")
async def get_agent_status(agent_id: str, request: Request):
    try:
        agent_manager = get_agent_manager_from_request(request)
    except HTTPException:
        # agent_manager 未初始化
        raise
    
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found or not initialized")
    
    return agent_manager.get_agent_status(agent_id)
```

## 相关文件

- [agent_manager.py](agent_manager.py) - AgentManager 类定义
- [main.py](main.py) - FastAPI 应用入口
- [routes/agent_conversation_routes.py](routes/agent_conversation_routes.py) - 使用示例

## 注意事项

1. **必须在应用启动后使用**：agent_manager 只在 lifespan 启动事件后才初始化
2. **避免全局导入**：不要在模块级别导入 agent_manager，这会导致循环依赖
3. **使用 Request 对象**：通过 FastAPI 的 Request 对象获取 agent_manager 是最安全的方式
4. **异常处理**：始终检查 agent_manager 是否为 None，并捕获可能的异常
