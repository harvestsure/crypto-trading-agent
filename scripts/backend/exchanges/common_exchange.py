# exchanges/common_exchange.py
# 通用交易所实现基类 - 提取 OKX 和 Binance 的公共逻辑

from abc import abstractmethod
import asyncio
import copy
import logging
from typing import List, Dict, Optional
from exchanges.base_exchange import BaseExchange
from common.data_types import DataEvent, DataEventType, DataEventFactory, OrderSide, OrderType


class CommonExchange(BaseExchange):
    """
    通用交易所实现基类
    提取 OKX 和 Binance 等交易所的公共逻辑
    """

    def __init__(self, exchange_id: str, api_keys: Dict = None, config: Dict = None, shared_state = None):
        super().__init__(exchange_id, api_keys, config, shared_state)
        
        # 定义支持的市场数据类型（按symbol订阅）
        self.supported_data_types = {
            DataEventType.TICKER,
            DataEventType.TRADE,
            DataEventType.ORDERBOOK,
            DataEventType.OHLCV,
        }
        
        # 账户数据类型（全局订阅，在initialize中通过watch_*_loop处理）
        self.account_data_types = {
            DataEventType.POSITION,
            DataEventType.ORDER,
            DataEventType.MY_TRADE,
            DataEventType.BALANCE,
        }

        self.hedge_mode = True  # 存储持仓模式状态
        
        # 数据订阅任务管理
        self._subscription_tasks: Dict[DataEventType, Dict[str, asyncio.Task]] = {
            data_type: {} for data_type in self.supported_data_types
        }
        
        # 订阅锁
        self._subscription_locks: Dict[DataEventType, asyncio.Lock] = {
            data_type: asyncio.Lock() for data_type in self.supported_data_types
        }

    async def close(self):
        logging.info(f"Closing {self.exchange_id} exchange...")
        
        # First, stop all subscription tasks that use ccxt_exchange
        for data_type in self.supported_data_types:
            await self._cancel_all_tasks_for_type(data_type)
        
        # Then cancel global tasks (watch loops, etc.)
        await super().close()
        
        # Give a brief moment for all pending operations to complete
        await asyncio.sleep(0.1)

        # Finally, close the CCXT exchange session
        if self.ccxt_exchange:
            try:
                await self.ccxt_exchange.close()
                logging.info(f"✅ {self.exchange_id} CCXT exchange session closed successfully.")
            except Exception as e:
                logging.error(f"Error closing {self.exchange_id} CCXT exchange: {e}")
                raise

    async def fetch_ohlcv(self, symbol: str, timeframe='1m', since: Optional[int] = None, limit: Optional[int] = None, params={}) -> List[list]:
        """获取K线数据"""
        return await self.ccxt_exchange.fetch_ohlcv(symbol, timeframe, since, limit, params)
    
    async def fetch_ticker(self, symbol: str, params={}) -> Optional[Dict]:
        """获取Ticker数据"""
        try:
            ticker = await self.ccxt_exchange.fetch_ticker(symbol, params)
            return ticker
        except Exception as e:
            logging.error(f"❌ Exchange failed to fetch ticker for {symbol} on {self.exchange_id}: {e}", exc_info=False)
            return None

    async def get_market_info(self, symbol: str) -> Optional[Dict]:
        """
        获取交易对的市场信息
        
        Returns:
            {
                'contract_size': float,
                'contract_size_currency': str,
                'price_precision': float,
                'amount_precision': float,
                'min_amount': float,
                'min_cost': float,
                'max_leverage': int,
                'settlement_currency': str,
                'type': str,
            }
        """
        try:
            if not self.ccxt_exchange.markets:
                await self.ccxt_exchange.load_markets()
            
            market = self.ccxt_exchange.market(symbol)
            
            if not market:
                logging.warning(f"未找到交易对 {symbol} 的市场信息")
                return None
            
            def safe_float(value, default=None):
                try:
                    return float(value) if value is not None else default
                except (TypeError, ValueError):
                    return default
            
            market_info = {
                'contract_size': safe_float(market.get('contractSize'), 1.0),
                'contract_size_currency': market.get('base', market.get('baseId', '')),
                'price_precision': safe_float(market.get('precision', {}).get('price'), 0.01),
                'amount_precision': safe_float(market.get('precision', {}).get('amount'), 1.0),
                'min_amount': safe_float(market.get('limits', {}).get('amount', {}).get('min'), 1.0),
                'min_cost': safe_float(market.get('limits', {}).get('cost', {}).get('min')),
                'max_leverage': int(market.get('info', {}).get('lever', 100)),
                'settlement_currency': market.get('settle') or market.get('quote'),  # 从市场数据中获取，不设默认值
                'type': market.get('type', 'swap'),
                'symbol': symbol,
                'base': market.get('base', ''),
                'quote': market.get('quote', ''),
            }
            
            logging.debug(f"获取到市场信息 {symbol}: 合约面值={market_info['contract_size']} {market_info['contract_size_currency']}, "
                         f"价格精度={market_info['price_precision']}, 数量精度={market_info['amount_precision']}")
            
            return market_info
            
        except Exception as e:
            logging.error(f"获取交易对 {symbol} 市场信息失败: {e}", exc_info=True)
            return None

    # === 统一订阅接口实现 ===

    async def _start_data_subscription(self, data_type: DataEventType, symbols: List[str]):
        """开始订阅指定数据类型和交易对"""
        async with self._subscription_locks[data_type]:
            for symbol in symbols:
                if symbol in self._subscription_tasks[data_type]:
                    continue
                
                task = asyncio.create_task(
                    self._watch_single_data_type(data_type, symbol),
                    name=f"{data_type.name.lower()}_{self.exchange_id}_{symbol}"
                )
                self._subscription_tasks[data_type][symbol] = task
                
            logging.info(f"Started {data_type.name} subscription for {len(symbols)} symbols on {self.exchange_id}")

    async def _stop_data_subscription(self, data_type: DataEventType, symbols: List[str]):
        """停止订阅指定数据类型和交易对"""
        async with self._subscription_locks[data_type]:
            for symbol in symbols:
                if symbol in self._subscription_tasks[data_type]:
                    task = self._subscription_tasks[data_type].pop(symbol)
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                    
            logging.info(f"Stopped {data_type.name} subscription for {len(symbols)} symbols on {self.exchange_id}")

    @abstractmethod
    async def _watch_single_data_type(self, data_type: DataEventType, symbol: str):
        """监听单个数据类型和交易对"""
        pass

    async def _cancel_all_tasks_for_type(self, data_type: DataEventType):
        """取消指定数据类型的所有任务"""
        async with self._subscription_locks[data_type]:
            for symbol in list(self._subscription_tasks[data_type].keys()):
                task = self._subscription_tasks[data_type].pop(symbol)
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

    # === 账户数据相关方法实现 ===
    
    async def watch_my_trades_loop(self):
        """监听成交记录"""
        while True:
            try:
                my_trades = await self.ccxt_exchange.watch_my_trades()
                for trade in my_trades:
                    event = DataEventFactory.create_my_trade_event(self.exchange_id, trade['symbol'], trade)
                    await self._emit_data_event(event)
            except Exception as e:
                logging.error(f"My trades loop error on {self.exchange_id}: {e}. Reconnecting...")
                await asyncio.sleep(10)

    async def watch_orders_loop(self):
        """监听订单变化"""
        while True:
            try:
                my_orders = await self.ccxt_exchange.watch_orders()
                for order in my_orders:
                    event = DataEventFactory.create_order_event(self.exchange_id, order['symbol'], order)
                    await self._emit_data_event(event)
            except Exception as e:
                logging.error(f"My orders loop error on {self.exchange_id}: {e}. Reconnecting...")
                await asyncio.sleep(10)

    async def watch_positions_loop(self):
        """监听持仓变化"""
        while True:
            try:
                positions = await self.ccxt_exchange.watch_positions()
                for position in positions:
                    # 发送持仓事件
                    event = DataEventFactory.create_position_event(self.exchange_id, position['symbol'], position)
                    await self._emit_data_event(event)
                    
                    # 更新共享状态
                    await self.shared_state.update_position_non_blocking(self.exchange_id, position['symbol'], position)
                    
            except Exception as e:
                logging.error(f"Position loop error on {self.exchange_id}: {e}. Reconnecting...")
                await asyncio.sleep(10)

    async def watch_balances_loop(self):
        """监听余额变化 - 支持多币种"""
        while True:
            try:
                balance_update = await self.ccxt_exchange.watch_balance()
                
                # 记录所有重要币种的余额
                important_currencies = ['USDT', 'USDC']
                balance_info = {curr: balance_update.get(curr, {}) for curr in important_currencies if curr in balance_update}
                if balance_info:
                    logging.info(f"Balance updated for {self.exchange_id}: {balance_info}")
                
                await self.shared_state.set_balance_non_blocking(self.exchange_id, balance_update)
                event = DataEventFactory.create_balance_event(self.exchange_id, copy.copy(balance_update))
                await self._emit_data_event(event)
                await asyncio.sleep(60)
            except Exception as e:
                logging.error(f"Balance loop error on {self.exchange_id}: {e}. Reconnecting...")
                await asyncio.sleep(10)

    # === 交易相关方法实现 ===

    def check_order_viability(self, balance: Dict, symbol: str, order_type: str, 
                            side: str, amount: float, price: float, leverage: int) -> tuple[bool, str]:
        """检查订单可行性 - 支持多币种结算"""
        # 从symbol中获取结算币种，例如 BTC/USDT:USDT 或 ETH/USDC:USDC
        settlement_currency = self._get_settlement_currency(symbol)
        
        free_balance = balance.get(settlement_currency, {}).get('free', 0)
        if not free_balance:
            return False, f"No free {settlement_currency} balance available."
        
        position_value = amount * price
        required_margin = position_value / leverage
        
        if required_margin > free_balance:
            return False, f"Insufficient margin. Required: {required_margin:.2f} {settlement_currency}, Available: {free_balance:.2f} {settlement_currency}"
            
        return True, "Order is viable."
    
    def _get_settlement_currency(self, symbol: str) -> str:
        """
        从交易对符号中提取结算币种
        例如: BTC/USDT:USDT -> USDT, ETH/USDC:USDC -> USDC
        """
        try:
            if ':' in symbol:
                return symbol.split(':')[1]
            elif '/' in symbol:
                return symbol.split('/')[1]
            else:
                return 'USDT'  # 默认返回USDT
        except Exception:
            return 'USDT'

    async def cancel_all_orders(self, symbol: str = None, params={}):
        """取消所有订单 - 子类应重写此方法"""
        raise NotImplementedError

    async def edit_order(self, order_id: str, symbol: str, type: OrderType, side: OrderSide, amount: float, price: float = None, params: Dict = {}):
        """修改订单 - 通用实现"""
        try:
            # CCXT edit_order signature: edit_order(id, symbol, type, side, amount, price=None, params={})
            return await self.ccxt_exchange.edit_order(order_id, symbol, type.value, side.value, amount, price, params)
        except Exception as e:
            logging.error(f"❌ Exchange failed to edit order {order_id} on {self.exchange_id} for {symbol}: {e}", exc_info=False)
            return None

    async def fetch_positions(self, symbols: Optional[List[str]] = None, params={}) -> List[Dict]:
        """获取持仓信息"""
        try:
            return await self.ccxt_exchange.fetch_positions(symbols, params=params)
        except Exception as e:
            logging.error(f"❌ Exchange failed to fetch positions on {self.exchange_id}: {e}", exc_info=False)
            return []

    def build_order_params(self, side: OrderSide, pos_side: str, reduce_only: bool, extra_params: Dict = None) -> Dict:
        """
        构建订单参数 - 子类应重写此方法以适配不同交易所
        
        Args:
            side: 订单方向 (BUY/SELL)
            pos_side: 持仓方向 ('long'/'short')
            reduce_only: 是否只减仓
            extra_params: 额外参数（如止损止盈等）
        
        Returns:
            交易所特定的参数字典
        """
        # 默认实现，子类应重写
        params = {}
        if extra_params:
            params.update(extra_params)
        return params
