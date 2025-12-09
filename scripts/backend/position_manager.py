# position_manager.py
# 持仓管理模块

import asyncio
import logging
from typing import Dict, List, Optional
from collections import defaultdict
from datetime import datetime
from common.data_types import Position, PositionSide, OrderSide, OrderAction
from shared_state import SharedState
from exchange_manager import ExchangeManager


class PositionManager:
    """多symbol持仓管理器"""
    
    def __init__(self, exchange_manager: ExchangeManager, shared_state: SharedState):
        self.exchange_manager: ExchangeManager = exchange_manager
        self.shared_state: SharedState = shared_state

        # 持仓存储: {exchange_id}:{symbol}:{side} -> Position
        self.positions: Dict[str, Position] = {}
        
        # 按交易所和symbol索引: {exchange_id}:{symbol} -> {side: Position}
        self.symbol_positions: Dict[str, Dict[PositionSide, Position]] = defaultdict(dict)
        
        # 锁
        self._position_lock = asyncio.Lock()
        
        logging.info("持仓管理模块已初始化。")
    
    def _get_position_key(self, exchange_id: str, symbol: str, side: PositionSide) -> str:
        """生成持仓键"""
        return f"{exchange_id}:{symbol}:{side.value}"
    
    def _get_symbol_key(self, exchange_id: str, symbol: str) -> str:
        """生成symbol键"""
        return f"{exchange_id}:{symbol}"
    
    async def update_position_from_event(self, exchange_id: str, symbol: str, position_data: Dict):
        """
        从交易所事件更新持仓（带锁的外部接口）。

        说明：为避免在已有锁的上下文中再次尝试加锁导致死锁，
        实际逻辑被移动到 `_update_position_from_event_nolock`，
        该方法可在持有 `_position_lock` 时直接调用。
        """
        async with self._position_lock:
            await self._update_position_from_event_nolock(exchange_id, symbol, position_data)

    async def _update_position_from_event_nolock(self, exchange_id: str, symbol: str, position_data: Dict):
        """
        从交易所事件更新持仓（内部无锁版本）。

        该方法假定调用者已持有 self._position_lock 或在不需要锁的上下文中调用。
        """
        # 解析持仓方向（支持传入字符串或 PositionSide Enum）
        pos_side_raw = position_data.get('side') or position_data.get('posSide', 'net')
        if isinstance(pos_side_raw, PositionSide):
            pos_side = pos_side_raw
        else:
            try:
                pos_side = PositionSide(str(pos_side_raw).lower())
            except Exception:
                pos_side = PositionSide.NET

        position_key = self._get_position_key(exchange_id, symbol, pos_side)
        symbol_key = self._get_symbol_key(exchange_id, symbol)

        # 获取持仓数量
        contracts = float(position_data.get('contracts', 0) or position_data.get('size', 0) or 0)

        # 如果持仓数量为0，删除持仓记录
        if abs(contracts) < 1e-8:
            if position_key in self.positions:
                self.positions.pop(position_key, None)
            if pos_side in self.symbol_positions.get(symbol_key, {}):
                # 安全删除，避免 KeyError；若该 symbol 下没有任何 side，清理该 symbol_key
                self.symbol_positions[symbol_key].pop(pos_side, None)
                if not self.symbol_positions[symbol_key]:
                    self.symbol_positions.pop(symbol_key, None)

            # 更新共享状态（非阻塞）
            await self.shared_state.update_position_non_blocking(exchange_id, symbol, None)
            logging.info(f"⚠️ 清除持仓: {exchange_id} {symbol} {pos_side.value}")
            return

        # 创建或更新持仓
        if position_key in self.positions:
            position = self.positions[position_key]
            position.update_from_dict(position_data)
        else:
            position = Position(
                exchange_id=exchange_id,
                symbol=symbol,
                side=pos_side,
                contract_size=float(position_data.get('contractSize', 1))
            )
            position.update_from_dict(position_data)
            self.positions[position_key] = position
            self.symbol_positions[symbol_key][pos_side] = position

        # 更新共享状态（非阻塞）
        await self.shared_state.update_position_non_blocking(exchange_id, symbol, {
            'side': pos_side.value,
            'contracts': position.contracts,
            'entry_price': position.entry_price,
            'mark_price': position.mark_price,
            'unrealized_pnl': position.unrealized_pnl,
            'leverage': position.leverage,
            'margin': position.margin,
            'liquidation_price': position.liquidation_price,
            'position_value': position.position_value,
        })

        logging.info(
            f"更新持仓: {exchange_id} {symbol} {pos_side.value} "
            f"数量={position.contracts:.4f} "
            f"均价={position.entry_price:.4f} "
            f"浮盈={position.unrealized_pnl:.4f}"
        )
    
    async def update_position_from_trade(self, exchange_id: str, symbol: str, 
                                        side: OrderSide, quantity: float, price: float,
                                        pos_side: PositionSide, reduce_only: bool = False):
        """
        从成交订单更新持仓(本地计算)
        
        Args:
            exchange_id: 交易所ID
            symbol: 交易对
            side: 订单方向 (buy/sell)
            quantity: 成交数量
            price: 成交价格
            pos_side: 持仓方向 ('long'/'short')
            reduce_only: 是否为平仓订单
        """
        async with self._position_lock:
            # 推断订单动作和持仓方向
            action, position_side = self._infer_action_and_side(side, pos_side, reduce_only)
            if not action or not position_side:
                logging.warning(f"无法推断订单动作或持仓方向: side={side}, pos_side={pos_side}, reduce_only={reduce_only}")
                return

            position_key = self._get_position_key(exchange_id, symbol, position_side)
            symbol_key = self._get_symbol_key(exchange_id, symbol)

            # 获取或创建持仓
            position = self._get_or_create_position(position_key, symbol_key, exchange_id, symbol, position_side)

            # 更新持仓
            if action in [OrderAction.OPEN_LONG, OrderAction.OPEN_SHORT]:
                self._handle_open_position(position, quantity, price, exchange_id, symbol, position_side)
            elif action in [OrderAction.CLOSE_LONG, OrderAction.CLOSE_SHORT]:
                await self._handle_close_position(position, quantity, price, exchange_id, symbol, position_side, position_key, symbol_key)

            position.updated_at = datetime.now()

    def _infer_action_and_side(self, side: OrderSide, pos_side: PositionSide, reduce_only: bool):
        """推断订单动作和持仓方向"""
        if pos_side:
            if pos_side == PositionSide.LONG:
                return (OrderAction.CLOSE_LONG if reduce_only else OrderAction.OPEN_LONG, PositionSide.LONG)
            elif pos_side == PositionSide.SHORT:
                return (OrderAction.CLOSE_SHORT if reduce_only else OrderAction.OPEN_SHORT, PositionSide.SHORT)
        else:
            if side == OrderSide.BUY:
                return (OrderAction.CLOSE_SHORT if reduce_only else OrderAction.OPEN_LONG, PositionSide.LONG)
            elif side == OrderSide.SELL:
                return (OrderAction.CLOSE_LONG if reduce_only else OrderAction.OPEN_SHORT, PositionSide.SHORT)
        return None, None

    def _get_or_create_position(self, position_key: str, symbol_key: str, exchange_id: str, symbol: str, position_side: PositionSide):
        """获取或创建持仓"""
        if position_key not in self.positions:
            position = Position(
                exchange_id=exchange_id,
                symbol=symbol,
                side=position_side
            )
            self.positions[position_key] = position
            self.symbol_positions[symbol_key][position_side] = position
        else:
            position = self.positions[position_key]
        return position

    def _handle_open_position(self, position: Position, quantity: float, price: float, exchange_id: str, symbol: str, position_side: PositionSide):
        """处理开仓逻辑"""
        old_value = position.contracts * position.entry_price
        new_value = quantity * price
        position.contracts += quantity
        if position.contracts > 0:
            position.entry_price = (old_value + new_value) / position.contracts

        logging.info(
            f"开仓成交: {exchange_id} {symbol} {position_side.value} "
            f"+{quantity:.4f} @ {price:.4f}, "
            f"总持仓={position.contracts:.4f} 均价={position.entry_price:.4f}"
        )

    async def _handle_close_position(self, position: Position, quantity: float, price: float, exchange_id: str, symbol: str, position_side: PositionSide, position_key: str, symbol_key: str):
        """处理平仓逻辑"""
        pnl = (price - position.entry_price) * quantity if position_side == PositionSide.LONG else (position.entry_price - price) * quantity
        position.contracts -= quantity
        position.realized_pnl += pnl

        logging.info(
            f"平仓成交: {exchange_id} {symbol} {position_side.value} "
            f"-{quantity:.4f} @ {price:.4f}, "
            f"盈亏={pnl:.4f}, 剩余={position.contracts:.4f}"
        )
        
        # 记录平仓盈亏到 shared_state
        try:
            import time
            trade_detail = {
                "exchange_id": exchange_id,
                "symbol": symbol,
                "side": "close",
                "position_side": position_side.value,
                "quantity": quantity,
                "price": price,
                "entry_price": position.entry_price,
                "pnl": pnl,
                "timestamp": time.time(),
            }
            await self.shared_state.add_trade_detail_non_blocking(trade_detail)
        except Exception as e:
            logging.warning(f"记录平仓盈亏失败: {e}")

        # 如果持仓清零，删除记录
        if abs(position.contracts) < 1e-8:
            # 使用 pop 避免在并发或不一致状态下抛出 KeyError
            self.positions.pop(position_key, None)
            if symbol_key in self.symbol_positions:
                self.symbol_positions[symbol_key].pop(position_side, None)
                if not self.symbol_positions[symbol_key]:
                    self.symbol_positions.pop(symbol_key, None)
            await self.shared_state.update_position_non_blocking(exchange_id, symbol, None)
            return
    
    async def get_position(self, exchange_id: str, symbol: str, 
                          side: PositionSide) -> Optional[Position]:
        """获取指定持仓"""
        position_key = self._get_position_key(exchange_id, symbol, side)
        return self.positions.get(position_key)
    
    async def get_symbol_positions(self, exchange_id: str, symbol: str) -> Dict[PositionSide, Position]:
        """获取某个symbol的所有持仓(多空)"""
        symbol_key = self._get_symbol_key(exchange_id, symbol)
        return self.symbol_positions.get(symbol_key, {}).copy()
    
    async def get_all_positions(self, exchange_id: str = None) -> List[Position]:
        """获取所有持仓"""
        if exchange_id:
            return [
                pos for pos in self.positions.values() 
                if pos.exchange_id == exchange_id and pos.is_open
            ]
        return [pos for pos in self.positions.values() if pos.is_open]
    
    async def has_position(self, exchange_id: str, symbol: str, 
                          side: PositionSide = None) -> bool:
        """检查是否有持仓"""
        if side:
            position_key = self._get_position_key(exchange_id, symbol, side)
            position = self.positions.get(position_key)
            return position is not None and position.is_open
        else:
            symbol_key = self._get_symbol_key(exchange_id, symbol)
            positions = self.symbol_positions.get(symbol_key, {})
            return any(pos.is_open for pos in positions.values())
    
    async def calculate_total_unrealized_pnl(self, exchange_id: str = None) -> float:
        """计算总未实现盈亏"""
        positions = await self.get_all_positions(exchange_id)
        return sum(pos.unrealized_pnl for pos in positions)
    
    async def calculate_total_margin(self, exchange_id: str = None) -> float:
        """计算总保证金占用"""
        positions = await self.get_all_positions(exchange_id)
        return sum(pos.margin for pos in positions)
    
    async def calculate_position_value(self, exchange_id: str = None) -> float:
        """计算总持仓价值"""
        positions = await self.get_all_positions(exchange_id)
        return sum(pos.position_value for pos in positions)
    
    async def sync_positions(self):
        """同步所有交易所的持仓"""
        for exchange_id in self.exchange_manager.exchanges.keys():
            await self.sync_positions_from_exchange(exchange_id)
    
    async def sync_positions_from_exchange(self, exchange_id: str):
        """
        从交易所同步所有持仓(主动查询)
        
        Args:
            exchange_id: 交易所ID
        """
        try:
            exchange = self.exchange_manager.exchanges.get(exchange_id)
            if not exchange:
                logging.error(f"交易所不存在: {exchange_id}")
                return

            # 获取所有持仓数据（锁外操作）
            positions_data = await exchange.fetch_positions()

            async with self._position_lock:  # 锁内操作
                logging.info(f"从 {exchange_id} 同步了 {len(positions_data)} 个持仓")

                # 创建一个集合来跟踪当前同步的持仓键
                synced_position_keys = set()

                # 更新或新增持仓
                for pos_data in positions_data:
                    symbol = pos_data.get('symbol')
                    if not symbol:
                        continue

                    # 解析持仓方向（支持传入字符串或 PositionSide Enum）
                    pos_side_raw = pos_data.get('side') or pos_data.get('posSide', 'net')
                    if isinstance(pos_side_raw, PositionSide):
                        pos_side = pos_side_raw
                    else:
                        try:
                            pos_side = PositionSide(str(pos_side_raw).lower())
                        except Exception:
                            pos_side = PositionSide.NET

                    position_key = self._get_position_key(exchange_id, symbol, pos_side)
                    synced_position_keys.add(position_key)

                    # 更新或新增持仓
                    # 已经在 sync 方法里持有锁，调用无锁版本以避免二次加锁导致死锁
                    await self._update_position_from_event_nolock(exchange_id, symbol, pos_data)

                # 找出需要移除的持仓
                all_position_keys = {key for key in self.positions.keys() if key.startswith(f"{exchange_id}:")}
                keys_to_remove = all_position_keys - synced_position_keys

                for key in keys_to_remove:
                    position = self.positions.pop(key, None)
                    if position:
                        symbol_key = self._get_symbol_key(exchange_id, position.symbol)
                        self.symbol_positions[symbol_key].pop(position.side, None)

                        # 更新共享状态（非阻塞）
                        await self.shared_state.update_position_non_blocking(exchange_id, position.symbol, None)

                        logging.info(f"移除持仓: {exchange_id} {position.symbol} {position.side.value}")

        except Exception as e:
            logging.error(f"同步持仓失败 {exchange_id}: {e}", exc_info=True)

    async def clear_all_positions(self, exchange_id: str = None):
        """清除所有持仓数据(仅本地)"""
        async with self._position_lock:
            if exchange_id:
                keys_to_delete = [key for key in self.positions.keys() if key.startswith(f"{exchange_id}:")]
                for key in keys_to_delete:
                    del self.positions[key]
                symbol_keys_to_delete = [key for key in self.symbol_positions.keys() if key.startswith(f"{exchange_id}:")]
                for key in symbol_keys_to_delete:
                    del self.symbol_positions[key]
            else:
                self.positions.clear()
                self.symbol_positions.clear()
            logging.info("已清除所有持仓数据。")
    
    async def get_position_summary(self, exchange_id: str = None) -> Dict:
        """获取持仓摘要"""
        positions = await self.get_all_positions(exchange_id)
        
        summary = {
            'total_positions': len(positions),
            'long_positions': len([p for p in positions if p.side == PositionSide.LONG]),
            'short_positions': len([p for p in positions if p.side == PositionSide.SHORT]),
            'total_unrealized_pnl': sum(p.unrealized_pnl for p in positions),
            'total_realized_pnl': sum(p.realized_pnl for p in positions),
            'total_margin': sum(p.margin for p in positions),
            'total_value': sum(p.position_value for p in positions),
            'positions': []
        }
        
        for pos in positions:
            summary['positions'].append({
                'exchange_id': pos.exchange_id,
                'symbol': pos.symbol,
                'side': pos.side.value,
                'contracts': pos.contracts,
                'entry_price': pos.entry_price,
                'mark_price': pos.mark_price,
                'unrealized_pnl': pos.unrealized_pnl,
                'leverage': pos.leverage,
                'margin': pos.margin,
                'liquidation_price': pos.liquidation_price,
            })
        
        return summary
