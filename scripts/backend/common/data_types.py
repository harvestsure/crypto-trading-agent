# common/data_types.py
# 统一数据类型定义和枚举

from datetime import datetime
from enum import Enum, auto
import logging
from math import isclose
from typing import Dict, Any, List, Optional, Union, Callable, Awaitable
from dataclasses import dataclass, field
import time
from uuid import uuid4

class DataEventType(Enum):
    """数据事件类型枚举"""
    # 市场数据类型
    TICKER = auto()
    TRADE = auto()
    ORDERBOOK = auto()
    OHLCV = auto()
    
    # 账户数据类型 (未来扩展)
    BALANCE = auto()
    POSITION = auto()
    ORDER = auto()
    MY_TRADE = auto()
    
    # 其他数据类型 (未来扩展)
    FUNDING_RATE = auto()
    MARK_PRICE = auto()
    INDEX_PRICE = auto()
    LIQUIDATION = auto()
    
    # 系统事件
    CONNECTION_STATUS = auto()
    ERROR = auto()

@dataclass
class DataEvent:
    """统一数据事件结构"""
    event_type: DataEventType
    exchange_id: str
    symbol: str
    data: Union[Dict[str, Any], List[Dict[str, Any]]]
    timestamp: float
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

class DataEventFactory:
    """数据事件工厂类"""
    
    @staticmethod
    def create_ticker_event(exchange_id: str, symbol: str, ticker_data: Dict[str, Any]) -> DataEvent:
        """创建ticker事件"""
        return DataEvent(
            event_type=DataEventType.TICKER,
            exchange_id=exchange_id,
            symbol=symbol,
            data=ticker_data,
            timestamp=time.time()
        )
    
    @staticmethod
    def create_trade_event(exchange_id: str, symbol: str, trades_data: List[Dict[str, Any]]) -> DataEvent:
        """创建trade事件"""
        return DataEvent(
            event_type=DataEventType.TRADE,
            exchange_id=exchange_id,
            symbol=symbol,
            data=trades_data,
            timestamp=time.time()
        )
    
    @staticmethod
    def create_orderbook_event(exchange_id: str, symbol: str, orderbook_data: Dict[str, Any]) -> DataEvent:
        """创建orderbook事件"""
        return DataEvent(
            event_type=DataEventType.ORDERBOOK,
            exchange_id=exchange_id,
            symbol=symbol,
            data=orderbook_data,
            timestamp=time.time()
        )
    
    @staticmethod
    def create_ohlcv_event(exchange_id: str, symbol: str, timeframe: str, ohlcv_data: List) -> DataEvent:
        """创建OHLCV事件"""
        return DataEvent(
            event_type=DataEventType.OHLCV,
            exchange_id=exchange_id,
            symbol=symbol,
            data=ohlcv_data,
            timestamp=time.time(),
            metadata={'timeframe': timeframe}
        )
    
    @staticmethod
    def create_balance_event(exchange_id: str, balance_data: Dict[str, Any]) -> DataEvent:
        """创建余额事件"""
        return DataEvent(
            event_type=DataEventType.BALANCE,
            exchange_id=exchange_id,
            symbol='',  # 余额事件不特定于某个交易对
            data=balance_data,
            timestamp=time.time()
        )
    
    @staticmethod
    def create_position_event(exchange_id: str, symbol: str, position_data: Dict[str, Any]) -> DataEvent:
        """创建持仓事件"""
        return DataEvent(
            event_type=DataEventType.POSITION,
            exchange_id=exchange_id,
            symbol=symbol,
            data=position_data,
            timestamp=time.time()
        )
    
    @staticmethod
    def create_order_event(exchange_id: str, symbol: str, order_data: Dict[str, Any]) -> DataEvent:
        """创建订单事件"""
        return DataEvent(
            event_type=DataEventType.ORDER,
            exchange_id=exchange_id,
            symbol=symbol,
            data=order_data,
            timestamp=time.time()
        )
    
    @staticmethod
    def create_my_trade_event(exchange_id: str, symbol: str, trade_data: Dict[str, Any]) -> DataEvent:
        """创建我的交易事件"""
        return DataEvent(
            event_type=DataEventType.MY_TRADE,
            exchange_id=exchange_id,
            symbol=symbol,
            data=trade_data,
            timestamp=time.time()
        )
    
    @staticmethod
    def create_error_event(exchange_id: str, symbol: str, error_data: Dict[str, Any]) -> DataEvent:
        """创建错误事件"""
        return DataEvent(
            event_type=DataEventType.ERROR,
            exchange_id=exchange_id,
            symbol=symbol,
            data=error_data,
            timestamp=time.time()
        )

# 数据事件处理器类型定义

DataEventHandler = Callable[[DataEvent], Awaitable[None]]


class OrderSide(Enum):
    BUY = "buy"     # 买入
    SELL = "sell"   # 卖出

class OrderStatus(Enum):
    PENDING = "pending"     # 已提交，等待成交
    OPEN = "open"           # 部分成交，还有剩余
    FILLED = "filled"       # 完全成交
    CANCELLED = "cancelled" # 已取消
    REJECTED = "rejected"   # 被拒绝
    EXPIRED = "expired"     # 已过期

# Order status map
STR_STATUS: dict[str, OrderStatus] = {
    'N/A': OrderStatus.PENDING,
    "pending": OrderStatus.PENDING,
    "open": OrderStatus.OPEN,
    "closed": OrderStatus.FILLED,
    "canceled": OrderStatus.CANCELLED,
    "expired": OrderStatus.EXPIRED,
    "rejected": OrderStatus.REJECTED
}

class OrderType(Enum):
    MARKET = "market"       # 市价单
    LIMIT = "limit"         # 限价单
    STOP = "stop"           # 止损单
    STOP_LIMIT = "stop_limit" # 止损限价单

class OrderAction(Enum):
    OPEN_LONG = "open_long"         # 开多仓
    OPEN_SHORT = "open_short"       # 开空仓
    CLOSE_LONG = "close_long"       # 平多仓
    CLOSE_SHORT = "close_short"     # 平空仓

class PositionSide(Enum):
    LONG = "long"       # 多仓
    SHORT = "short"     # 空仓
    NET = "net"         # 单向持仓模式

@dataclass
class Position:
    """持仓数据结构"""
    exchange_id: str
    symbol: str
    side: PositionSide  # 'long' or 'short'
    contracts: float = 0.0  # 持仓数量(张数)
    contract_size: float = 1.0  # 合约面值
    entry_price: float = 0.0  # 平均开仓价
    mark_price: float = 0.0  # 标记价格
    liquidation_price: Optional[float] = None  # 强平价格
    leverage: int = 1  # 杠杆倍数
    margin: float = 0.0  # 保证金
    unrealized_pnl: float = 0.0  # 未实现盈亏
    realized_pnl: float = 0.0  # 已实现盈亏
    margin_ratio: float = 0.0  # 保证金率
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = self.created_at
    
    @property
    def position_value(self) -> float:
        """持仓价值"""
        return self.contracts * self.contract_size * self.mark_price
    
    @property
    def is_open(self) -> bool:
        """是否有持仓"""
        return abs(self.contracts) > 0
    
    @property
    def notional(self) -> float:
        """名义价值"""
        return self.contracts * self.contract_size * self.entry_price
    
    def update_from_dict(self, data: Dict[str, Any]):
        """从字典更新持仓数据(用于处理交易所返回的数据)"""
        self.contracts = float(data.get('contracts') or 0)
        self.entry_price = float(data.get('entryPrice') or 0)
        self.mark_price = float(data.get('markPrice') or 0)
        liquidation_price = data.get('liquidationPrice')
        self.liquidation_price = float(liquidation_price) if liquidation_price else None
        leverage = data.get('leverage')
        self.leverage = int(leverage) if leverage is not None else 1
        self.margin = float(data.get('initialMargin') or 0)
        self.unrealized_pnl = float(data.get('unrealizedPnl') or 0)
        self.realized_pnl = float(data.get('realizedPnl') or 0)
        self.margin_ratio = float(data.get('marginRatio') or 0)
        self.updated_at = datetime.now()

@dataclass
class OrderFee:
    """订单手续费数据结构"""
    cost: float = 0.0  # 手续费总额
    currency: Optional[str] = None  # 手续费币种（从交易所数据中获取）
    rate: Optional[float] = None  # 手续费率（百分比）
    
    @staticmethod
    def from_dict(fee_dict: Dict[str, Any]) -> 'OrderFee':
        """从字典创建手续费对象"""
        if not fee_dict:
            return OrderFee()
        return OrderFee(
            cost=float(fee_dict.get('cost') or 0),
            currency=fee_dict.get('currency'),  # 直接使用交易所返回的币种
            rate=float(fee_dict.get('rate')) if fee_dict.get('rate') is not None else None
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'cost': self.cost,
            'currency': self.currency,
            'rate': self.rate
        }


@dataclass
class Order:
    """
    统一订单数据结构 - 兼容CCXT和各大交易所格式
    支持OKX、Binance等交易所的订单数据
    """
    exchange_id: str  # 交易所ID
    order_id: str  # 交易所返回的订单ID
    clOrdId: str  # 客户端订单ID（用于去重）
    symbol: str  # 交易对（如 'BTC/USDT'）
    order_type: OrderType  # 订单类型：MARKET, LIMIT, STOP, STOP_LIMIT
    side: OrderSide  # 订单方向：BUY, SELL
    quantity: float  # 原始订单数量
    pos_side: Optional[PositionSide] = None  # 持仓方向：long, short, net
    action: Optional[OrderAction] = None  # 订单操作：OPEN_LONG, OPEN_SHORT, CLOSE_LONG, CLOSE_SHORT

    local_order: bool = True  # 是否为本地创建的订单（非交易所下单）
    
    # === 基础字段 ===
    price: Optional[float] = None  # 订单价格
    filled_quantity: float = 0.0  # 已成交数量
    average_price: Optional[float] = None  # 平均成交价格
    status: OrderStatus = OrderStatus.PENDING  # 订单状态
    
    # === 止损/止盈相关 ===
    stop_price: Optional[float] = None  # 止损/止盈触发价格
    
    # === 额外信息 ===
    strategy_id: Optional[str] = None  # 策略ID
    
    # === 时间戳 ===
    timestamp: Optional[float] = None  # 订单创建时间戳（秒）
    created_at: datetime = field(default_factory=datetime.now)  # 订单创建时间
    updated_at: datetime = field(default_factory=datetime.now)  # 订单更新时间
    expires_at: Optional[datetime] = None  # 订单过期时间
    
    # === 成本与手续费 ===
    cost: float = 0.0  # 订单总成本 = quantity * price
    fee: 'OrderFee' = field(default_factory=OrderFee)  # 手续费信息
    
    # === CCXT兼容字段 ===
    info: Dict[str, Any] = field(default_factory=dict)  # 交易所原始响应数据
    fee_currency: Optional[str] = None  # 手续费币种（从交易所数据中获取）
    trades: List[Dict[str, Any]] = field(default_factory=list)  # 该订单的成交明细列表
    
    # === 特定字段 ===
    reduce_only: bool = False  # 是否仅平仓（OKX/Binance）
    post_only: bool = False  # 是否仅做Maker（Binance）
    
    # === Binance特定字段 ===
    working_type: Optional[str] = None  # Working type (Binance)
    
    def __post_init__(self):
        """初始化处理"""
        if self.clOrdId is None:
            self.clOrdId = uuid4().hex
        
        if self.timestamp is None:
            self.timestamp = time.time()
        
        if isinstance(self.fee, dict):
            self.fee = OrderFee.from_dict(self.fee)
    
    @property
    def remaining_quantity(self) -> float:
        """剩余未成交数量"""
        return self.quantity - self.filled_quantity
    
    @property
    def is_active(self) -> bool:
        """是否为活跃订单"""
        return self.status in [OrderStatus.PENDING, OrderStatus.OPEN]
    
    @property
    def is_closed(self) -> bool:
        """是否已关闭"""
        # 先检查明确的非FILLED关闭状态(快速路径)
        if self.status in [OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED]:
            return True
        # 再检查FILLED状态或实际完全成交(处理状态延迟)
        return self.status == OrderStatus.FILLED or self.is_fully_filled
    
    @property
    def fill_ratio(self) -> float:
        """成交比例"""
        if self.quantity <= 0:
            return 0.0
        return min(1.0, self.filled_quantity / self.quantity)
    
    @property
    def is_fully_filled(self) -> bool:
        """是否完全成交"""
        if self.quantity <= 0:
            return False
        
        # 使用相对容差比较，处理浮点数精度
        return isclose(self.filled_quantity, self.quantity, rel_tol=1e-9)

    @property
    def is_partially_filled(self) -> bool:
        """是否部分成交"""
        if self.quantity <= 0:
            return False
        
        # 已成交数量 > 0 且未完全成交
        return (self.filled_quantity > 0 and 
                not self.is_fully_filled)
    
    def update_from_ccxt_order(self, ccxt_order: Dict[str, Any]):
        """
        从CCXT订单数据更新
        
        Args:
            ccxt_order: CCXT返回的订单字典
        """
        # 防御性更新：只有当新值不为 None 时才更新
        if ccxt_order.get('id'):
            self.order_id = ccxt_order['id']
        
        # 更新 clOrdId（客户端订单ID）
        new_clOrdId = ccxt_order.get('clientOrderId', ccxt_order.get('clOrdId')) or ccxt_order.get('info', {}).get('clOrdId')
        if new_clOrdId:
            self.clOrdId = new_clOrdId
        
        # 更新 symbol - 只有当新值不为 None 时才更新
        if ccxt_order.get('symbol'):
            self.symbol = ccxt_order['symbol']
        
        # 更新时间戳
        if ccxt_order.get('timestamp'):
            self.timestamp = ccxt_order['timestamp']
        
        # 更新订单类型和方向（防御性处理 None 值）
        order_type_str = (ccxt_order.get('type') or '').lower()
        if order_type_str in ['market', 'limit', 'stop', 'stop_limit']:
            try:
                self.order_type = OrderType[order_type_str.upper()]
            except (KeyError, ValueError):
                pass
        
        side_str = (ccxt_order.get('side') or '').lower()
        if side_str in ['buy', 'sell']:
            try:
                self.side = OrderSide[side_str.upper()]
            except (KeyError, ValueError):
                pass
        
        # 更新数量和价格
        self.quantity = float(ccxt_order.get('amount') or self.quantity)
        if ccxt_order.get('price') is not None:
            self.price = float(ccxt_order.get('price'))
        
        self.filled_quantity = float(ccxt_order.get('filled') or 0)
        
        # 更新平均成交价格
        if ccxt_order.get('average') is not None:
            self.average_price = float(ccxt_order.get('average'))
        
        # 更新成本
        if ccxt_order.get('cost') is not None:
            self.cost = float(ccxt_order.get('cost'))
        else:
            self.cost = self.filled_quantity * (self.average_price or self.price or 0)
        
        # 更新订单状态（防御性处理 None 值）
        status_str = (ccxt_order.get('status') or '').lower()
        if status_str in STR_STATUS:
            self.status = STR_STATUS[status_str]
        
        # 更新手续费
        if ccxt_order.get('fee'):
            self.fee = OrderFee.from_dict(ccxt_order.get('fee'))
            if self.fee.currency:
                self.fee_currency = self.fee.currency
        
        # 保存原始数据
        self.info = ccxt_order.get('info', {})
        
        # 更新时间戳
        self.updated_at = datetime.now()
        
        # 提取交易所特定字段
        self._extract_exchange_specific_fields(ccxt_order)
    
    def _extract_exchange_specific_fields(self, ccxt_order: Dict[str, Any]):
        """提取交易所特定的字段"""
        info = ccxt_order.get('info', {})
        
        if info.get('posSide'):
            self.pos_side = info.get('posSide')
        
        if info.get('reduceOnly'):
            reduce_only_str = str(info.get('reduceOnly')).lower()
            self.reduce_only = reduce_only_str in ['true', '1', 'yes']
        
        # Binance特定字段
        if info.get('workingType'):
            self.working_type = info.get('workingType')
        
        # Binance postOnly字段
        if info.get('postOnly'):
            post_only_str = str(info.get('postOnly')).lower()
            self.post_only = post_only_str in ['true', '1', 'yes']
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'exchange_id': self.exchange_id,
            'order_id': self.order_id,
            'clOrdId': self.clOrdId,
            'symbol': self.symbol,
            'order_type': self.order_type.name if self.order_type else None,
            'side': self.side.name if self.side else None,
            'quantity': self.quantity,
            'filled_quantity': self.filled_quantity,
            'price': self.price,
            'average_price': self.average_price,
            'cost': self.cost,
            'status': self.status.name if self.status else None,
            'fee': self.fee.to_dict() if self.fee else None,
            'timestamp': self.timestamp,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'strategy_id': self.strategy_id,
            'pos_side': self.pos_side,
            'action': self.action.value if self.action else None,
            'reduce_only': self.reduce_only,
            'post_only': self.post_only,
            'working_type': self.working_type,
        }
    
    def __str__(self) -> str:
        """字符串表示"""
        return (f"Order({self.exchange_id}/{self.symbol} {self.side.value} "
                f"{self.filled_quantity:.2f}/{self.quantity:.2f} @ "
                f"{self.average_price or self.price or 'N/A'} - {self.status.value})")
    

