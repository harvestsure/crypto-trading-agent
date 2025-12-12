import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict
import uuid
from dataclasses import dataclass
from risk_manager import RiskManager
from exchange_manager import ExchangeManager
from position_manager import PositionManager
from common.data_types import Order, OrderAction, OrderType, OrderStatus, OrderSide, PositionSide



@dataclass
class PortfolioConstraints:
    """投资组合约束"""
    max_total_orders: int = 100  # 总订单数量限制
    max_symbol_orders: int = 5   # 单个symbol订单数量限制
    max_position_value: float = 1000000  # 最大持仓价值
    max_symbol_exposure: float = 100000   # 单个symbol最大风险暴露
    daily_order_limit: int = 200          # 每日订单限制

class SymbolGroup:
    """Symbol分组管理"""
    
    def __init__(self, name: str, symbols: List[str], constraints: PortfolioConstraints):
        self.name = name
        self.symbols = set(symbols)
        self.constraints = constraints
        self.order_count_today = 0
        self.last_reset_date = datetime.now().date()

# id_key = f"{exchange_id}:{symbol}"
class OrderManager:
    """多symbol订单管理器"""
    
    def __init__(self, exchange_manager: ExchangeManager, risk_manager: RiskManager, position_manager: PositionManager):
        self.exchange_manager: ExchangeManager = exchange_manager
        self.risk_manager: RiskManager = risk_manager
        self.position_manager: PositionManager = position_manager

        self.orders: Dict[str, Order] = {}  # 所有订单 order_id -> Order
        self.client_order_id_map: Dict[str, str] = {}  # client_order_id -> order_id 映射
        self.symbol_orders: Dict[str, List[Order]] = defaultdict(list)  # {exchange_id}:{symbol} -> 订单列表
        self.group_orders: Dict[str, List[Order]] = defaultdict(list)   # 分组 -> 订单列表
        self.pending_orders: Dict[str, List[Order]] = defaultdict(list) # {exchange_id}:{symbol} -> pending订单
        self.open_orders: Dict[str, List[Order]] = defaultdict(list)    # {exchange_id}:{symbol} -> open订单
        
        # 分组管理
        self.symbol_groups: Dict[str, SymbolGroup] = {}
        self.symbol_to_group: Dict[str, str] = {}  # {exchange_id}:{symbol} -> 分组名
        
        # 全局约束
        self.global_constraints = PortfolioConstraints()
        self._order_lock = asyncio.Lock()
        
        # 性能优化
        self._symbol_cache = {}  # symbol缓存
        self._order_priority_queue = []  # 订单优先级队列

        logging.info("订单管理模块已初始化。")
        
    async def add_symbol_group(self, group_name: str, symbols: List[str], 
                             constraints: PortfolioConstraints = None):
        """添加symbol分组"""
        async with self._order_lock:
            if constraints is None:
                constraints = self.global_constraints
            
            group = SymbolGroup(group_name, symbols, constraints)
            self.symbol_groups[group_name] = group
            
            for symbol in symbols:
                self.symbol_to_group[symbol] = group_name
            logging.info(f"添加分组 {group_name}: {len(symbols)}个symbol")

    async def create_order_advanced(self, 
                                exchange_id: str, 
                                symbol: str, 
                                order_type: OrderType, 
                                action: OrderAction,
                                amount: float,
                                price: float = None,
                                sl_price: float = None,
                                tp_price: float = None,
                                leverage: int = None,
                                post_only: bool = False) -> Optional[Order]:
        """
        高级订单创建方法
        
        Args:
            symbol: 交易对
            order_type: 'limit' 或 'market'
            action: 操作类型
                - 'open_long': 开多仓
                - 'open_short': 开空仓  
                - 'close_long': 平多仓
                - 'close_short': 平空仓
            amount: 数量
            price: 价格
            sl_price: 止损价格
            tp_price: 止盈价格
            leverage: 杠杆倍数
            post_only: 是否只做Maker（仅限价单有效）
        """
        symbol_key = f"{exchange_id}:{symbol}"

        exchange = self.exchange_manager.exchanges.get(exchange_id)
        if not exchange:
            logging.error(f"Attempted to trade on an unknown exchange: {exchange_id}")
            return None
        
        # 确定交易方向和仓位方向
        action_map = {
            OrderAction.OPEN_LONG: {'side': OrderSide.BUY, 'posSide': PositionSide.LONG, 'reduceOnly': False},
            OrderAction.OPEN_SHORT: {'side': OrderSide.SELL, 'posSide': PositionSide.SHORT, 'reduceOnly': False},
            OrderAction.CLOSE_LONG: {'side': OrderSide.SELL, 'posSide': PositionSide.LONG, 'reduceOnly': True},
            OrderAction.CLOSE_SHORT: {'side': OrderSide.BUY, 'posSide': PositionSide.SHORT, 'reduceOnly': True},
        }
        
        if action not in action_map:
            raise ValueError(f"Invalid action: {action}")
        
        config = action_map[action]

        # 前置检查（需要加锁访问共享数据）
        async with self._order_lock:
            if not await self._pre_order_checks(symbol_key, config['side'], amount, price):
                return None
        
        # 平仓订单额外检查：验证是否有持仓
        if config['reduceOnly']:
            positions = await self.position_manager.get_symbol_positions(exchange_id, symbol)
            pos_side = config['posSide']  # PositionSide.LONG or PositionSide.SHORT
            
            if not positions or pos_side not in positions:
                logging.warning(f"⚠️ 平仓失败：没有{pos_side.value}持仓 - {exchange_id}:{symbol}")
                return None
            
            position = positions[pos_side]
            if not position or position.contracts <= 0:
                logging.warning(f"⚠️ 平仓失败：{pos_side.value}持仓数量为0 - {exchange_id}:{symbol}")
                return None
            
            # 检查平仓数量是否超过持仓
            position_contracts = position.contracts
            if amount > position_contracts:
                logging.warning(f"⚠️ 平仓数量({amount})超过持仓({position_contracts})，调整为持仓数量")
                amount = position_contracts
        
        # 使用交易所的 build_order_params 方法构建参数
        params = exchange.build_order_params(
            side=config['side'],
            pos_side=config['posSide'].value,
            reduce_only=config['reduceOnly'],
            extra_params={}
        )
        
        # 设置杠杆
        if leverage and not config['reduceOnly']:  # 开仓时才设置杠杆
            await exchange.set_leverage(leverage, symbol, config['posSide'].value)
        
        # 设置止损止盈 (添加到 params 中)
        if sl_price:
            params['stopLoss'] = {
                'triggerPrice': str(sl_price),
                'type': 'market'
            }
        
        if tp_price:
            params['takeProfit'] = {
                'triggerPrice': str(tp_price), 
                'type': 'market'
            }

        # 生成临时client_order_id，用于在API调用前创建占位订单
        # OKX requires alphanumeric only (no hyphens or special chars), max 32 chars
        temp_client_order_id = uuid.uuid4().hex[:32]
        
        # 先创建占位订单对象，使用临时ID
        # 这样可以确保在交易所返回之前，交易事件就能找到订单对象
        placeholder_order = Order(
            exchange_id=exchange_id,
            clOrdId=temp_client_order_id,
            order_id=f"PENDING_{uuid.uuid4().hex[:8]}",  # 临时唯一ID，等API返回后更新
            symbol=symbol,
            order_type=order_type,
            side=config['side'],
            pos_side=config['posSide'],
            action=action,
            reduce_only=config['reduceOnly'],
            quantity=amount,
            price=price,
            local_order=True,
            post_only=post_only,
            strategy_id=None
        )
        
        # 先添加占位订单到管理系统（需要加锁）
        async with self._order_lock:
            await self._add_order_to_management(placeholder_order)
        
        try:
            # 将自定义的 client_order_id 添加到 params 中
            params['clientOrderId'] = temp_client_order_id
            
            # 网络IO操作，不持有锁
            order_data = await exchange.create_order(
                symbol,
                order_type,
                config['side'],
                amount,
                price,
                params,
                post_only=post_only
            )

            if order_data is None:
                # 移除占位订单（需要加锁）
                async with self._order_lock:
                    await self._remove_order_from_management(placeholder_order)
                logging.error(f"🙅 订单创建失败: {exchange_id} {symbol} {order_type.value} {action.value} {amount} @ {price}")
                # 在此处尝试更新持仓信息
                await self.position_manager.sync_positions_from_exchange(exchange_id)
                return None
            
            # 从返回数据中提取真实的订单ID
            order_id = order_data.get('id') or order_data['info'].get('ordId')
            client_order_id = order_data.get('clientOrderId', order_data.get('clOrdId')) or order_data.get('info', {}).get('clOrdId', order_id)

            if order_id is None:
                # 移除占位订单（需要加锁）
                async with self._order_lock:
                    await self._remove_order_from_management(placeholder_order)
                logging.error(f"🙅 订单创建失败: {exchange_id} {symbol} {order_type.value} {action.value} {amount} @ {price}")
                return None
            
            # 更新占位订单的真实ID（需要加锁保护共享数据）
            async with self._order_lock:
                old_order_id = placeholder_order.order_id
                placeholder_order.order_id = order_id
                # client_order_id 应该与 temp_client_order_id 一致，因为我们已经传递给交易所
                # 但为了保险起见，如果交易所返回了不同的值，使用交易所返回的
                if client_order_id and client_order_id != temp_client_order_id:
                    placeholder_order.clOrdId = client_order_id
                    self.client_order_id_map.pop(temp_client_order_id, None)
                    self.client_order_id_map[client_order_id] = order_id
                else:
                    # 正常情况：client_order_id == temp_client_order_id
                    # 只需要更新 order_id 映射即可
                    self.client_order_id_map[temp_client_order_id] = order_id
                
                # 更新索引：移除旧ID，添加新ID
                self.orders.pop(old_order_id, None)
                self.orders[order_id] = placeholder_order
            
            logging.info(f"创建订单: {order_id} ({client_order_id}) {config['side']} {order_type.value} {action.value} {amount} {exchange_id} {symbol} @ {price}")
            return placeholder_order
            
        except Exception as e:
            # 发生异常时移除占位订单（需要加锁）
            async with self._order_lock:
                await self._remove_order_from_management(placeholder_order)
            logging.error(f"❌ 订单创建异常: {e}")
            raise

    # 便捷方法
    async def open_long(self, exchange_id: str, symbol: str, amount: float, price: float = None, 
                    order_type: OrderType = OrderType.LIMIT, leverage: int = None):
        """开多仓"""
        return await self.create_order_advanced(
            exchange_id=exchange_id,
            symbol=symbol,
            order_type=order_type,
            action=OrderAction.OPEN_LONG,
            amount=amount,
            price=price,
            leverage=leverage
        )

    async def open_short(self, exchange_id: str, symbol: str, amount: float, price: float = None,
                        order_type: OrderType = OrderType.LIMIT, leverage: int = None):
        """开空仓"""
        return await self.create_order_advanced(
            exchange_id=exchange_id,
            symbol=symbol,
            order_type=order_type,
            action=OrderAction.OPEN_SHORT,
            amount=amount,
            price=price,
            leverage=leverage
        )

    async def close_long(self, exchange_id: str, symbol: str, amount: float, price: float = None,
                        order_type: OrderType = OrderType.MARKET):
        """平多仓"""
        return await self.create_order_advanced(
            exchange_id=exchange_id,
            symbol=symbol,
            order_type=order_type,
            action=OrderAction.CLOSE_LONG,
            amount=amount,
            price=price
        )

    async def close_short(self, exchange_id: str, symbol: str, amount: float, price: float = None,
                        order_type: OrderType = OrderType.MARKET):
        """平空仓"""
        return await self.create_order_advanced(
            exchange_id=exchange_id,
            symbol=symbol,
            order_type=order_type,
            action=OrderAction.CLOSE_SHORT,
            amount=amount,
            price=price
        )
    
    async def create_orders_batch(self, exchange_id: str, orders_data: List[Dict]) -> List[Order]:
        """
        批量创建订单
        
        Args:
            exchange_id: 交易所ID
            orders_data: 订单数据列表，每个订单包含:
                {
                    'symbol': str,
                    'action': OrderAction,
                    'amount': float,
                    'price': float (可选),
                    'order_type': OrderType (可选，默认LIMIT),
                    'post_only': bool (可选，默认False)
                }
        
        Returns:
            创建成功的订单对象列表
        """
        exchange = self.exchange_manager.exchanges.get(exchange_id)
        if not exchange:
            logging.error(f"Attempted to trade on an unknown exchange: {exchange_id}")
            return []
        
        # 构建交易所格式的订单列表
        exchange_orders = []
        order_configs = []  # 保存每个订单的配置信息
        
        for order_data in orders_data:
            symbol = order_data['symbol']
            action = order_data['action']
            amount = order_data['amount']
            price = order_data.get('price')
            order_type = order_data.get('order_type', OrderType.LIMIT)
            post_only = order_data.get('post_only', False)
            
            # 确定交易方向和仓位方向
            action_map = {
                OrderAction.OPEN_LONG: {'side': OrderSide.BUY, 'posSide': PositionSide.LONG, 'reduceOnly': False},
                OrderAction.OPEN_SHORT: {'side': OrderSide.SELL, 'posSide': PositionSide.SHORT, 'reduceOnly': False},
                OrderAction.CLOSE_LONG: {'side': OrderSide.SELL, 'posSide': PositionSide.LONG, 'reduceOnly': True},
                OrderAction.CLOSE_SHORT: {'side': OrderSide.BUY, 'posSide': PositionSide.SHORT, 'reduceOnly': True},
            }
            
            if action not in action_map:
                logging.warning(f"Invalid action: {action}, skipping order")
                continue
            
            config = action_map[action]
            order_configs.append({
                'symbol': symbol,
                'action': action,
                'amount': amount,
                'price': price,
                'order_type': order_type,
                'config': config,
                'post_only': post_only
            })
            
            # 构建交易所订单参数
            # 使用交易所的 build_order_params 方法来确保兼容性
            # OKX requires alphanumeric only (no hyphens or special chars), max 32 chars
            temp_client_order_id = uuid.uuid4().hex[:32]
            
            # 调用交易所特定的参数构建方法
            params = exchange.build_order_params(
                side=config['side'],
                pos_side=config['posSide'].value,
                reduce_only=config['reduceOnly'],
                extra_params={'clientOrderId': temp_client_order_id}
            )
            
            exchange_orders.append({
                'symbol': symbol,
                'type': order_type,
                'side': config['side'],
                'amount': amount,
                'price': price,
                'params': params,
                'post_only': post_only,
                'client_order_id': temp_client_order_id
            })
        
        if not exchange_orders:
            return []
        
        # 创建占位订单
        placeholder_orders = []
        async with self._order_lock:
            for i, order_config in enumerate(order_configs):
                temp_client_order_id = exchange_orders[i]['client_order_id']
                placeholder_order = Order(
                    exchange_id=exchange_id,
                    clOrdId=temp_client_order_id,
                    order_id=f"PENDING_{uuid.uuid4().hex[:8]}",
                    symbol=order_config['symbol'],
                    order_type=order_config['order_type'],
                    side=order_config['config']['side'],
                    pos_side=order_config['config']['posSide'],
                    action=order_config['action'],
                    reduce_only=order_config['config']['reduceOnly'],
                    quantity=order_config['amount'],
                    price=order_config['price'],
                    local_order=True,
                    post_only=order_config['post_only'],
                    strategy_id=None
                )
                placeholder_orders.append(placeholder_order)
                await self._add_order_to_management(placeholder_order)
        
        try:
            # 调用交易所批量创建订单
            results = await exchange.create_orders(exchange_orders)
            
            if not results:
                # 全部失败，移除所有占位订单
                async with self._order_lock:
                    for placeholder in placeholder_orders:
                        await self._remove_order_from_management(placeholder)
                logging.error(f"🙅 批量订单创建失败: {exchange_id}")
                return []
            
            # 更新成功创建的订单
            successful_orders = []
            async with self._order_lock:
                for i, order_data in enumerate(results):
                    if order_data is None:
                        continue
                    
                    order_id = order_data.get('id') or order_data.get('info', {}).get('ordId')
                    client_order_id = order_data.get('clientOrderId') or order_data.get('info', {}).get('clOrdId')
                    
                    if not order_id:
                        continue
                    
                    # 找到对应的占位订单
                    placeholder = None
                    for p in placeholder_orders:
                        if p.clOrdId == client_order_id or (i < len(placeholder_orders) and p == placeholder_orders[i]):
                            placeholder = p
                            break
                    
                    if placeholder:
                        # 更新占位订单
                        old_order_id = placeholder.order_id
                        placeholder.order_id = order_id
                        
                        if client_order_id and client_order_id != placeholder.clOrdId:
                            self.client_order_id_map.pop(placeholder.clOrdId, None)
                            placeholder.clOrdId = client_order_id
                            self.client_order_id_map[client_order_id] = order_id
                        else:
                            self.client_order_id_map[placeholder.clOrdId] = order_id
                        
                        # 更新索引
                        self.orders.pop(old_order_id, None)
                        self.orders[order_id] = placeholder
                        successful_orders.append(placeholder)
                        
                        logging.info(f"批量订单创建成功: {order_id} ({client_order_id}) {placeholder.action.value} {placeholder.symbol}")
            
            # 移除失败的占位订单
            async with self._order_lock:
                for placeholder in placeholder_orders:
                    if placeholder not in successful_orders:
                        await self._remove_order_from_management(placeholder)
            
            logging.info(f"✅ 批量创建订单完成: {len(successful_orders)}/{len(orders_data)} 成功")
            return successful_orders
            
        except Exception as e:
            # 发生异常时移除所有占位订单
            async with self._order_lock:
                for placeholder in placeholder_orders:
                    await self._remove_order_from_management(placeholder)
            logging.error(f"❌ 批量订单创建异常: {e}", exc_info=True)
            return []
    
    async def update_order_status(self, order_id: str, status: OrderStatus, filled_quantity: float = 0):
        """更新订单状态（兼容旧接口）"""
        async with self._order_lock:
            order = self.orders.get(order_id)
            if not order:
                logging.warning(f"尝试更新未知订单: {order_id} -> {status.value}, 已成交: {filled_quantity}")
                return
            
            # 只有当状态或成交量发生变化时，才更新 updated_at
            if order.status != status or order.filled_quantity != filled_quantity:
                order.updated_at = datetime.now()
            
            order.status = status
            order.filled_quantity = filled_quantity

            symbol_key = f"{order.exchange_id}:{order.symbol}"

            if status == OrderStatus.OPEN:
                # 从pending移到open
                if order in self.pending_orders[symbol_key]:
                    self.pending_orders[symbol_key].remove(order)
                self.open_orders[symbol_key].append(order)
            
            # 如果订单完成或取消，从活跃列表中移除
            if order.is_closed:
                await self._remove_from_active_lists(order)
            
            logging.info(f"更新订单状态: {order_id} -> {status.value}, 已成交: {filled_quantity}/{order.quantity}")

    async def add_order_filled_quantity(self, order_id: str, filled_quantity: float):
        """增加订单已成交数量（兼容旧接口）"""
        async with self._order_lock:
            order = self.orders.get(order_id)
            if not order:
                logging.warning(f"尝试更新未知订单的已成交数量: {order_id} + {filled_quantity}")
                return
            
            order.filled_quantity += filled_quantity
            order.updated_at = datetime.now()
            
            logging.info(f"更新订单已成交数量: {order_id} + {filled_quantity} -> {order.filled_quantity}/{order.quantity}")
    
    async def update_order_from_ccxt(self, ccxt_order: Dict[str, Any]):
        """
        从CCXT返回的订单数据更新订单状态
        
        这是新的推荐方法，能够处理完整的CCXT订单数据
        
        Args:
            ccxt_order: CCXT返回的订单字典
        """
        async with self._order_lock:
            order_id = ccxt_order.get('id')
            if not order_id:
                logging.warning(f"CCXT订单缺少ID: {ccxt_order}")
                return
            
            order = self.orders.get(order_id)
            if not order:
                logging.warning(f"尝试更新未知订单: {order_id}")
                return
            
            # 使用Order的更新方法
            order.update_from_ccxt_order(ccxt_order)
            
            symbol_key = f"{order.exchange_id}:{order.symbol}"
            
            # 更新活跃订单列表
            if order.status == OrderStatus.OPEN:
                if order in self.pending_orders[symbol_key]:
                    self.pending_orders[symbol_key].remove(order)
                if order not in self.open_orders[symbol_key]:
                    self.open_orders[symbol_key].append(order)
            
            # 如果订单完成或取消，从活跃列表中移除
            if order.is_closed:
                await self._remove_from_active_lists(order)
            
            logging.info(f"更新订单状态 (CCXT): {order}")

    async def cancel_order(self, exchange_id: str, order_id: str):
        """取消订单"""
        async with self._order_lock:
            order = self.orders.get(order_id)
            if not order:
                logging.warning(f"尝试取消未知订单: {order_id}")
                return
            
            exchange = self.exchange_manager.exchanges.get(exchange_id)
            if not exchange:
                logging.error(f"Attempted to trade on an unknown exchange: {exchange_id}")
                return None
            
            result = await exchange.cancel_order(order_id, order.symbol)

            if result is None:
                logging.error(f"取消订单失败: {exchange_id} {order_id}")
                return None
            
            order.update_from_ccxt_order(result)
            
            if order.is_closed:
                await self._remove_from_active_lists(order)
            
            logging.info(f"取消订单成功: {exchange_id} {order_id}")

    async def _cancel_orders(self, exchange_id: str, ids, symbol: str = None, params={}):
        """取消多个订单"""
        exchange = self.exchange_manager.exchanges.get(exchange_id)
        if not exchange:
            logging.error(f"Attempted to trade on an unknown exchange: {exchange_id}")
            return None

        # :returns dict: an list of `order structures <https://docs.ccxt.com/#/?id=order-structure>`
        result = await exchange.cancel_orders(ids, symbol, params)
        return result

    async def _update_cancelled_orders(self, results: List[Dict[str, Any]]) -> List[Order]:
        """
        根据交易所返回结果更新订单状态（内部方法）
        
        Args:
            results: 交易所返回的订单结果列表
            
        Returns:
            List[Order]: 成功更新的订单列表
        """
        rets = []
        if not results:
            return rets
        
        for result in results:
            order_id = result.get('id')
            order = self.orders.get(order_id)
            if order:
                rets.append(order)
                # 使用 update_from_ccxt_order 方法更新订单状态
                old_status = order.status
                order.update_from_ccxt_order(result)
                
                # 只有当状态发生变化时才处理
                if order.status != old_status:
                    # 如果订单已关闭，从活跃列表中移除
                    if order.is_closed:
                        await self._remove_from_active_lists(order)
                        logging.info(f"订单状态变化: {order_id} {old_status.value} -> {order.status.value}")
        
        return rets

    async def cancel_orders(self, exchange_id: str, ids, symbol: str = None, params={})-> Optional[List[Order]]:
        """取消多个订单"""
        async with self._order_lock:
            if not ids:
                logging.info(f"没有订单需要取消")
                return []
            
            results = await self._cancel_orders(exchange_id, ids, symbol, params)
            
            # 根据返回结果更新订单状态
            rets = await self._update_cancelled_orders(results)
            
            # 清理空的列表（已被移除的订单会留下空列表）
            if symbol:
                symbol_key = f"{exchange_id}:{symbol}"
                if symbol_key in self.pending_orders and not self.pending_orders[symbol_key]:
                    del self.pending_orders[symbol_key]
                if symbol_key in self.open_orders and not self.open_orders[symbol_key]:
                    del self.open_orders[symbol_key]
            
            logging.info(f"取消{len(ids)}个订单")

            return rets

    async def cancel_all_orders(self, exchange_id: str) -> Optional[List[Order]]:
        """取消所有订单"""
        async with self._order_lock:
            active_orders = [o for o in self.orders.values() if o.is_active and o.exchange_id == exchange_id]
            
            if not active_orders:
                logging.info(f"没有活跃订单需要取消")
                return []
            
            ids = [order.order_id for order in active_orders]
            # 交易所内部已实现分批逻辑
            results = await self._cancel_orders(exchange_id, ids)
            
            # 根据返回结果更新订单状态
            rets = await self._update_cancelled_orders(results)
            
            # 清理空的列表（已被移除的订单会留下空列表）
            self.pending_orders = {k: v for k, v in self.pending_orders.items() if v}
            self.open_orders = {k: v for k, v in self.open_orders.items() if v}
            
            logging.info(f"取消所有{len(active_orders)}个活跃订单")
            
            return rets

    async def fetch_order_and_update(self, exchange_id: str, order_id: str) -> Optional[Order]:
        """
        从交易所查询订单并更新本地状态
        
        Args:
            exchange_id: 交易所ID
            order_id: 订单ID
            
        Returns:
            Order: 更新后的订单对象，如果失败返回None
        """
        async with self._order_lock:
            order = self.orders.get(order_id)
            if not order:
                logging.warning(f"尝试查询未知订单: {order_id}")
                return None
            
            exchange = self.exchange_manager.exchanges.get(exchange_id)
            if not exchange:
                logging.error(f"Attempted to query order on unknown exchange: {exchange_id}")
                return None
        
        # 网络IO操作，不持有锁
        result = await exchange.fetch_order(order_id, order.symbol)
        
        if result is None:
            logging.error(f"查询订单失败: {exchange_id} {order_id}")
            return None
        
        # 更新本地订单状态
        async with self._order_lock:
            order = self.orders.get(order_id)  # 重新获取，确保状态最新
            if not order:
                logging.warning(f"订单在查询过程中被移除: {order_id}")
                return None
            
            order.update_from_ccxt_order(result)
            
            # 如果订单已关闭，从活跃列表中移除
            if order.is_closed:
                await self._remove_from_active_lists(order)
            
            logging.info(f"查询并更新订单成功: {exchange_id} {order_id} - {order.status.value}")
            return order

    async def edit_order(self, exchange_id: str, order_id: str, new_amount: float = None, new_price: float = None, params: Optional[Dict] = None) -> Optional[Order]:
        """
        修改订单
        
        Args:
            exchange_id: 交易所ID
            order_id: 订单ID
            new_amount: 新数量 (可选)
            new_price: 新价格 (可选)
            params: 额外参数
            
        Returns:
            Optional[Order]: 修改后的订单对象，失败返回None
        """
        # 获取订单对象（需要加锁）
        async with self._order_lock:
            order = self.orders.get(order_id)
            if not order:
                logging.warning(f"尝试修改未知订单: {order_id}")
                return None
            
            if not order.is_active:
                logging.warning(f"尝试修改非活跃订单: {order_id} ({order.status})")
                return None
            
            # 复制一份订单信息用于调用，避免长时间持有锁
            symbol = order.symbol
            order_type = order.order_type
            side = order.side
            current_amount = order.quantity
            current_price = order.price

        # 验证必要参数
        if not symbol:
            logging.error(f"订单缺少symbol信息: {order_id}")
            return None
        
        if not order_type:
            logging.error(f"订单缺少order_type信息: {order_id}")
            return None
        
        if not side:
            logging.error(f"订单缺少side信息: {order_id}")
            return None

        exchange = self.exchange_manager.exchanges.get(exchange_id)
        if not exchange:
            logging.error(f"Unknown exchange: {exchange_id}")
            return None
        params = params or {}
        # 如果没有提供新值，使用旧值
        amount = new_amount if new_amount is not None else current_amount
        price = new_price if new_price is not None else current_price
        
        try:
            # 调用交易所接口 (网络IO，不持有锁)
            result = await exchange.edit_order(
                order_id, 
                symbol, 
                order_type, 
                side, 
                amount, 
                price, 
                params
            )
            
            if result is None:
                logging.error(f"修改订单失败: {exchange_id} {symbol} {order_id} {order_type.value} {side.value} -> {amount} @ {price}")
                return None
            
            # 更新订单状态（需要加锁）
            async with self._order_lock:
                # 重新获取订单，防止在网络IO期间被删除
                order = self.orders.get(order_id)
                if order:
                    order.update_from_ccxt_order(result)
                    logging.info(f"修改订单成功: {exchange_id} {symbol} {order_id} {order.action.value} {order.status.value} -> {amount} @ {price}")
                    return order
                else:
                    logging.warning(f"订单在修改期间被移除: {order_id}")
                    return None
                    
        except Exception as e:
            logging.error(f"修改订单异常: {exchange_id} {symbol} {order_id}: {e}", exc_info=True)
            return None

    async def get_open_orders(self, exchange_id: str, symbol: str, side: OrderSide = None):
        """获取指定symbol的open订单        
        Args:
            exchange_id: 交易所ID
            symbol: 交易对
            side: 订单方向 (buy/sell)，可选
        
        Returns:
            List[Order]: 符合条件的订单列表
        """
        symbol_key = f"{exchange_id}:{symbol}"
        orders = self.open_orders.get(symbol_key, [])
        
        if side:
            return [order for order in orders if order.side == side]

        return orders.copy()

    async def get_pending_orders(self, exchange_id: str, symbol: str, side: OrderSide = None):
        """获取指定symbol的pending订单        
        Args:
            exchange_id: 交易所ID
            symbol: 交易对
            side: 订单方向 (buy/sell)，可选
        
        Returns:
            List[Order]: 符合条件的订单列表
        """
        symbol_key = f"{exchange_id}:{symbol}"
        orders = self.pending_orders.get(symbol_key, [])
        
        if side:
            return [order for order in orders if order.side == side]

        return orders.copy()

    async def _pre_order_checks(self, symbol_key: str, side: OrderSide, quantity: float, price: float) -> bool:
        """下单前检查"""
        # 1. 检查全局订单数量限制
        total_orders = len([o for o in self.orders.values() if o.is_active])
        if total_orders >= self.global_constraints.max_total_orders:
            logging.info(f"达到全局订单数量限制: {total_orders}")
            return False
        
        # # 2. 检查单个symbol订单数量限制
        # symbol_active_orders = [o for o in self.symbol_orders.get(symbol_key, []) if o.is_active]
        # if len(symbol_active_orders) >= self.global_constraints.max_symbol_orders:
        #     # 打印详细的活跃订单信息以便调试
        #     active_order_info = [f"ID={o.order_id} 状态={o.status.value} 操作={o.action.value}" for o in symbol_active_orders]
        #     logging.info(f"达到{symbol_key}订单数量限制: {len(symbol_active_orders)}")
        #     logging.info(f"活跃订单列表: {', '.join(active_order_info)}")
        #     return False
        
        # 3. 检查分组限制
        group_name = self.symbol_to_group.get(symbol_key)
        if group_name and group_name in self.symbol_groups:
            group = self.symbol_groups[group_name]
            group_active_orders = len([o for o in self.group_orders.get(group_name, []) if o.is_active])
            if group_active_orders >= group.constraints.max_symbol_orders:
                logging.info(f"达到分组{group_name}订单数量限制: {group_active_orders}")
                return False
        
        # 4. 检查风险暴露
        if not await self._check_exposure_limits(symbol_key, side, quantity, price):
            return False
        
        return True

    async def _check_exposure_limits(self, symbol_key: str, side: OrderSide, quantity: float, price: float) -> bool:
        """检查风险暴露限制"""
        # 计算新订单的价值
        order_value = quantity * price if price else 0
        
        # 检查单个symbol暴露
        symbol_exposure = await self._calculate_symbol_exposure(symbol_key)
        if symbol_exposure + order_value > self.global_constraints.max_symbol_exposure:
            logging.info(f"超过{symbol_key}风险暴露限制: {symbol_exposure + order_value:.2f}")
            return False
        
        # 检查分组暴露
        group_name = self.symbol_to_group.get(symbol_key)
        if group_name:
            group_exposure = await self._calculate_group_exposure(group_name)
            group_limit = self.symbol_groups[group_name].constraints.max_symbol_exposure
            if group_exposure + order_value > group_limit:
                logging.info(f"超过分组{group_name}风险暴露限制: {group_exposure + order_value:.2f}")
                return False
        
        # 检查总暴露
        total_exposure = await self._calculate_total_exposure()
        if total_exposure + order_value > self.global_constraints.max_position_value:
            logging.info(f"超过总风险暴露限制: {total_exposure + order_value:.2f}")
            return False
        
        return True

    async def _calculate_symbol_exposure(self, symbol_key: str) -> float:
        """计算symbol的风险暴露"""
        exposure = 0
        for order in self.symbol_orders.get(symbol_key, []):
            if order.is_active:
                value = order.remaining_quantity * (order.price or 0)
                exposure += value
        return exposure
    
    async def _calculate_group_exposure(self, group_name: str) -> float:
        """计算分组的风险暴露"""
        exposure = 0
        for order in self.group_orders.get(group_name, []):
            if order.is_active:
                value = order.remaining_quantity * (order.price or 0)
                exposure += value
        return exposure
    
    async def _calculate_total_exposure(self) -> float:
        """计算总风险暴露"""
        exposure = 0
        for order in self.orders.values():
            if order.is_active:
                value = order.remaining_quantity * (order.price or 0)
                exposure += value
        return exposure

    async def _add_order_to_management(self, order: Order):
        """添加订单到管理系统"""
        symbol_key = f"{order.exchange_id}:{order.symbol}"
        self.orders[order.order_id] = order
        self.client_order_id_map[order.clOrdId] = order.order_id
        
        # 添加到symbol索引
        self.symbol_orders[symbol_key].append(order)

        # 添加到分组索引
        group_name = self.symbol_to_group.get(symbol_key)
        if group_name:
            self.group_orders[group_name].append(order)
        
        # 添加到pending列表
        self.pending_orders[symbol_key].append(order)
    
    async def _remove_order_from_management(self, order: Order):
        """从管理系统中移除订单"""
        symbol_key = f"{order.exchange_id}:{order.symbol}"
        
        # 从主字典移除
        self.orders.pop(order.order_id, None)
        self.client_order_id_map.pop(order.clOrdId, None)
        
        # 从symbol索引移除
        if symbol_key in self.symbol_orders:
            self.symbol_orders[symbol_key] = [o for o in self.symbol_orders[symbol_key] if o.order_id != order.order_id]
        
        # 从分组索引移除
        group_name = self.symbol_to_group.get(symbol_key)
        if group_name and group_name in self.group_orders:
            self.group_orders[group_name] = [o for o in self.group_orders[group_name] if o.order_id != order.order_id]
        
        # 从pending列表移除
        if symbol_key in self.pending_orders:
            self.pending_orders[symbol_key] = [o for o in self.pending_orders[symbol_key] if o.order_id != order.order_id]
    
    async def get_order_by_client_id(self, client_order_id: str) -> Optional[Order]:
        """通过client_order_id获取订单"""
        async with self._order_lock:
            order_id = self.client_order_id_map.get(client_order_id)
            if order_id:
                return self.orders.get(order_id)
            return None

        
    async def has_active_order(self, exchange_id: str, symbol: str) -> bool:
        """检查是否有活跃订单"""
        async with self._order_lock:
            symbol_key = f"{exchange_id}:{symbol}"
            orders = self.symbol_orders.get(symbol_key, [])
            return any(o.is_active for o in orders)
    
    async def get_orders_by_symbol(self, exchange_id: str, symbol: str, active_only: bool = True) -> List[Order]:
        """获取指定symbol的订单"""
        async with self._order_lock:
            symbol_key = f"{exchange_id}:{symbol}"
            orders = self.symbol_orders.get(symbol_key, [])
            if active_only:
                return [o for o in orders if o.is_active]
            return orders.copy()
    
    async def get_orders_by_group(self, group_name: str, active_only: bool = True) -> List[Order]:
        """获取指定分组的订单"""
        async with self._order_lock:
            orders = self.group_orders.get(group_name, [])
            if active_only:
                return [o for o in orders if o.is_active]
            return orders.copy()
    
    async def get_orders_by_strategy(self, strategy_id: str, active_only: bool = True) -> List[Order]:
        """获取指定策略的订单"""
        async with self._order_lock:
            orders = [o for o in self.orders.values() if o.strategy_id == strategy_id]
            if active_only:
                return [o for o in orders if o.is_active]
            return orders
    
    async def get_all_active_orders(self) -> Dict[str, List[Order]]:
        """获取所有活跃订单（按symbol分组）"""
        async with self._order_lock:
            active_orders = defaultdict(list)
            for symbol_key, orders in self.symbol_orders.items():
                active_orders[symbol_key] = [o for o in orders if o.is_active]
            return dict(active_orders)
    
    async def cancel_orders_by_symbol(self, exchange_id: str, symbol: str, side: OrderSide = None) -> Optional[List[Order]]:
        """取消指定symbol的订单"""
        symbol_key = f"{exchange_id}:{symbol}"
        async with self._order_lock:
            orders_to_cancel = []
            for order in self.symbol_orders.get(symbol_key, []):
                if order.is_active and (side is None or order.side == side):
                    orders_to_cancel.append(order)
            
            if not orders_to_cancel:
                logging.info(f"没有活跃订单需要取消: {symbol}")
                return []
            
            ids = [order.order_id for order in orders_to_cancel]
            # 交易所内部已实现分批逻辑
            results = await self._cancel_orders(exchange_id, ids, symbol)
            
            # 根据返回结果更新订单状态
            rets = await self._update_cancelled_orders(results)
            
            # 清理空的列表
            if symbol_key in self.pending_orders and not self.pending_orders[symbol_key]:
                del self.pending_orders[symbol_key]
            if symbol_key in self.open_orders and not self.open_orders[symbol_key]:
                del self.open_orders[symbol_key]

            logging.info(f"取消{symbol}的{len(orders_to_cancel)}个订单")
            
            return rets
    
    async def cancel_orders_by_group(self, group_name: str, side: OrderSide = None) -> Optional[List[Order]]:
        """取消指定分组的订单"""
        async with self._order_lock:
            orders_to_cancel = []
            for order in self.group_orders.get(group_name, []):
                if order.is_active and (side is None or order.side == side):
                    orders_to_cancel.append(order)
            
            if not orders_to_cancel:
                logging.info(f"没有活跃订单需要取消: 分组{group_name}")
                return []
            
            rets = []
            # 按交易所和symbol分组
            cancel_by_exchange_symbol = defaultdict(list)
            for order in orders_to_cancel:
                key = (order.exchange_id, order.symbol)
                cancel_by_exchange_symbol[key].append(order)
            
            # 按交易所和symbol执行取消（交易所内部已实现分批逻辑）
            for (exchange_id, symbol), orders in cancel_by_exchange_symbol.items():
                ids = [order.order_id for order in orders]
                results = await self._cancel_orders(exchange_id, ids, symbol)
                
                # 根据返回结果更新订单状态
                batch_rets = await self._update_cancelled_orders(results)
                rets.extend(batch_rets)
            
            logging.info(f"取消分组{group_name}的{len(orders_to_cancel)}个订单")
            
            return rets

    async def fetch_ohlcv(self,  exchange_id: str, symbol: str, timeframe='1m', since: Optional[int] = None, limit: Optional[int] = None, params={}) -> List[list]:
        """获取动态交易对的K线数据"""
        try:
            exchange = self.exchange_manager.exchanges.get(exchange_id)
            if not exchange:
                logging.error(f"Attempted to fetch_ohlcv on an unknown exchange: {exchange_id}")
                return

            list = await exchange.fetch_ohlcv(symbol, timeframe, since, limit, params=params)
            return list
        except Exception as e:
            logging.error(f"Failed to fetch_ohlcv on {exchange_id} for {symbol}: {e}", exc_info=False)
            return []
        
    async def fetch_ticker(self, exchange_id: str, symbol: str, params={}) -> Optional[Dict]:
        """获取动态交易对的Ticker数据"""
        try:
            exchange = self.exchange_manager.exchanges.get(exchange_id)
            if not exchange:
                logging.error(f"Attempted to fetch_ticker on an unknown exchange: {exchange_id}")
                return None

            ticker = await exchange.fetch_ticker(symbol, params=params)
            return ticker
        except Exception as e:
            logging.error(f"Failed to fetch_ticker on {exchange_id} for {symbol}: {e}", exc_info=False)
            return None
    
    async def _remove_from_active_lists(self, order: Order):
        """从活跃列表中移除订单"""
        symbol_key = f"{order.exchange_id}:{order.symbol}"
        
        # 从pending列表移除
        if symbol_key in self.pending_orders:
            self.pending_orders[symbol_key] = [
                o for o in self.pending_orders[symbol_key] 
                if o.order_id != order.order_id
            ]
        
        # 从open列表移除
        if symbol_key in self.open_orders:
            self.open_orders[symbol_key] = [
                o for o in self.open_orders[symbol_key]
                if o.order_id != order.order_id
            ]
    
    async def get_portfolio_summary(self) -> Dict:
        """获取投资组合摘要"""
        async with self._order_lock:
            total_orders = len(self.orders)
            active_orders = len([o for o in self.orders.values() if o.is_active])
            pending_orders = sum(len(orders) for orders in self.pending_orders.values())
            open_orders = sum(len(orders) for orders in self.open_orders.values())
            
            # 按symbol统计
            symbol_stats = {}
            for symbol_key in self.symbol_orders:
                symbol_orders = self.symbol_orders[symbol_key]
                active_count = len([o for o in symbol_orders if o.is_active])
                total_value = sum(o.quantity * (o.price or 0) for o in symbol_orders if o.is_active)
                symbol_stats[symbol_key] = {
                    'total_orders': len(symbol_orders),
                    'active_orders': active_count,
                    'total_value': total_value
                }
            
            # 按分组统计
            group_stats = {}
            for group_name in self.group_orders:
                group_orders = self.group_orders[group_name]
                active_count = len([o for o in group_orders if o.is_active])
                total_value = sum(o.quantity * (o.price or 0) for o in group_orders if o.is_active)
                group_stats[group_name] = {
                    'total_orders': len(group_orders),
                    'active_orders': active_count,
                    'total_value': total_value,
                    'symbol_count': len(self.symbol_groups[group_name].symbols)
                }
            
            return {
                'total_orders': total_orders,
                'active_orders': active_orders,
                'pending_orders': pending_orders,
                'open_orders': open_orders,
                'symbol_stats': symbol_stats,
                'group_stats': group_stats,
                'total_exposure': await self._calculate_total_exposure(),
                'timestamp': datetime.now()
            }
