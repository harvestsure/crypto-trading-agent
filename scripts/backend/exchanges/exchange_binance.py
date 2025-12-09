# exchanges/exchange_binance.py
# Binance交易所优化实现 - 使用统一数据事件接口

import asyncio
import ccxt.pro as ccxtpro
import logging
from typing import List, Dict, Optional
from exchanges.common_exchange import CommonExchange
from common.data_types import DataEventType, DataEventFactory, OrderType, OrderSide


class BinanceExchange(CommonExchange):
    """Binance交易所优化实现"""

    def __init__(self, exchange_id: str, api_keys: dict, config: Dict):
        super().__init__(exchange_id, api_keys, config)

    async def initialize(self):
        logging.info(f"Initializing {self.exchange_id} ...")
        self.ccxt_exchange = ccxtpro.binance(self.api_keys)
        self.ccxt_exchange.aiohttp_proxy = self.config.PROXY.get('url') if self.config.PROXY.get('enabled') else None
        self.ccxt_exchange.aiohttp_trust_env = True
        self.ccxt_exchange.options['defaultType'] = 'swap'
        
        # 增加 recvWindow 以容忍更大的时间差（默认 10000ms 改为 60000ms）
        self.ccxt_exchange.options['recvWindow'] = 60000
        
        # 启用时间差自动调整
        self.ccxt_exchange.options['adjustForTimeDifference'] = True

        # 加载并同步时间差
        await self.ccxt_exchange.load_time_difference()
        
        is_sandbox_mode = config.EXCHANGE_SANDBOX_MODE.get(self.exchange_id, False)
        self.ccxt_exchange.enable_demo_trading(is_sandbox_mode)
        logging.info(f"loaded {self.exchange_id} for sandbox mode: {is_sandbox_mode}")

        settings = config.EXCHANGE_SETTINGS.get(self.exchange_id, {})
        
        # await self.cancel_all_orders()
        self.hedge_mode = settings.get('hedge_mode', True)  # 保存持仓模式设置
        await self.set_position_mode(hedge_mode=self.hedge_mode)

        # 启动全局监听任务
        await self._create_global_task(self.watch_balances_loop())
        # await self._create_global_task(self.watch_positions_loop())
        await self._create_global_task(self.watch_my_trades_loop())
        await self._create_global_task(self.watch_orders_loop())

    async def set_position_mode(self, hedge_mode: bool):
        """设置持仓模式 - Binance 特定实现"""
        try:
            # Use the correct CCXT method or raw API call
            await self.ccxt_exchange.set_position_mode(
                hedged=hedge_mode,
                symbol=None  # None means apply to all symbols
            )
            logging.info(f"Successfully set position mode for {self.exchange_id} to hedge_mode={hedge_mode}")
        except Exception as e:
            # e.args[0] is a dict containing error details
            # e.args[0] = 'binance {"code":-4059,"msg":"No need to change position side."}'
            # 如果 e 中的code是-4059，说明不需要设置
            if isinstance(e.args[0], str) and '"code":-4059' in e.args[0]:
                logging.info(f"Position mode for {self.exchange_id} is already set to hedge_mode={hedge_mode}, no change needed.")
            else:   
                logging.warning(f"Could not set position mode for {self.exchange_id}: {e}")

    async def set_leverage_for_all_symbols(self, leverage: int, symbols: List[str]):
        """为所有交易对设置杠杆 - Binance 特定实现"""
        logging.info(f"Setting leverage to {leverage}x for {len(symbols)} symbols on {self.exchange_id}...")
        for symbol in symbols:
            try:
                await self.ccxt_exchange.set_leverage(leverage, symbol)
            except Exception as e:
                logging.warning(f"Could not set leverage for {symbol} on {self.exchange_id}: {e}")
        logging.info(f"Finished setting leverage for {self.exchange_id}.")

    async def set_leverage(self, leverage: int, symbol: str, posSide: str):
        """为指定交易对设置杠杆 - Binance 实现"""
        try:
            # Binance 不需要 posSide 参数
            await self.ccxt_exchange.set_leverage(leverage, symbol)
            logging.info(f"Set leverage to {leverage}x for {symbol} on {self.exchange_id}")
        except Exception as e:
            logging.error(f"Failed to set leverage for {symbol} on {self.exchange_id}: {e}")

    async def fetch_dynamic_symbols(self) -> List[str]:
        """获取动态交易对列表 - Binance 特定实现"""
        try:
            discovery_params = config.SYMBOL_DISCOVERY
            markets = await self.ccxt_exchange.load_markets()
            tickers = await self.ccxt_exchange.fetch_tickers()
            
            quote_currencies = discovery_params.get('quote_currencies', ['USDT'])
            top_n_per_currency = discovery_params.get('top_n_symbols_per_currency', 10)
            
            all_top_symbols = []
            
            for quote_currency in quote_currencies:
                # Filter for perpetual futures with the correct quote currency
                # 只选择永续合约（没有到期日的合约）
                valid_symbols = [
                    s for s, m in markets.items() 
                    if m['type'] == 'swap' 
                    and m.get('quote') == quote_currency 
                    and m.get('settle') == quote_currency
                ]

                filtered_tickers = []
                for symbol in valid_symbols:
                    if symbol in tickers:
                        ticker = tickers[symbol]
                        
                        quote_volume = ticker.get('quoteVolume')
                        if not quote_volume:
                            base_volume = ticker.get('baseVolume', 0) or 0
                            latest_price = ticker.get('last') or ticker.get('close') or ticker.get('ask') or ticker.get('bid') or 0
                            quote_volume = base_volume * latest_price
                            ticker['quoteVolume'] = quote_volume
                        
                        if quote_volume > discovery_params['min_24h_volume']:
                            filtered_tickers.append(ticker)

                # Sort by quote volume descending
                sorted_tickers = sorted(filtered_tickers, key=lambda x: x.get('quoteVolume', 0), reverse=True)
                
                top_symbols = [t['symbol'] for t in sorted_tickers[:top_n_per_currency]]
                all_top_symbols.extend(top_symbols)
                logging.info(f"Discovered top {len(top_symbols)} {quote_currency} symbols on {self.exchange_id}: {top_symbols}")
            
            logging.info(f"Total discovered symbols on {self.exchange_id}: {len(all_top_symbols)}")
            return all_top_symbols
        except Exception as e:
            logging.error(f"Error discovering symbols on {self.exchange_id}: {e}")
            return []
        
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
                    event = DataEventFactory.create_orderbook_event(self.exchange_id, symbol, data)
                    
                elif data_type == DataEventType.OHLCV:
                    timeframe = config.STRATEGY_PARAMS['timeframe']
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
        构建 Binance 订单参数
        
        Args:
            side: 订单方向 (BUY/SELL)
            pos_side: 持仓方向 ('long'/'short')
            reduce_only: 是否只减仓
            extra_params: 额外参数（如止损止盈等）
        
        Returns:
            Binance 特定的参数字典
        """
        params = {}
        
        # Binance 规则：
        # 1. 对冲模式（hedge_mode=True）：
        #    - 不能发送 reduceOnly 参数
        #    - 必须设置 positionSide 为 LONG/SHORT
        # 2. 单向持仓模式（hedge_mode=False）：
        #    - 当 reduce_only=True 时：发送 reduceOnly='true'（字符串）
        #    - 当 reduce_only=False 时：不发送 reduceOnly
        #    - positionSide 必须设置为 BOTH
        
        if self.hedge_mode:
            # 对冲模式：使用 LONG/SHORT，不发送 reduceOnly
            params['positionSide'] = pos_side.upper()
        else:
            # 单向持仓模式：使用 BOTH
            params['positionSide'] = 'BOTH'
            # 只在平仓时发送 reduceOnly（必须是字符串 'true'）
            if reduce_only:
                params['reduceOnly'] = 'true'
        
        if extra_params:
            params.update(extra_params)
        
        return params

    async def create_order(self, symbol: str, type: OrderType, side: OrderSide, amount: float, 
                          price: float = None, params: Dict = {}, post_only: bool = False):
        """创建订单 - Binance 实现"""
        logging.info(f"Creating order on {self.exchange_id}: {symbol}, type={type}, side={side}, amount={amount}, price={price}, params={params}, post_only={post_only}")
        try:
            # 复制 params 避免修改原始数据
            final_params = params.copy()
            
            # 🔑 根据持仓模式设置 positionSide
            if self.hedge_mode:
                # 对冲模式：不允许 reduceOnly，使用 LONG/SHORT
                final_params.pop('reduceOnly', None)
                if 'positionSide' not in final_params:
                    final_params['positionSide'] = 'LONG' if side == OrderSide.BUY else 'SHORT'
            else:
                # 🔑 单向持仓模式：强制使用 BOTH（覆盖任何传入值）
                final_params['positionSide'] = 'BOTH'
            
            # 设置 postOnly（仅限价单有效）
            if post_only and type == OrderType.LIMIT:
                final_params['timeInForce'] = 'GTX'  # Binance 使用 GTX 表示 PostOnly

            # 使用 REST API 而不是 WebSocket（更稳定，避免签名问题）
            return await self.ccxt_exchange.create_order(symbol, type.value, side.value, amount, price, params=final_params)
        except Exception as e:
            logging.error(f"❌ Exchange failed to create order on {self.exchange_id} for {symbol}: {e}", exc_info=False)
            # ❌ Exchange failed to create order on binance for BTC/USDT:USDT: binance {"code":-2022,"msg":"ReduceOnly Order is rejected."}
            # 在此处应该尝试同步下position信息
            
            return None

    async def create_orders(self, orders: List[Dict]) -> List[Dict]:
        """批量创建订单 - Binance 实现，使用原生批量接口"""
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
                params = order.get('params', {}).copy()  # 复制一份，避免修改原始数据
                post_only = order.get('post_only', False)
                
                # 🔑 构建订单参数
                order_params = {}
                
                # 🔑 根据持仓模式设置 positionSide
                if self.hedge_mode:
                    # 对冲模式：不发送 reduceOnly，使用 LONG/SHORT
                    params.pop('reduceOnly', None)
                    if 'positionSide' in params:
                        order_params['positionSide'] = params.pop('positionSide')
                    else:
                        order_params['positionSide'] = 'LONG' if side == OrderSide.BUY else 'SHORT'
                else:
                    # 🔑 单向持仓模式：强制使用 BOTH（覆盖任何传入值）
                    params.pop('positionSide', None)  # 移除可能存在的错误值
                    order_params['positionSide'] = 'BOTH'
                    # 保留 reduceOnly 参数
                    if 'reduceOnly' in params:
                        order_params['reduceOnly'] = params.pop('reduceOnly')
                
                # 设置 postOnly
                if post_only and order_type == OrderType.LIMIT:
                    order_params['timeInForce'] = 'GTX'
                
                # 合并其他剩余参数
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
            
            # Binance 批量下单限制：最多 5 个订单/批次
            # 如果订单数量超过限制，分批处理
            BATCH_SIZE = 5
            all_results = []
            
            # 使用 ccxt 原生批量下单接口
            if hasattr(self.ccxt_exchange, 'create_orders'):
                # 分批处理
                for i in range(0, len(ccxt_orders), BATCH_SIZE):
                    batch = ccxt_orders[i:i + BATCH_SIZE]
                    logging.info(f"Creating batch {i//BATCH_SIZE + 1}: {len(batch)} orders")
                    
                    try:
                        results = await self.ccxt_exchange.create_orders(batch)
                        all_results.extend(results)
                        logging.info(f"✅ Batch {i//BATCH_SIZE + 1} successful: {len(results)} orders")
                    except Exception as batch_error:
                        logging.error(f"❌ Batch {i//BATCH_SIZE + 1} failed: {batch_error}")
                        # 批次失败时，尝试单个下单
                        for order in batch:
                            try:
                                result = await self.ccxt_exchange.create_order(
                                    order['symbol'],
                                    order['type'],
                                    order['side'],
                                    order['amount'],
                                    order['price'],
                                    params=order['params']
                                )
                                if result:
                                    all_results.append(result)
                            except Exception as single_error:
                                logging.error(f"❌ Single order failed: {single_error}")
                
                logging.info(f"✅ Successfully created {len(all_results)}/{len(orders)} orders on {self.exchange_id}")
                return all_results
            else:
                # 如果不支持批量接口，降级为并发单个下单
                logging.warning(f"⚠️ {self.exchange_id} does not support native create_orders, using concurrent approach")
                tasks = []
                for order in ccxt_orders:
                    task = self.ccxt_exchange.create_order(
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
        """取消订单 - Binance 实现"""
        try:
            return await self.ccxt_exchange.cancel_order_ws(order_id, symbol)
        except Exception as e:
            logging.error(f"❌ Exchange failed to cancel order {order_id} on {self.exchange_id} for {symbol}: {e}", exc_info=False)
            return None

    async def cancel_orders(self, ids, symbol: str = None, params={}):
        """取消多个订单 - Binance 实现（支持自动分批）"""
        if not ids:
            logging.info(f"No orders to cancel on {self.exchange_id} for {symbol}")
            return []
        
        logging.info(f"Cancelling {len(ids)} orders on {self.exchange_id} for {symbol}")
        
        # 🔥 Binance API限制：每次最多取消10个订单，需要分批处理
        BATCH_SIZE = 10
        all_results = []
        
        try:
            for i in range(0, len(ids), BATCH_SIZE):
                batch_ids = ids[i:i + BATCH_SIZE]
                batch_num = i // BATCH_SIZE + 1
                total_batches = (len(ids) - 1) // BATCH_SIZE + 1
                
                try:
                    results = await self.ccxt_exchange.cancel_orders(batch_ids, symbol, params=params)
                    if results:
                        all_results.extend(results if isinstance(results, list) else [results])
                    logging.info(f"✅ 取消订单批次 {batch_num}/{total_batches}：{len(batch_ids)}个订单成功")
                except Exception as e:
                    # 忽略"订单不存在"的错误（订单可能已经成交或取消）
                    error_str = str(e)
                    if ('"code":-2011' in error_str or '"code":-2013' in error_str or 
                        'Unknown order' in error_str or 'Order does not exist' in error_str):
                        logging.debug(f"部分订单不存在或已取消，忽略错误: {symbol}")
                    else:
                        logging.error(f"❌ 取消订单批次 {batch_num}/{total_batches} 失败: {e}")
                
                # 批次之间稍微等待，避免频率限制
                if i + BATCH_SIZE < len(ids):
                    await asyncio.sleep(0.3)
            
            logging.info(f"✅ 完成取消 {len(ids)} 个订单，成功 {len(all_results)} 个")
            return all_results
            
        except Exception as e:
            logging.error(f"❌ Exchange failed to cancel orders on {self.exchange_id} for {symbol}: {e}", exc_info=False)
            return all_results if all_results else None

    async def cancel_all_orders(self, symbol: str = None, params={}):
        """取消所有订单 - Binance 实现"""
        try:
            result = await self.ccxt_exchange.cancel_all_orders_ws(symbol, params=params)
            logging.info(f"Cancelled all open orders on {self.exchange_id} for symbol: {symbol if symbol else 'ALL'}")
            return result
        except Exception as e:
            logging.error(f"❌ Exchange failed to cancel all orders on {self.exchange_id} for {symbol}: {e}", exc_info=False)
            return None

    async def edit_order(self, order_id: str, symbol: str, type: OrderType, side: OrderSide, amount: float, price: float = None, params: Dict = {}):
        """修改订单 - Binance 实现"""
        try:
            # 验证必要参数
            if not type or not side:
                logging.error(f"❌ Invalid parameters for edit_order: order_id={order_id}, type={type}, side={side}")
                return None
            
            return await self.ccxt_exchange.edit_order_ws(order_id, symbol, type.value, side.value, amount, price, params=params)
        except Exception as e:
            error_str = str(e)
            # 如果订单不存在，返回None而不是抛出异常
            if ('"code":-2011' in error_str or '"code":-2013' in error_str or 
                'Unknown order' in error_str or 'Order does not exist' in error_str):
                logging.debug(f"订单不存在或已完成: {order_id}")
                return None
            
            # 忽略"无需修改"的错误（Binance错误码 -5027）
            if '"code":-5027' in error_str or 'No need to modify the order' in error_str or \
                '"code":-5043' in error_str or 'A pending modification already exists for this order' in error_str:
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
        """查询订单 - Binance 实现"""
        try:
            return await self.ccxt_exchange.fetch_order_ws(order_id, symbol, params=params)
        except Exception as e:
            error_str = str(e)
            # 如果订单不存在，返回None而不是抛出异常
            if ('"code":-2011' in error_str or '"code":-2013' in error_str or 
                'Unknown order' in error_str or 'Order does not exist' in error_str):
                logging.debug(f"订单不存在: {order_id}")
                return None
            
            logging.error(f"❌ Exchange failed to fetch order {order_id} on {self.exchange_id} for {symbol}: {e}", exc_info=False)
            return None