# exchanges/exchange_okx.py
# OKX交易所优化实现 - 使用统一数据事件接口

import asyncio
import ccxt.pro as ccxtpro
import logging
from typing import List, Dict, Optional
from exchanges.common_exchange import CommonExchange
from common.data_types import DataEventType, DataEventFactory, OrderType, OrderSide
from config import EXCHANGE_SANDBOX_MODE, EXCHANGE_SETTINGS, PROXY, SYMBOL_DISCOVERY, STRATEGY_PARAMS



class OkxExchange(CommonExchange):
    """OKX交易所优化实现"""

    def __init__(self, exchange_id: str, api_keys: dict, config: Dict):
        super().__init__(exchange_id, api_keys, config)

    async def initialize(self):
        logging.info(f"Initializing {self.exchange_id} ...")
        self.ccxt_exchange = ccxtpro.okx(self.api_keys)
        self.ccxt_exchange.aiohttp_proxy = PROXY.get('url') if PROXY.get('enabled') else None
        self.ccxt_exchange.aiohttp_trust_env = True
        self.ccxt_exchange.options["defaultType"] = "swap"
        
        is_sandbox_mode: bool = bool(self.config.get('testnet', False))
        self.ccxt_exchange.set_sandbox_mode(is_sandbox_mode)
        logging.info(f"loaded {self.exchange_id} for sandbox mode: {is_sandbox_mode}")

        settings = EXCHANGE_SETTINGS.get(self.exchange_id, {})
        # await self.cancel_all_orders()
        self.hedge_mode = settings.get('hedge_mode', True)  # 保存持仓模式设置
        await self.set_position_mode(hedge_mode=self.hedge_mode)

        # 启动全局监听任务
        await self._create_global_task(self.watch_balances_loop())
        # await self._create_global_task(self.watch_positions_loop())
        await self._create_global_task(self.watch_my_trades_loop())
        await self._create_global_task(self.watch_orders_loop())

    async def set_position_mode(self, hedge_mode: bool):
        """设置持仓模式 - OKX 特定实现"""
        try:
            mode = 'long_short_mode' if hedge_mode else 'net_mode'
            await self.ccxt_exchange.private_post_account_set_position_mode({'posMode': mode})
            logging.info(f"Successfully set position mode for {self.exchange_id} to {mode}")
        except Exception as e:
            logging.error(f"Failed to set position mode for {self.exchange_id}: {e}")

    async def set_leverage_for_all_symbols(self, leverage: int, symbols: List[str]):
        """为所有交易对设置杠杆 - OKX 特定实现"""
        logging.info(f"Setting leverage to {leverage}x for {len(symbols)} symbols on {self.exchange_id}...")
        for symbol in symbols:
            try:
                await self.set_leverage(leverage, symbol, 'long')
                await self.set_leverage(leverage, symbol, 'short')
            except Exception as e:
                logging.warning(f"Could not set leverage for {symbol} on {self.exchange_id}: {e}")
        logging.info(f"Finished setting leverage for {self.exchange_id}.")

    async def set_leverage(self, leverage: int, symbol: str, posSide: str):
        """为指定交易对设置杠杆 - OKX 特定实现"""
        try:
            params = {'mgnMode': 'isolated', 'posSide': posSide}
            await self.ccxt_exchange.set_leverage(leverage, symbol, params)
            logging.info(f"Set leverage to {leverage}x for {symbol} {posSide} on {self.exchange_id}")
        except Exception as e:
            logging.error(f"Failed to set leverage for {symbol} on {self.exchange_id}: {e}")

    async def _watch_single_data_type(self, data_type: DataEventType, symbol: str):
        """监听单个数据类型和交易对"""
        logging.info(f"Starting {data_type.name} watch for {symbol} on {self.exchange_id}")
        
        while True:
            try:
                if symbol not in self._subscription_tasks[data_type]:
                    logging.info(f"{data_type.name} watch for {symbol} stopped (task removed)")
                    break
                
                # 根据数据类型调用相应的监听方法
                if data_type == DataEventType.TICKER:
                    data = await self.ccxt_exchange.watch_ticker(symbol)
                    logging.debug(f"✅ Received ticker data for {symbol}: {data.get('last', 0)}")
                    event = DataEventFactory.create_ticker_event(self.exchange_id, symbol, data)
                    
                elif data_type == DataEventType.TRADE:
                    data = await self.ccxt_exchange.watch_trades(symbol)        
                    logging.debug(f"✅ Received {len(data)} trades for {symbol}")
                    event = DataEventFactory.create_trade_event(self.exchange_id, symbol, data)
                    
                elif data_type == DataEventType.ORDERBOOK:
                    data = await self.ccxt_exchange.watch_order_book(symbol)    
                    logging.debug(f"✅ Received order book data for {symbol}")
                    event = DataEventFactory.create_orderbook_event(self.exchange_id, symbol, data)
                    
                elif data_type == DataEventType.OHLCV:
                    timeframe = STRATEGY_PARAMS['timeframe']
                    data = await self.ccxt_exchange.watch_ohlcv(symbol, timeframe)
                    logging.debug(f"✅ Received OHLCV data for {symbol}")
                    event = DataEventFactory.create_ohlcv_event(self.exchange_id, symbol, timeframe, data)                  
                  
                else:
                    logging.warning(f"Unsupported data type: {data_type.name}")
                    break
                
                # 发送事件到统一处理器
                await self._emit_data_event(event)
                
            except asyncio.CancelledError:
                logging.info(f"{data_type.name} watch for {symbol} cancelled")
                break
            except Exception as e:
                logging.error(f"{data_type.name} loop error for {symbol} on {self.exchange_id}: {e}. Reconnecting...")
                await asyncio.sleep(5)

    # === 交易相关方法实现 ===

    def build_order_params(self, side: OrderSide, pos_side: str, reduce_only: bool, extra_params: Dict = None) -> Dict:
        """
        构建 OKX 订单参数
        
        Args:
            side: 订单方向 (BUY/SELL)
            pos_side: 持仓方向 ('long'/'short')
            reduce_only: 是否只减仓
            extra_params: 额外参数（如止损止盈等）
        
        Returns:
            OKX 特定的参数字典
        """
        params = {
            'tdMode': 'isolated',
            'posSide': pos_side,
            'reduceOnly': reduce_only
        }
        
        if extra_params:
            params.update(extra_params)
        
        return params

    async def create_order(self, symbol: str, type: OrderType, side: OrderSide, amount: float, 
                          price: float = None, params: Dict = {}, post_only: bool = False):
        """创建订单 - OKX 实现"""
        try:
            default_params = {'tdMode': 'isolated'}
            
            # 设置 postOnly（仅限价单有效）
            if post_only and type == OrderType.LIMIT:
                default_params['postOnly'] = True  # OKX 直接使用 postOnly 参数
            
            default_params.update(params)

            return await self.ccxt_exchange.create_order_ws(symbol, type.value, side.value, amount, price, params=default_params)
        except Exception as e:
            logging.error(f"❌ Exchange failed to create order on {self.exchange_id} for {symbol}: {e}", exc_info=False)
            return None

    async def create_orders(self, orders: List[Dict]) -> List[Dict]:
        """批量创建订单 - OKX 实现，使用原生批量接口"""
        logging.info(f"Creating {len(orders)} orders on {self.exchange_id}")
        try:
            # 构建符合 ccxt create_orders 接口的订单列表
            ccxt_orders = []
            for order in orders:
                symbol = order['symbol']
                order_type = order['type']
                side = order['side']
                amount = order['amount']
                price = order.get('price')
                params = order.get('params', {})
                post_only = order.get('post_only', False)
                
                # 构建订单参数
                order_params = {'tdMode': 'isolated'}
                
                # 设置 postOnly
                if post_only and order_type == OrderType.LIMIT:
                    order_params['postOnly'] = True
                
                order_params.update(params)
                
                # ccxt create_orders 需要的格式
                ccxt_orders.append({
                    'symbol': symbol,
                    'type': order_type.value,
                    'side': side.value,
                    'amount': amount,
                    'price': price,
                    'params': order_params
                })
            
            # 使用 ccxt 原生批量下单接口
            # OKX 支持 create_orders 方法
            if hasattr(self.ccxt_exchange, 'create_orders'):
                results = await self.ccxt_exchange.create_orders(ccxt_orders)
                logging.info(f"✅ Successfully created {len(results)}/{len(orders)} orders on {self.exchange_id}")
                return results
            else:
                # 如果不支持批量接口，降级为并发单个下单
                logging.warning(f"⚠️ {self.exchange_id} does not support native create_orders, using concurrent approach")
                tasks = []
                for order in ccxt_orders:
                    task = self.ccxt_exchange.create_order_ws(
                        order['symbol'],
                        order['type'],
                        order['side'],
                        order['amount'],
                        order['price'],
                        params=order['params']
                    )
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 过滤成功的订单
                successful_orders = []
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logging.error(f"❌ Failed to create order {i+1}/{len(orders)}: {result}")
                    elif result is not None:
                        successful_orders.append(result)
                
                logging.info(f"✅ Successfully created {len(successful_orders)}/{len(orders)} orders on {self.exchange_id}")
                return successful_orders
            
        except Exception as e:
            logging.error(f"❌ Exchange failed to create batch orders on {self.exchange_id}: {e}", exc_info=False)
            return []

    async def cancel_order(self, order_id: str, symbol: str):
        """取消订单 - OKX 实现"""
        try:
            return await self.ccxt_exchange.cancel_order_ws(order_id, symbol)
        except Exception as e:
            logging.error(f"❌ Exchange failed to cancel order {order_id} on {self.exchange_id} for {symbol}: {e}", exc_info=False)
            return None

    async def cancel_orders(self, ids, symbol: str = None, params={}):
        """取消多个订单 - OKX 实现"""
        try:
            return await self.ccxt_exchange.cancel_orders_ws(ids, symbol, params=params)
        except Exception as e:
            logging.error(f"❌ Exchange failed to cancel orders on {self.exchange_id} for {symbol}: {e}", exc_info=False)
            return None

    async def cancel_all_orders(self, symbol: str = None, params={}):
        """取消所有订单 - OKX 实现"""
        try:
            result = await self.ccxt_exchange.cancel_all_orders_ws(symbol, params=params)
            logging.info(f"Cancelled all open orders on {self.exchange_id} for symbol: {symbol if symbol else 'ALL'}")
            return result
        except Exception as e:
            logging.error(f"❌ Exchange failed to cancel all orders on {self.exchange_id} for {symbol}: {e}", exc_info=False)
            return  None

    async def edit_order(self, order_id: str, symbol: str, type: OrderType, side: OrderSide, amount: float, price: float = None, params: Dict = {}):
        """修改订单 - OKX 实现"""
        try:
            # 验证必要参数
            if not type or not side:
                logging.error(f"❌ Invalid parameters for edit_order: order_id={order_id}, type={type}, side={side}")
                return None
            
            # OKX 修改订单通常只需要 newSz (amount) 或 newPx (price)
            # CCXT 的 edit_order 会处理这些映射
            # 但我们需要确保 tdMode 等参数正确，虽然修改订单可能不需要 tdMode，但保持一致性比较好
            
            # 注意：OKX API 修改订单时，有些参数可能不需要传，或者有特定格式
            # 这里直接调用 ccxt 的 edit_order，它会映射到 private_post_trade_amend_order
            
            return await self.ccxt_exchange.edit_order_ws(order_id, symbol, type.value, side.value, amount, price, params=params)
        except Exception as e:
            error_str = str(e)
            
            # OKX 错误码处理：
            # 51503: 订单已完成或取消
            # 51400: 订单取消中，不能修改
            # 51401: 订单已撤销
            # 51402: 订单已完成
            if ('"sCode":"51503"' in error_str or '"sCode":"51400"' in error_str or 
                '"sCode":"51401"' in error_str or '"sCode":"51402"' in error_str or
                'already been filled or canceled' in error_str or
                'Order does not exist' in error_str):
                logging.debug(f"订单不存在或已完成: {order_id} - {error_str}")
                return None
            
            # 51506: 订单无需修改（价格/数量未变化）
            if '"sCode":"51506"' in error_str or 'Nothing to amend' in error_str:
                logging.info(f"订单无需修改: {order_id} (价格/数量未变化)")
                # 尝试获取当前订单状态并返回，模拟修改成功
                try:
                    current_order = await self.ccxt_exchange.fetch_order_ws(order_id, symbol)
                    return current_order
                except Exception as fetch_err:
                    logging.warning(f"无法获取无需修改的订单信息: {fetch_err}")
                    return None
            
            logging.error(f"❌ Exchange failed to edit order {order_id} on {self.exchange_id} for {symbol}: {e}", exc_info=False)
            return None

    async def fetch_order(self, order_id: str, symbol: str, params: Dict = {}):
        """查询订单 - OKX 实现"""
        try:
            return await self.ccxt_exchange.fetch_order_ws(order_id, symbol, params=params)
        except Exception as e:
            error_str = str(e)
            
            # OKX 错误码处理：
            # 51603: 订单不存在
            if '"sCode":"51603"' in error_str or 'Order does not exist' in error_str:
                logging.debug(f"订单不存在: {order_id}")
                return None
            
            logging.error(f"❌ Exchange failed to fetch order {order_id} on {self.exchange_id} for {symbol}: {e}", exc_info=False)
            return None
        
    async def fetch_balance(self, params: Dict = {}) -> Dict:
        """获取账户余额信息 - OKX 实现"""
        try:
            return await self.ccxt_exchange.fetch_balance(params)
        except Exception as e:
            logging.error(f"❌ Exchange failed to fetch balance on {self.exchange_id}: {e}", exc_info=False)
            return {}
