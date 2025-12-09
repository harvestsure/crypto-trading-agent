"""
Agent 基类和管理器
"""

from collections import deque
import json
import asyncio
import logging
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
from uuid import uuid4
from pydantic import BaseModel
from common.data_types import DataEvent, DataEventType, Order
import pandas as pd


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

        # 数据存储 - 保持原有结构以兼容现有策略
        self.ticker_history = deque(maxlen=100)
        self.trade_history = deque(maxlen=500)
        self.orderbook_history = deque(maxlen=50)
        self.balance_history = deque(maxlen=50)
        self.position_history = deque(maxlen=100)
        self.order_history = deque(maxlen=200)
        self.my_trade_history = deque(maxlen=200)
        self.last_price = 0.0

        self.ohlcv_data = {} # {timeframe: DataFrame}
        self.max_ohlcv_length = 500  # 默认最大OHLCV数据长度

    
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

    async def on_data_event(self, event: DataEvent):
        """
        统一数据事件处理入口
        
        Args:
            event: 数据事件对象
        """
        try:
            # 验证事件是否属于当前策略
            if event.exchange_id != self.exchange_id:
                return
            
            # 对于非全局事件，检查symbol是否匹配
            if event.symbol and event.symbol != self.symbol:
                return
            
            # 根据事件类型分发到具体处理方法
            handler_map = {
                DataEventType.TICKER: self._handle_ticker_event,
                DataEventType.TRADE: self._handle_trade_event,
                DataEventType.ORDERBOOK: self._handle_orderbook_event,
                DataEventType.OHLCV: self._handle_ohlcv_event,
                DataEventType.BALANCE: self._handle_balance_event,
                DataEventType.POSITION: self._handle_position_event,
                DataEventType.ORDER: self._handle_order_event,
                DataEventType.MY_TRADE: self._handle_my_trade_event,
                DataEventType.ERROR: self._handle_error_event,
            }
            
            handler = handler_map.get(event.event_type)
            if handler:
                await handler(event)
            else:
                logging.warning(f"未处理的事件类型: {event.event_type}")
           
        except Exception as e:
            logging.error(f"处理数据事件失败 {self.name}: {e}", exc_info=True)
    
    # === 具体事件处理方法 ===
    
    async def _handle_ticker_event(self, event: DataEvent):
        """处理ticker事件"""
        ticker_data = event.data
        ticker_data['received_at'] = event.timestamp
        self.ticker_history.append(ticker_data)
        
        # 调用子类的ticker处理逻辑
        await self._process_ticker(ticker_data)
    
    async def _handle_trade_event(self, event: DataEvent):
        """处理trade事件"""
        trades = event.data
        for trade_data in trades:
            trade_data['received_at'] = event.timestamp
            self.trade_history.append(trade_data)
            await self._process_trade(trade_data)
    
    async def _handle_orderbook_event(self, event: DataEvent):
        """处理orderbook事件"""
        orderbook_data = event.data
        orderbook_data['received_at'] = event.timestamp
        self.orderbook_history.append(orderbook_data)
        
        await self._process_orderbook(orderbook_data)
    
    async def _handle_ohlcv_event(self, event: DataEvent):
        """处理OHLCV事件"""
        timeframe = event.metadata.get('timeframe', '1m')
        ohlcv_data = event.data
      
        # 更新OHLCV数据存储
        get_new_kline = self._update_ohlcv_data(timeframe, ohlcv_data)
        if get_new_kline:
            logging.info(f"添加新K线 {self.name} {timeframe}")
        
        await self._process_ohlcv(timeframe, ohlcv_data)
    
    async def _handle_balance_event(self, event: DataEvent):
        """处理余额事件"""
        balance_data = event.data
        balance_data['received_at'] = event.timestamp
        self.balance_history.append(balance_data)
        
        await self._process_balance(balance_data)
    
    async def _handle_position_event(self, event: DataEvent):
        """处理持仓事件"""
        position_data = event.data
        position_data['received_at'] = event.timestamp
        self.position_history.append(position_data)
        
        await self._process_position(position_data)
    
    async def _handle_order_event(self, event: DataEvent):
        """处理订单事件"""
        order_data = event.data
        order_data['received_at'] = event.timestamp
        self.order_history.append(order_data)

        order = None
        try:
            # 尝试从order_id查找现有订单
            order_id = order_data.get('id') or order_data.get('order_id')
            existing_order = self.order_manager.orders.get(order_id) if order_id else None
            
            if existing_order:
                order = existing_order
                # 更新现有订单
                order.filled_quantity = float(order_data.get('filled') or 0)
                status_str = order_data.get('status', '').lower()
                if status_str in STR_STATUS:
                    order.status = STR_STATUS[status_str]

                # 调用order_manager的更新方法
                await self.order_manager.update_order_status(
                    order_id=order.order_id,
                    status=order.status,
                    filled_quantity=order.filled_quantity
                )
            else:
                # 创建新Order对象
                order = Order(
                    exchange_id=self.exchange_id,
                    order_id=order_data.get('id', order_data.get('order_id', 'N/A')),
                    clOrdId=order_data.get('clientOrderId', order_data.get('clOrdId')) or order_data.get('info', {}).get('clOrdId', 'N/A'),
                    symbol=self.symbol,
                    order_type=OrderType.LIMIT,  # 默认值，会被覆盖
                    side=OrderSide.BUY,  # 默认值，会被覆盖
                    quantity=float(order_data.get('amount', 0)),
                    local_order=False,  # 交易所下单
                )
                order.update_from_ccxt_order(order_data)    

                await self.position_manager.sync_positions_from_exchange(self.exchange_id)
            
            logging.info(f"🎁🎁 订单更新 {self.name}: "
                        f"ID={order.order_id}, "
                        f"状态={order.status.name}, "
                        f"类型={order.order_type.name}, "
                        f"方向={order.side.value}, "
                        f"数量={order.filled_quantity}/{order.quantity}, "
                        f"价格={order.average_price or order.price or 'N/A'}")
            
            # 同步订单到 SharedState
            if order:                        
                await self._process_order(order)
                await self.shared_state.add_order_history_non_blocking(order.to_dict())
        
        except Exception as e:
            logging.error(f"处理订单数据失败 {self.name}: {e}", exc_info=True)

    
    async def _handle_my_trade_event(self, event: DataEvent):
        """处理我的交易事件"""
        trade_data = event.data
        trade_data['received_at'] = event.timestamp
        self.my_trade_history.append(trade_data)
        
        await self._process_my_trade(trade_data)
    
    async def _handle_error_event(self, event: DataEvent):
        """处理错误事件"""
        error_data = event.data
        logging.error(f"收到错误事件 {self.name} - {error_data}")
        
        await self._process_error(error_data)
    
    # === 子类可重写的处理方法 ===
    
    async def _process_ticker(self, ticker_data: Dict[str, Any]):
        """子类可重写的ticker处理逻辑"""
        self.last_price = ticker_data.get('last') or ticker_data.get('close')
    
    async def _process_trade(self, trade_data: Dict[str, Any]):
        """子类可重写的trade处理逻辑"""
        pass
    
    async def _process_orderbook(self, orderbook_data: Dict[str, Any]):
        """子类可重写的orderbook处理逻辑"""
        pass
    
    async def _process_ohlcv(self, timeframe: str, ohlcv_data: List):
        """子类可重写的OHLCV处理逻辑"""
        pass
    
    async def _process_balance(self, balance_data: Dict[str, Any]):
        """子类可重写的余额处理逻辑"""
        # 计算总权益并更新权益曲线
        pass
    
    async def _process_position(self, position_data: Dict[str, Any]):
        """子类可重写的持仓处理逻辑"""
        logging.debug(f"持仓更新 {self.name}: "
                    f"方向={position_data.get('side', 'N/A')}, "
                    f"数量={position_data.get('size', 0)}, "
                    f"未实现盈亏={position_data.get('unrealizedPnl', 0)}")
    
    async def _process_order(self, order: Order):
        """子类可重写的订单处理逻辑"""
        pass

    async def _process_my_trade(self, trade_data: Dict[str, Any]):
        """子类可重写的我的交易处理逻辑"""
        # 提取手续费
        fee_value = 0.0
        fee_obj = trade_data.get('fee')
        if fee_obj is not None:
            if isinstance(fee_obj, dict):
                # fee 是字典格式: {'cost': 0.05, 'currency': 'USDT'}
                fee_value = float(fee_obj.get('cost', 0) or fee_obj.get('value', 0) or 0)
            else:
                # fee 是直接数值
                try:
                    fee_value = float(fee_obj)
                except Exception:
                    fee_value = 0.0
        else:
            # No fee object found in trade_data
            logging.debug(f"[_process_my_trade] No fee in trade_data for {self.symbol}: {trade_data.get('id')}")
        
        # 记录手续费到 shared_state
        if fee_value > 0:
            try:
                # Get timestamp and convert milliseconds to seconds if needed
                ts = trade_data.get('timestamp')
                if ts and ts > 1e10:
                    ts = ts / 1000
                
                fee_detail = {
                    "exchange_id": self.exchange_id,
                    "symbol": self.symbol,
                    "side": trade_data.get('side'),
                    "amount": trade_data.get('amount'),
                    "price": trade_data.get('price'),
                    "fee": fee_value,
                    "timestamp": ts,
                    "pnl": 0,  # 手续费记录不包含 pnl，pnl 由 position_manager 负责
                }
                await self.shared_state.add_trade_detail_non_blocking(fee_detail)
                logging.info(f"✅ 记录手续费: {self.symbol} {fee_value:.6f} USDT")
            except Exception as e:
                logging.warning(f"记录手续费失败: {e}")
        else:
            logging.debug(f"[_process_my_trade] Fee is 0 for {self.symbol}, fee_obj={fee_obj}")
        
        try:
            order_id = trade_data.get('order') or trade_data.get('id')
            client_order_id = trade_data.get('clientOrderId') or trade_data.get('info', {}).get('clOrdId')
            
            # 优先通过client_order_id查找订单（因为占位订单可能还在使用临时order_id）
            existing_order = None
            if client_order_id:
                existing_order = await self.order_manager.get_order_by_client_id(client_order_id)
            
            # 如果通过client_order_id找不到，再通过order_id查找
            if not existing_order and order_id:
                async with self.order_manager._order_lock:
                    existing_order = self.order_manager.orders.get(order_id)
            
            # 如果找不到订单，等待一小段时间后重试（可能占位订单正在创建）
            if not existing_order and (client_order_id or order_id):
                await asyncio.sleep(0.05)  # 等待50ms
                if client_order_id:
                    existing_order = await self.order_manager.get_order_by_client_id(client_order_id)
                if not existing_order and order_id:
                    async with self.order_manager._order_lock:
                        existing_order = self.order_manager.orders.get(order_id)
            
            logging.info(f"💹💹 交易执行 {self.name}: "
                        f"order={order_id or 'N/A'}(ID:{trade_data.get('id', 'N/A')}), "
                        f"方向={trade_data.get('side', 'N/A')}, "
                        f"数量={trade_data.get('amount', 0)}, "
                        f"价格={trade_data.get('price', 0)}, "
                        f"手续费={fee_value}")
            
            if existing_order:
                order = existing_order

                amount = float(trade_data.get('amount', 0))
                price = float(trade_data.get('price', 0))

                await self.order_manager.add_order_filled_quantity(
                    order_id=order.order_id,
                    filled_quantity=amount
                )
                
                # 市场订单特殊处理：成交后立即检查是否应标记为完成
                # Binance市场订单瞬间成交，但订单事件可能晚到，此时需要主动更新状态
                if order.order_type == OrderType.MARKET:
                    if order.is_fully_filled:
                        # 订单已完全成交，确保状态为FILLED
                        if order.status != OrderStatus.FILLED:
                            order.status = OrderStatus.FILLED
                            await self.order_manager.update_order_status(
                                order_id=order.order_id,
                                status=OrderStatus.FILLED,
                                filled_quantity=order.filled_quantity
                            )
                            logging.info(f"🔧 市场订单成交后标记完成: {order.order_id} ({order.filled_quantity}/{order.quantity})")
                    else:
                        # 🔑 市场订单部分成交警告：不应频繁发生
                        # 市场订单通常会瞬间完全成交，部分成交可能意味着流动性不足或订单被拆分
                        logging.warning(
                            f"⚠️ 市场订单部分成交: {order.order_id} "
                            f"已成交={order.filled_quantity}/{order.quantity} "
                            f"({order.fill_ratio*100:.1f}%), 等待后续成交"
                        )
                        # 不要主动标记为FILLED，等待交易所发送订单状态更新事件

                # 调用position_manager更新持仓
                await self.position_manager.update_position_from_trade(
                    exchange_id=self.exchange_id,
                    symbol=self.symbol,
                    side=order.side,
                    quantity=amount,
                    price=price,
                    pos_side=order.pos_side,
                    reduce_only=order.reduce_only,
                )
            else:
                await self.position_manager.sync_positions_from_exchange(self.exchange_id)

        except Exception as e:
            logging.error(f"更新持仓失败: {e}", exc_info=True)

        # === 保持原有的工具方法以兼容现有策略 ===
    
    def _update_ohlcv_data(self, timeframe: str, ohlcv_data: List) -> bool:
        """更新OHLCV数据存储"""
        if not ohlcv_data:
            return False
        
        # 处理多根K线数据
        if isinstance(ohlcv_data[0], list):
            # 多根K线数据
            new_data_list = ohlcv_data
        else:
            # 单根K线数据
            new_data_list = [ohlcv_data]

        get_new_kline = False
        
        # 创建DataFrame
        new_df = pd.DataFrame(new_data_list, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        new_df['timestamp'] = pd.to_datetime(new_df['timestamp'], unit='ms')
        new_df.set_index('timestamp', inplace=True)
        
        if timeframe not in self.ohlcv_data:
            # 初始化存储
            self.ohlcv_data[timeframe] = new_df
        else:
            # 获取现有数据
            existing_df = self.ohlcv_data[timeframe]
            
            # 逐个处理新数据点
            for timestamp, new_row in new_df.iterrows():
                if timestamp in existing_df.index:
                    # 更新现有行
                    existing_df.loc[timestamp] = new_row.values
                else:
                    # 添加新行
                    existing_df = pd.concat([existing_df, pd.DataFrame([new_row], index=[timestamp])])
                    get_new_kline = True
            
            # 按时间戳排序并去重（保留最后一个）
            existing_df = existing_df[~existing_df.index.duplicated(keep='last')]
            existing_df = existing_df.sort_index()
            
            # 更新存储
            self.ohlcv_data[timeframe] = existing_df
        
        # 保持数据长度限制
        if len(self.ohlcv_data[timeframe]) > self.max_ohlcv_length:
            self.ohlcv_data[timeframe] = self.ohlcv_data[timeframe].iloc[-self.max_ohlcv_length:]
        
        return get_new_kline