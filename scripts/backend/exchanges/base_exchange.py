# exchanges/base_exchange.py
# 优化后的交易所基类 - 使用统一数据事件接口

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Set, Optional
from common.data_types import DataEvent, DataEventType, DataEventHandler, OrderType, OrderSide


class BaseExchange(ABC):
    """
    优化后的交易所抽象基类
    - 使用统一的数据事件接口
    - 支持灵活的数据类型订阅
    - 便于扩展新的数据类型
    """
    
    def __init__(self, exchange_id: str, api_keys: Dict = None, config: Dict = None, shared_state = None):
        self.exchange_id = exchange_id
        self.api_keys = api_keys or {}
        self.config = config or {}
        self.shared_state = shared_state
        self.ccxt_exchange = None

        self.global_tasks: List[asyncio.Task] = []
        
        # 支持的数据类型
        self.supported_data_types: Set[DataEventType] = {
            DataEventType.TICKER,
            DataEventType.TRADE,
            DataEventType.ORDERBOOK,
            DataEventType.OHLCV,
            DataEventType.BALANCE,
            DataEventType.POSITION,
            DataEventType.ORDER,
            DataEventType.MY_TRADE,
        }
        
        # 当前订阅的数据类型和交易对
        self.active_subscriptions: Dict[DataEventType, Set[str]] = {}
        
        # 统一数据事件处理器
        self.data_event_handler: DataEventHandler = None
    
    @abstractmethod
    async def initialize(self):
        """初始化交易所连接和设置"""
        pass

    @abstractmethod
    async def close(self):
        """关闭交易所连接"""
        logging.info("🔻 Cancelling background tasks...")
        for task in self.global_tasks:
            if not task.done():
                task.cancel()

        # 等待任务真正结束
        await asyncio.gather(*self.global_tasks, return_exceptions=True)
        logging.info("✅ All tasks cancelled.")
    
    @abstractmethod
    async def set_leverage_for_all_symbols(self, leverage: int, symbols: List[str]):
        """为所有交易对设置杠杆"""
        pass
    
    @abstractmethod
    async def set_leverage(self, leverage: int, symbol: str, posSide: str):
        """为指定交易对和仓位方向设置杠杆"""
        pass

    @abstractmethod
    async def set_position_mode(self, hedge_mode: bool):
        """设置持仓模式"""
        pass
    
    @abstractmethod
    async def fetch_dynamic_symbols(self) -> List[str]:
        """获取动态交易对列表"""
        pass

    @abstractmethod
    async def fetch_ohlcv(self, symbol: str, timeframe='1m', since: Optional[int] = None, limit: Optional[int] = None, params={}) -> List[list]:
        """获取动态交易对的K线数据"""
        pass

    @abstractmethod
    async def fetch_ticker(self, symbol: str, params={}) -> Optional[Dict]:
        """获取动态交易对的Ticker数据"""
        pass

    @abstractmethod
    async def get_market_info(self, symbol: str) -> Optional[Dict]:
        """
        获取交易对的市场信息
        
        Returns:
            {
                'contract_size': float,      # 合约面值（如 0.01 ETH）
                'contract_size_currency': str, # 合约面值币种（如 'ETH'）
                'price_precision': float,    # 价格精度（如 0.1）
                'amount_precision': float,   # 数量精度（如 1）
                'min_amount': float,         # 最小下单量
                'min_cost': float,          # 最小下单金额（可选）
                'max_leverage': int,        # 最大杠杆倍数
                'settlement_currency': str, # 结算币种
                'type': str,                # 合约类型：'swap', 'future', 'spot'
            }
        """
        pass
    
    # === 统一订阅接口 ===
    
    def set_data_event_handler(self, handler: DataEventHandler):
        """设置统一数据事件处理器"""
        self.data_event_handler = handler
    
    async def subscribe_data(self, data_types: List[DataEventType], symbols: List[str]):
        """
        订阅指定数据类型和交易对
        
        Args:
            data_types: 要订阅的数据类型列表
            symbols: 要订阅的交易对列表
        """
        # 收集所有需要执行的订阅任务
        subscribe_tasks = []
        unsubscribe_tasks = []
        
        for data_type in data_types:
            if data_type not in self.supported_data_types:
                raise ValueError(f"数据类型 {data_type} 不被支持")
            
            # 更新活跃订阅
            if data_type not in self.active_subscriptions:
                self.active_subscriptions[data_type] = set()
            
            current_symbols = self.active_subscriptions[data_type]
            new_symbols = set(symbols)
            
            # 计算需要添加和移除的交易对
            symbols_to_add = new_symbols - current_symbols
            symbols_to_remove = current_symbols - new_symbols
            
            # 收集订阅任务（稍后并行执行）
            if symbols_to_add:
                subscribe_tasks.append(self._start_data_subscription(data_type, list(symbols_to_add)))
            
            if symbols_to_remove:
                unsubscribe_tasks.append(self._stop_data_subscription(data_type, list(symbols_to_remove)))
            
            # 更新活跃订阅记录
            self.active_subscriptions[data_type] = new_symbols
        
        # 并行执行所有订阅和取消订阅操作
        all_tasks = subscribe_tasks + unsubscribe_tasks
        if all_tasks:
            await asyncio.gather(*all_tasks, return_exceptions=True)
    
    async def unsubscribe_data(self, data_types: List[DataEventType], symbols: List[str] = None):
        """
        取消订阅指定数据类型
        
        Args:
            data_types: 要取消订阅的数据类型列表
            symbols: 要取消订阅的交易对列表，如果为None则取消所有
        """
        for data_type in data_types:
            if data_type not in self.active_subscriptions:
                continue
            
            if symbols is None:
                # 取消所有交易对的订阅
                symbols_to_remove = list(self.active_subscriptions[data_type])
                self.active_subscriptions[data_type].clear()
            else:
                # 取消指定交易对的订阅
                symbols_to_remove = [s for s in symbols if s in self.active_subscriptions[data_type]]
                for symbol in symbols_to_remove:
                    self.active_subscriptions[data_type].discard(symbol)
            
            if symbols_to_remove:
                await self._stop_data_subscription(data_type, symbols_to_remove)
    
    # === 子类需要实现的具体订阅方法 ===
    
    @abstractmethod
    async def _start_data_subscription(self, data_type: DataEventType, symbols: List[str]):
        """开始订阅指定数据类型和交易对"""
        pass
    
    @abstractmethod
    async def _stop_data_subscription(self, data_type: DataEventType, symbols: List[str]):
        """停止订阅指定数据类型和交易对"""
        pass
    
    # === 数据事件发送方法 ===

    async def _create_global_task(self, coro):
        """添加全局任务并跟踪"""
        task = asyncio.create_task(coro)
        self.global_tasks.append(task)

        # 添加完成回调，确保后台任务的异常被记录，避免 "Future exception was never retrieved" 的警告
        def _task_done_callback(t: asyncio.Task):
            try:
                exc = t.exception()
                if exc:
                    logging.error(f"Background task raised exception: {exc}", exc_info=True)
            except asyncio.CancelledError:
                # 任务被取消，忽略
                pass
            except Exception as cb_err:
                logging.error(f"Error while handling task completion: {cb_err}", exc_info=True)

        task.add_done_callback(_task_done_callback)
        return task
    
    async def _emit_data_event(self, event: DataEvent):
        """发送数据事件到处理器"""
        if self.data_event_handler:
            await self.data_event_handler(event)
    
    # === 交易相关方法 (保持原有接口) ===
    
    @abstractmethod
    def check_order_viability(self, balance: Dict, symbol: str, order_type: str, 
                            side: str, amount: float, price: float, leverage: int) -> tuple[bool, str]:
        """检查订单可行性"""
        pass
    
    @abstractmethod
    async def create_order(self, symbol: str, type: OrderType, side: OrderSide, amount: float, 
                          price: float = None, params: Dict = {}, post_only: bool = False):
        """创建订单"""
        pass
    
    @abstractmethod
    async def create_orders(self, orders: List[Dict]) -> List[Dict]:
        """
        批量创建订单
        
        Args:
            orders: 订单列表，每个订单包含:
                {
                    'symbol': str,
                    'type': OrderType,
                    'side': OrderSide,
                    'amount': float,
                    'price': float (可选),
                    'params': Dict (可选),
                    'post_only': bool (可选)
                }
        
        Returns:
            创建成功的订单列表
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str):
        """取消订单"""
        pass

    @abstractmethod
    async def cancel_orders(self, ids, symbol: str = None, params={}):
        """取消多个订单"""
        pass

    @abstractmethod
    async def edit_order(self, order_id: str, symbol: str, type: OrderType, side: OrderSide, amount: float, price: float = None, params: Dict = {}):
        """修改订单"""
        pass

    @abstractmethod
    async def fetch_order(self, order_id: str, symbol: str, params: Dict = {}):
        """查询订单"""
        pass

    @abstractmethod
    async def fetch_positions(self, symbols: Optional[List[str]] = None, params={}) -> List[Dict]:
        """获取持仓信息"""
        pass
        
    # === 状态查询方法 ===
    
    def get_supported_data_types(self) -> Set[DataEventType]:
        """获取支持的数据类型"""
        return self.supported_data_types.copy()
    
    def get_active_subscriptions(self) -> Dict[DataEventType, Set[str]]:
        """获取当前活跃的订阅"""
        return {k: v.copy() for k, v in self.active_subscriptions.items()}
    
    def is_subscribed(self, data_type: DataEventType, symbol: str = None) -> bool:
        """检查是否已订阅指定数据类型"""
        if data_type not in self.active_subscriptions:
            return False
        
        if symbol is None:
            return len(self.active_subscriptions[data_type]) > 0
        
        return symbol in self.active_subscriptions[data_type]
