# exchange_manager.py
# 优化后的交易所管理器 - 使用统一数据事件接口和数据库配置

import asyncio
import importlib
import logging
from typing import Dict, Any, List, Set, Optional, Callable
from exchanges.base_exchange import BaseExchange
from shared_state import SharedState
from common.data_types import DataEvent, DataEventType, DataEventHandler

class ExchangeManager:
    """
    优化后的交易所管理器
    - 从数据库读取交易所配置
    - 支持动态添加、修改、删除交易所
    - 使用统一的数据事件接口
    - 支持灵活的数据类型订阅
    - 简化数据流管理
    """
    
    def __init__(self, shared_state: Optional[SharedState] = None):
        self.shared_state = shared_state
        self.exchanges: Dict[str, Any] = {}
        self.custom_exchanges: Dict[str, BaseExchange] = {}
        
        # 当前订阅的数据类型和交易对
        self._current_subscriptions: Dict[str, Dict[DataEventType, Set[str]]] = {}

        self.data_event_handler: Optional[DataEventHandler] = None

    async def initialize_all(self, exchange_configs: List[Dict[str, Any]] = None):
        """
        初始化多个交易所（通常从数据库读取配置）
        
        Args:
            exchange_configs: 交易所配置列表，格式为 [{
                'id': 'ex_xxx',
                'exchange': 'binance',  # 交易所类型
                'api_key': '...',
                'secret': '...',
                'passphrase': '...',  # 可选，OKX等需要
                'testnet': True
            }, ...]
        """
        if not exchange_configs:
            logging.info("没有交易所配置需要初始化")
            return
        
        logging.info(f"开始初始化 {len(exchange_configs)} 个交易所")
        
        for config in exchange_configs:
            await self.add_exchange(config)
    
    async def add_exchange(self, config: Dict[str, Any]) -> bool:
        """
        添加单个交易所
        
        Args:
            config: 交易所配置字典，包含 id, exchange, api_key, secret, passphrase (可选), testnet
        
        Returns:
            是否成功添加
        """
        exchange_id = config.get('id')
        exchange_type = config.get('exchange')
        
        if not exchange_id or not exchange_type:
            logging.error(f"交易所配置缺少必需字段: {config}")
            return False
        
        if exchange_id in self.exchanges or exchange_id in self.custom_exchanges:
            logging.warning(f"交易所 {exchange_id} 已存在")
            return False
        
        try:
            # 尝试使用自定义交易所实现（如果存在）
            custom_impl = await self._try_load_custom_exchange(exchange_id, config)
            if custom_impl:
                self.custom_exchanges[exchange_id] = custom_impl
                logging.info(f"✅ 已加载自定义交易所实现: {exchange_id}")
                return True
            
            # 否则使用 ccxt.pro
            exchange_obj = await self._create_ccxt_exchange(exchange_type, config)
            if exchange_obj:
                self.exchanges[exchange_id] = exchange_obj
                logging.info(f"✅ 已连接交易所: {exchange_id} ({exchange_type})")
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"❌ 添加交易所 {exchange_id} 失败: {e}", exc_info=True)
            return False
    
    async def _try_load_custom_exchange(self, exchange_id: str, config: Dict[str, Any]) -> Optional[BaseExchange]:
        """
        尝试加载自定义交易所实现
        """
        try:
            exchange_type = config.get('exchange')
            module_name = f"exchanges.exchange_{exchange_type}"
            class_name = f"{exchange_type.capitalize()}Exchange"
            
            logging.debug(f"尝试加载自定义交易所: {module_name}.{class_name}")
            module = importlib.import_module(module_name)
            ExchangeClass = getattr(module, class_name)
            
            # Normalize api_keys: support both new format (api_keys dict) and legacy format (separate fields)
            api_keys = config.get('api_keys', {})
            if not api_keys:
                api_keys = {
                    'api_key': config.get('api_key'),
                    'secret': config.get('secret'),
                    'passphrase': config.get('passphrase')
                }
            else:
                # If api_keys is new format, convert to ccxt format
                # ccxt 期望: api_key, secret (not api_secret), passphrase
                if isinstance(api_keys, dict):
                    api_keys = {
                        'api_key': api_keys.get('api_key'),
                        'secret': api_keys.get('secret'), 
                        'passphrase': api_keys.get('passphrase')
                    }
            
            # Remove None values
            api_keys = {k: v for k, v in api_keys.items() if v is not None}
            
            exchange_instance = ExchangeClass(
                exchange_id=exchange_id,
                api_keys=api_keys,
                config={'testnet': config.get('testnet', False)},
                shared_state=self.shared_state
            )
            
            # 设置事件处理器
            if hasattr(exchange_instance, 'set_data_event_handler'):
                exchange_instance.set_data_event_handler(self._handle_data_event)
            
            # 初始化
            if hasattr(exchange_instance, 'initialize'):
                await exchange_instance.initialize()
            
            return exchange_instance
        except (ImportError, AttributeError):
            return None
        except Exception as e:
            logging.debug(f"加载自定义交易所失败: {e}")
            return None
        
    async def _handle_data_event(self, event: DataEvent):
        """统一数据事件处理器"""
        try:
            # 将事件转发给策略管理器
            if self.data_event_handler:
                await self.data_event_handler(event)
        except Exception as e:
            logging.error(f"处理数据事件失败: {e}", exc_info=False)
    
    async def _create_ccxt_exchange(self, exchange_type: str, config: Dict[str, Any]) -> Optional[Any]:
        """
        使用自定义交易所实现创建交易所实例
        优先使用 BinanceExchange、OkxExchange 等自定义实现
        """
        try:
            exchange_id = config.get('id')
            
            # 尝试加载自定义交易所实现
            module_name = f"exchanges.exchange_{exchange_type}"
            class_name = f"{exchange_type.capitalize()}Exchange"
            
            logging.debug(f"尝试加载自定义交易所: {module_name}.{class_name}")
            module = importlib.import_module(module_name)
            ExchangeClass = getattr(module, class_name)

            # Normalize api_keys: support both new format (api_keys dict) and legacy format (separate fields)
            api_keys = config.get('api_keys', {})
            if not api_keys:
                api_keys = {
                    'api_key': config.get('api_key'),
                    'secret': config.get('secret'), 
                    'passphrase': config.get('passphrase')
                }
            else:
                # If api_keys is new format, convert to ccxt format
                # ccxt 期望: api_key, secret (not secret), passphrase
                if isinstance(api_keys, dict):
                    api_keys = {
                        'api_key': api_keys.get('api_key'),
                        'secret': api_keys.get('secret'),
                        'passphrase': api_keys.get('passphrase')
                    }
            
            # Remove None values
            api_keys = {k: v for k, v in api_keys.items() if v is not None}
            
            # 创建自定义交易所实例
            exchange_instance = ExchangeClass(
                exchange_id=exchange_id,
                api_keys=api_keys,
                config=config
            )
            
            # 设置事件处理器（如果该实例支持）
            if hasattr(exchange_instance, 'set_data_event_handler'):
                exchange_instance.set_data_event_handler(self._handle_data_event)
            
            # 初始化交易所连接
            if hasattr(exchange_instance, 'initialize'):
                await exchange_instance.initialize()
            
            logging.info(f"✅ 已创建自定义交易所实例: {exchange_id} ({exchange_type})")
            return exchange_instance
            
        except (ImportError, AttributeError) as e:
            logging.debug(f"自定义交易所实现不存在或加载失败: {e}")
            return None
        except Exception as e:
            logging.error(f"创建交易所实例失败: {e}", exc_info=True)
            return None
    
    
    async def update_exchange(self, exchange_id: str, config: Dict[str, Any]) -> bool:
        """
        更新交易所配置并重新连接
        """
        # 先断开现有连接
        await self.remove_exchange(exchange_id)
        
        # 使用新配置添加交易所
        config['id'] = exchange_id
        return await self.add_exchange(config)
    
    async def remove_exchange(self, exchange_id: str) -> bool:
        """
        移除交易所并关闭连接
        """
        try:
            if exchange_id in self.custom_exchanges:
                exchange = self.custom_exchanges[exchange_id]
                if hasattr(exchange, 'close'):
                    await exchange.close()
                del self.custom_exchanges[exchange_id]
                logging.info(f"已移除自定义交易所: {exchange_id}")
                
            elif exchange_id in self.exchanges:
                exchange = self.exchanges[exchange_id]
                if hasattr(exchange, 'close'):
                    await exchange.close()
                del self.exchanges[exchange_id]
                logging.info(f"已移除交易所: {exchange_id}")
            
            # 清理订阅数据
            if exchange_id in self._current_subscriptions:
                del self._current_subscriptions[exchange_id]
            
            return True
        except Exception as e:
            logging.error(f"移除交易所 {exchange_id} 失败: {e}")
            return False
    
    def get_exchange(self, exchange_id: str) -> Optional[Any]:
        """
        获取交易所实例
        """
        return self.custom_exchanges.get(exchange_id) or self.exchanges.get(exchange_id)
    
    def get_all_exchanges(self) -> Dict[str, Any]:
        """
        获取所有交易所实例
        """
        return {**self.custom_exchanges, **self.exchanges}
        # """统一数据事件处理器"""
        # try:
        #     # 将事件转发给策略管理器
        #     if self.data_event_handler:
        #         await self.data_event_handler(event)
        # except Exception as e:
        #     logging.error(f"处理数据事件失败: {e}", exc_info=False)

    def set_data_event_handler(self, handler: DataEventHandler):
        """设置统一数据事件处理器"""
        self.data_event_handler = handler
    
    async def update_watched_symbols(self, active_symbols: Dict[str, List[str]], exchange_settings: Dict[str, Any] = None):
        """
        更新监听的交易对和数据类型
        
        Args:
            active_symbols: {exchange_id: [symbol1, symbol2, ...]}
            exchange_settings: {exchange_id: {default_leverage, ...}}
        """
        logging.info("更新监听交易对和数据类型...")
        
        # 检查是否有变化
        symbols_changed = False
        for exchange_id, symbols in active_symbols.items():
            current_symbols = set()
            if exchange_id in self._current_subscriptions:
                for data_type_symbols in self._current_subscriptions[exchange_id].values():
                    current_symbols.update(data_type_symbols)
            
            if current_symbols != set(symbols):
                symbols_changed = True
                break
        
        if not symbols_changed:
            logging.info("监听交易对未变化，跳过更新")
            return
        
        # 默认订阅的数据类型（仅市场数据，账户数据由全局loop处理）
        default_data_types = [
            DataEventType.TICKER,
            DataEventType.TRADE,
            DataEventType.ORDERBOOK,
            DataEventType.OHLCV,
        ]

        # 更新交易所订阅
        await self._update_exchange_subscriptions(default_data_types, active_symbols, exchange_settings)
        
        # 更新跟踪记录
        self._current_subscriptions = {}
        for exchange_id, symbols in active_symbols.items():
            if exchange_id not in self._current_subscriptions:
                self._current_subscriptions[exchange_id] = {}
                        
            for data_type in default_data_types:
                self._current_subscriptions[exchange_id][data_type] = set(symbols)

    async def _update_exchange_subscriptions(self, data_types: List[DataEventType], active_symbols: Dict[str, List[str]], exchange_settings: Dict[str, Any] = None):
        """更新交易所的数据订阅"""
        exchange_settings = exchange_settings or {}
        
        for exchange_id, symbols in active_symbols.items():
            if exchange_id not in self.exchanges or not symbols:
                continue
                
            exchange = self.exchanges[exchange_id]
            
            # 设置杠杆
            leverage = exchange_settings.get(exchange_id, {}).get('default_leverage', 10)
            await exchange.set_leverage_for_all_symbols(leverage, symbols)
            
            try:
                await exchange.subscribe_data(data_types, symbols)
                logging.info(f"Updated subscriptions for {exchange_id} with {len(symbols)} symbols")
            except Exception as e:
                logging.error(f"Failed to update subscriptions for {exchange_id}: {e}")

    async def subscribe_additional_data_types(self, exchange_id: str, data_types: List[DataEventType], symbols: List[str] = None):
        """
        订阅额外的数据类型
        
        Args:
            exchange_id: 交易所ID
            data_types: 要订阅的数据类型列表
            symbols: 要订阅的交易对列表，如果为None则使用当前活跃的交易对
        """
        if exchange_id not in self.exchanges:
            logging.error(f"交易所 {exchange_id} 未初始化")
            return
        
        exchange = self.exchanges[exchange_id]
        
        # 如果未指定交易对，使用当前活跃的交易对
        if symbols is None:
            symbols = []
            if exchange_id in self._current_subscriptions:
                for data_type_symbols in self._current_subscriptions[exchange_id].values():
                    symbols.extend(data_type_symbols)
                symbols = list(set(symbols))  # 去重
        
        if not symbols:
            logging.warning(f"没有活跃的交易对可供订阅 {exchange_id}")
            return
        
        try:
            await exchange.subscribe_data(data_types, symbols)
            
            # 更新跟踪记录
            if exchange_id not in self._current_subscriptions:
                self._current_subscriptions[exchange_id] = {}
            
            for data_type in data_types:
                if data_type not in self._current_subscriptions[exchange_id]:
                    self._current_subscriptions[exchange_id][data_type] = set()
                self._current_subscriptions[exchange_id][data_type].update(symbols)
            
            logging.info(f"Successfully subscribed to additional data types {[dt.name for dt in data_types]} for {exchange_id}")
            
        except Exception as e:
            logging.error(f"Failed to subscribe to additional data types for {exchange_id}: {e}")

    async def unsubscribe_data_types(self, exchange_id: str, data_types: List[DataEventType], symbols: List[str] = None):
        """
        取消订阅指定数据类型
        
        Args:
            exchange_id: 交易所ID
            data_types: 要取消订阅的数据类型列表
            symbols: 要取消订阅的交易对列表，如果为None则取消所有
        """
        if exchange_id not in self.exchanges:
            logging.error(f"交易所 {exchange_id} 未初始化")
            return
        
        exchange = self.exchanges[exchange_id]
        
        try:
            await exchange.unsubscribe_data(data_types, symbols)
            
            # 更新跟踪记录
            if exchange_id in self._current_subscriptions:
                for data_type in data_types:
                    if data_type in self._current_subscriptions[exchange_id]:
                        if symbols is None:
                            self._current_subscriptions[exchange_id][data_type].clear()
                        else:
                            for symbol in symbols:
                                self._current_subscriptions[exchange_id][data_type].discard(symbol)
            
            logging.info(f"Successfully unsubscribed from data types {[dt.name for dt in data_types]} for {exchange_id}")
            
        except Exception as e:
            logging.error(f"Failed to unsubscribe from data types for {exchange_id}: {e}")

    async def get_subscription_status(self) -> Dict[str, Any]:
        """获取当前订阅状态"""
        status = {}
        
        for exchange_id, exchange in self.exchanges.items():
            exchange_status = {
                'supported_data_types': [dt.name for dt in exchange.get_supported_data_types()],
                'active_subscriptions': {}
            }
            
            active_subs = exchange.get_active_subscriptions()
            for data_type, symbols in active_subs.items():
                exchange_status['active_subscriptions'][data_type.name] = list(symbols)
            
            status[exchange_id] = exchange_status
        
        return status

    async def close_all(self):
        """关闭所有交易所连接"""
        logging.info("关闭所有交易所连接...")
        
        # 关闭自定义交易所
        custom_close_tasks = [
            ex.close() if hasattr(ex, 'close') else asyncio.sleep(0)
            for ex in self.custom_exchanges.values()
        ]
        
        # 关闭 ccxt 交易所
        ccxt_close_tasks = [
            ex.close() if hasattr(ex, 'close') else asyncio.sleep(0)
            for ex in self.exchanges.values()
        ]
        
        await asyncio.gather(*custom_close_tasks, *ccxt_close_tasks, return_exceptions=True)
        
        # 清理所有数据
        self.custom_exchanges.clear()
        self.exchanges.clear()
        self._current_subscriptions.clear()
        
        logging.info("所有交易所连接已关闭")
