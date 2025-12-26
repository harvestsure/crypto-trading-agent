"""
智能交易 Agent
每个 Agent 对应一个交易所、一个交易对、一个时间框架和多个技术指标
与 LLM 交互，订阅实时市场数据，执行交易决策
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass
import pandas as pd
import pandas_ta as ta

from trading_agents.symbol_tracker import SymbolTracker
from trading_agents.base_agent import BaseAgent, AgentStatus
from models.llm_model import LLMModel
from tools.tool_registry import ToolRegistry
from exchanges.common_exchange import CommonExchange
from common.data_types import DataEventType, DataEvent
from prompts.trading_prompts import get_prompt_template

logger = logging.getLogger(__name__)


@dataclass
class MarketContext:
    """市场上下文数据"""
    symbol: str
    timeframe: str
    current_price: float
    klines: List[List]  # OHLCV数据
    indicators: Dict[str, Any]
    ticker: Optional[Dict] = None
    orderbook: Optional[Dict] = None
    
    def to_llm_prompt(self, format_func=None) -> str:
        """转换为 LLM 提示词"""
        klines_summary = f"最近{len(self.klines)}根K线数据"
        if self.klines:
            last_kline = self.klines[-1]
            klines_summary += f"\n最新K线: 开{last_kline[1]}, 高{last_kline[2]}, 低{last_kline[3]}, 收{last_kline[4]}, 量{last_kline[5]}"
        
        # 使用优化后的指标显示（如果提供了format_func）
        if format_func and callable(format_func):
            indicators_str = format_func(self.indicators)
        else:
            # 默认简单显示
            indicators_str = "\n".join([f"{k}: {v}" for k, v in self.indicators.items()])
        
        return f"""
市场数据 ({self.symbol} @ {self.timeframe}):
当前价格: {self.current_price}

{klines_summary}

技术指标:
{indicators_str}

订单簿深度: {"已加载" if self.orderbook else "未加载"}
"""


@dataclass
class PositionContext:
    """持仓上下文数据"""
    positions: List[Dict]
    total_value: float
    total_pnl: float
    leverage: int
    
    def to_llm_prompt(self) -> str:
        """转换为 LLM 提示词"""
        if not self.positions:
            return "当前持仓: 无持仓"
        
        positions_str = ""
        for pos in self.positions:
            side = pos.get('side', 'N/A')
            contracts = pos.get('contracts', 0)
            entry_price = pos.get('entryPrice', 0)
            current_price = pos.get('markPrice', 0)
            pnl = pos.get('unrealizedPnl', 0)
            pnl_percent = pos.get('percentage', 0)
            
            positions_str += f"""
- {side.upper()} {contracts}张 @ {entry_price}
  当前价格: {current_price}
  浮动盈亏: {pnl:.2f} ({pnl_percent:.2f}%)
"""
        
        return f"""
持仓信息:
杠杆倍数: {self.leverage}x
持仓总价值: {self.total_value:.2f}
总浮动盈亏: {self.total_pnl:.2f}
{positions_str}
"""


@dataclass
class AccountContext:
    """账户上下文数据"""
    balance: Dict[str, Any]
    available_margin: float
    used_margin: float
    margin_ratio: float
    
    def to_llm_prompt(self) -> str:
        """转换为 LLM 提示词"""
        return f"""
账户信息:
可用保证金: {self.available_margin:.2f}
已用保证金: {self.used_margin:.2f}
保证金率: {self.margin_ratio:.2%}
"""


@dataclass
class OrderContext:
    """订单上下文数据"""
    open_orders: List[Dict]
    pending_count: int
    total_order_value: float
    
    def to_llm_prompt(self) -> str:
        """转换为 LLM 提示词"""
        if not self.open_orders:
            return "未成交订单: 无"
        
        orders_str = ""
        for order in self.open_orders:
            side = order.get('side', 'N/A')
            symbol = order.get('symbol', 'N/A')
            price = order.get('price', 0)
            amount = order.get('amount', 0)
            status = order.get('status', 'N/A')
            order_type = order.get('type', 'N/A')
            
            orders_str += f"""
  - {side.upper()} {symbol} @ {price} x {amount}
    类型: {order_type} | 状态: {status}
"""
        
        return f"""
未成交订单:
订单数量: {self.pending_count}
订单总价值: {self.total_order_value:.2f}
{orders_str}
"""


class SmartTradingAgent(BaseAgent):
    """
    智能交易 Agent
    
    功能:
    1. 订阅实时市场数据 (K线、Ticker、订单簿、成交)
    2. 收集持仓和账户信息
    3. 与 LLM 交互，获取交易决策
    4. 执行交易指令 (开多/开空/平仓/条件止盈止损/持有)
    5. 使用 Tools 扩展功能
    """
    
    def __init__(
        self,
        agent_id: str,
        name: str,
        exchange: CommonExchange,
        symbols: List[str],
        timeframe: str,
        indicators: List[str],
        llm_model: LLMModel,
        tool_registry: ToolRegistry,
        system_prompt: str,
        config: Dict[str, Any] = None,
    ):
        super().__init__(agent_id, name)
        
        self.exchange = exchange
        self.symbols = symbols
        self.timeframe = timeframe
        self.indicators = indicators
        self.llm_model = llm_model
        self.tool_registry = tool_registry
        self.system_prompt = system_prompt
        self.config = config or {}
        
        # 数据缓存
        self.current_ticker: Optional[Dict] = None
        self.current_orderbook: Optional[Dict] = None
        self.current_positions: List[Dict] = []
        self.current_balance: Dict[str, Any] = {}

        # 决策循环任务
        self.decision_loop_task: Optional[asyncio.Task] = None
        
        # 配置参数
        self.max_position_size = self.config.get('max_position_size', 1000.0)
        self.risk_per_trade = self.config.get('risk_per_trade', 0.02)
        self.default_leverage = self.config.get('default_leverage', 1)
        self.decision_interval = self.config.get('decision_interval', 60)  # 决策间隔(秒)
        self.indicator_window_size = self.config.get('indicator_window_size', 15)  # 指标窗口大小（传给LLM的数据点数）
        
        # 初始化对话
        self.llm_model.create_conversation(self.system_prompt)
        
        # K线数据管理（使用DataFrame字典，每个symbol一个）
        self.dfs: Dict[str, pd.DataFrame] = {}
        for symbol in self.symbols:
            df = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            self.dfs[symbol] = df
        
        # 数据处理参数（每个symbol独立追踪）
        self.max_kline_history = self.config.get('max_kline_history', 500)
        self.last_kline_timestamps: Dict[str, Optional[int]] = {symbol: None for symbol in self.symbols}
        self.last_decision_time = 0  # 上次决策时间
        self.min_decision_interval = self.config.get('min_decision_interval', 120)  # 最小决策间隔(秒)
        self.lock = asyncio.Lock()
        self.symbol_trackers: Dict[str, SymbolTracker] = {}

        logger.info(f"SmartTradingAgent {self.name} initialized for (symbols={self.symbols}) @ {self.timeframe}")
    
    async def _on_initialize(self):
        """初始化 Agent"""

        for symbol in self.symbols:
            self.symbol_trackers[symbol] = SymbolTracker(self.exchange.exchange_id, symbol)
        # 1. 加载历史K线
        await self._load_historical_klines()
               
        # 2. 启动决策循环
        self.decision_loop_task = asyncio.create_task(self._decision_loop())
        
        logger.info(f"Agent {self.name} initialized and running")
    
    async def _on_cleanup(self):
        """清理资源"""
        # 停止决策循环
        if self.decision_loop_task:
            self.decision_loop_task.cancel()
            try:
                await self.decision_loop_task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"Agent {self.name} cleaned up")
    
    async def execute(self, task: str, context: Optional[Dict[str, Any]] = None):
        """
        执行任务（实现抽象方法）
        对于 SmartTradingAgent，实时决策循环已在 _on_initialize 中启动
        此方法提供外部执行接口
        
        Args:
            task: 任务描述
            context: 执行上下文
        """
        self.current_task = task
        self.add_message("user", task)
        logger.info(f"Agent {self.name} executing task: {task}")
        
        # SmartTradingAgent 通过自动决策循环运行，这里主要作为接口实现
        # 如果需要执行特定任务，可以将其添加到任务队列
        # 当前实现中，Agent 已在 _on_initialize 中启动自动决策循环
    
    async def _load_historical_klines(self):
        """加载历史K线数据并初始化指标"""
        try:
            for symbol in self.symbols:
                logger.info(f"Loading historical klines for {symbol} @ {self.timeframe}")
                
                # 加载最近500根K线
                klines = await self.exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=self.timeframe,
                    limit=self.max_kline_history
                )
                
                if klines:
                    logger.info(f"Loaded {len(klines)} historical klines for {symbol}")
                    
                    # 构建DataFrame并计算指标
                    await self._process_klines_batch(symbol, klines, is_history=True)
                else:
                    logger.warning(f"No historical klines loaded for {symbol}")
                    
        except Exception as e:
            logger.error(f"Error loading historical klines: {e}", exc_info=True)   


    # ========== 数据事件回调 ==========
    
    async def _on_kline_update(self, event: DataEvent):
        """K线更新回调 - 处理新K线和K线更新"""
        try:
            symbol = event.symbol
            if symbol not in self.symbols:
                return
                
            kline = event.data
            current_time = datetime.now().timestamp()
            
            async with self.lock:
                # 检查是否是新K线：比较时间戳
                is_new_candle = False
                last_ts = self.last_kline_timestamps.get(symbol)
                if last_ts is None or kline[0] > last_ts:
                    is_new_candle = True
                    self.last_kline_timestamps[symbol] = kline[0]
                
                # 处理K线数据
                await self._process_kline_update(symbol, kline, is_new_candle, current_time)
                
                logger.debug(f"{symbol} Kline {'new' if is_new_candle else 'updated'}: O={kline[1]}, H={kline[2]}, L={kline[3]}, C={kline[4]}")
        except Exception as e:
            logger.error(f"Error handling kline update: {e}", exc_info=True)
    
    async def _on_ticker_update(self, event: DataEvent):
        """Ticker更新回调"""
        self.current_ticker = event.data
        logger.debug(f"Ticker updated: {event.data.get('last', 'N/A')}")
    
    async def _on_orderbook_update(self, event: DataEvent):
        """订单簿更新回调"""
        self.current_orderbook = event.data
        logger.debug(f"Orderbook updated")
    
    async def _on_position_update(self, event: DataEvent):
        """持仓更新回调"""
        position = event.data
        # 更新持仓列表
        symbol = position.get('symbol')
        existing = [p for p in self.current_positions if p.get('symbol') == symbol]
        if existing:
            # 更新现有持仓
            idx = self.current_positions.index(existing[0])
            self.current_positions[idx] = position
        else:
            # 添加新持仓
            self.current_positions.append(position)
        
        logger.info(f"Position updated: {symbol} - {position.get('side')} {position.get('contracts')} @ {position.get('entryPrice')}")
    
    async def _on_order_update(self, event: DataEvent):
        """订单更新回调"""
        order = event.data
        logger.info(f"Order updated: {order.get('id')} - {order.get('status')}")
    
    # ========== 决策循环 ==========
    
    async def _decision_loop(self):
        """主决策循环"""
        logger.info(f"Starting decision loop for {self.name}")
        
        try:
            while True:
                try:
                    # 检查是否被暂停 — 如果暂停则退出决策循环，等待由外部 resume() 重新启动
                    if self.status == AgentStatus.PAUSED:
                        logger.info(f"Agent {self.name} paused — stopping decision loop")
                        return
                    
                    # 执行一次决策
                    await self._make_decision()
                except Exception as e:
                    logger.error(f"Error in decision loop: {e}", exc_info=True)
                    self.set_error(f"Decision error: {str(e)}")
                
                # 等待下一次决策
                await asyncio.sleep(self.decision_interval)
                
        except asyncio.CancelledError:
            logger.info(f"Decision loop cancelled for {self.name}")
    
    async def _make_decision(self):
        """执行一次决策"""
        self.set_status(AgentStatus.THINKING, "Analyzing market and making decision")
        
        try:
            # 1. 收集市场数据（所有symbols）
            market_contexts = self._build_market_context()
            
            if not market_contexts:
                logger.warning("No market data available for decision")
                self.set_status(AgentStatus.IDLE)
                return
            
            # 2. 收集持仓数据
            position_context = self._build_position_context()
            
            # 3. 收集账户数据
            account_context = await self._build_account_context()
            
            # 4. 收集订单数据
            order_context = await self._build_order_context()
            
            # 5. 构建 LLM 提示词
            prompt = self._build_llm_prompt(market_contexts, position_context, account_context, order_context)
            
            # 6. 获取工具定义
            tools = self.tool_registry.get_openai_tools()
            
            # 7. 调用 LLM (使用异步调用避免阻塞事件循环)
            logger.info(f"Calling LLM for decision...")
            response = await self.llm_model.chat_completion_async(
                user_message=prompt,
                tools=tools if tools else None,
            )
            
            # 8. 处理 LLM 响应
            await self._process_llm_response(response, market_contexts, position_context)
            
            self.set_status(AgentStatus.IDLE)
            
        except Exception as e:
            logger.error(f"Error making decision: {e}", exc_info=True)
            raise

    async def pause(self):
        """Pause the agent by cancelling its decision loop task."""
        if self.decision_loop_task:
            self.decision_loop_task.cancel()
            try:
                await self.decision_loop_task
            except asyncio.CancelledError:
                pass
            self.decision_loop_task = None
            logger.info(f"Agent {self.name} decision loop paused")

    async def resume(self):
        """Resume the agent by starting the decision loop if not running."""
        if not self.decision_loop_task or self.decision_loop_task.done():
            self.decision_loop_task = asyncio.create_task(self._decision_loop())
            logger.info(f"Agent {self.name} decision loop resumed")
    
    def _build_market_context(self) -> List[MarketContext]:
        """构建市场上下文 - 返回所有symbols的市场数据"""
        contexts = []
        
        for symbol in self.symbols:
            df = self.dfs.get(symbol)
            if df is None or len(df) == 0:
                continue
                
            # 计算技术指标
            indicators = self._calculate_indicators(symbol)
            
            # 获取当前价格
            current_price = float(df['close'].iloc[-1])
            
            # 获取最近N根K线数据
            klines = []
            for idx, row in df.tail(self.indicator_window_size).iterrows():
                klines.append([
                    int(idx.timestamp() * 1000),
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    float(row['volume'])
                ])
            
            contexts.append(MarketContext(
                symbol=symbol,
                timeframe=self.timeframe,
                current_price=current_price,
                klines=klines,
                indicators=indicators,
                ticker=self.current_ticker,
                orderbook=self.current_orderbook,
            ))
        
        return contexts
    
    def _build_position_context(self) -> PositionContext:
        """构建持仓上下文"""
        total_value = 0.0
        total_pnl = 0.0
        
        # 收集所有symbols的持仓
        symbol_positions = [p for p in self.current_positions if p.get('symbol') in self.symbols]
        
        for pos in symbol_positions:
            total_value += abs(pos.get('notional', 0))
            total_pnl += pos.get('unrealizedPnl', 0)
        
        return PositionContext(
            positions=symbol_positions,
            total_value=total_value,
            total_pnl=total_pnl,
            leverage=self.default_leverage,
        )
    
    async def _build_account_context(self) -> AccountContext:
        """构建账户上下文"""
        # 获取余额信息
        try:
            balance = await self.exchange.fetch_balance()
            self.current_balance = balance
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            balance = self.current_balance
        
        # 提取保证金信息
        # 从balance中获取结算币种 (例如USDT)
        settlement_currency = self._get_settlement_currency()
        currency_balance = balance.get(settlement_currency, {})
        
        available_margin = currency_balance.get('free', 0)
        used_margin = currency_balance.get('used', 0)
        total_margin = currency_balance.get('total', 0)
        
        margin_ratio = used_margin / total_margin if total_margin > 0 else 0
        
        return AccountContext(
            balance=balance,
            available_margin=available_margin,
            used_margin=used_margin,
            margin_ratio=margin_ratio,
        )
    
    async def _build_order_context(self) -> OrderContext:
        """构建订单上下文 - 获取未成交订单"""
        open_orders = []
        total_value = 0.0
        
        try:
            # 获取所有监控交易对的未成交订单
            for symbol in self.symbols:
                try:
                    orders = await self.exchange.fetch_open_orders(symbol)
                    if orders:
                        open_orders.extend(orders)
                        # 计算订单总价值
                        for order in orders:
                            price = order.get('price', 0)
                            amount = order.get('amount', 0)
                            total_value += price * amount
                except Exception as e:
                    logger.debug(f"Error fetching orders for {symbol}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error building order context: {e}")
        
        return OrderContext(
            open_orders=open_orders,
            pending_count=len(open_orders),
            total_order_value=total_value,
        )
    
    def _get_settlement_currency(self) -> str:
        """获取结算币种"""
        # 从第一个symbol中提取，例如 BTC/USDT:USDT -> USDT
        if not self.symbols:
            return 'USDT'
        symbol = self.symbols[0]
        if ':' in symbol:
            return symbol.split(':')[1]
        elif '/' in symbol:
            return symbol.split('/')[1]
        return 'USDT'
    
    def _summarize_indicator_trend(self, indicator_name: str, data: List[float]) -> str:
        """
        将指标数据总结为趋势描述，减少token消耗
        """
        if not data or len(data) < 2:
            return f"{indicator_name}: 数据不足"
        
        current = data[-1]
        previous = data[-2]
        change = current - previous
        change_pct = (change / previous * 100) if previous != 0 else 0
        
        # 判断趋势
        if len(data) >= 5:
            recent_trend = data[-5:]
            is_rising = all(recent_trend[i] <= recent_trend[i+1] for i in range(len(recent_trend)-1))
            is_falling = all(recent_trend[i] >= recent_trend[i+1] for i in range(len(recent_trend)-1))
            trend = "上升" if is_rising else "下降" if is_falling else "震荡"
        else:
            trend = "上升" if change > 0 else "下降"
        
        # 特殊指标的额外判断
        extra_info = ""
        if indicator_name == "RSI":
            if current > 70:
                extra_info = " [超买区]"
            elif current < 30:
                extra_info = " [超卖区]"
        elif indicator_name == "MACD_Histogram":
            if current > 0 and previous <= 0:
                extra_info = " [金叉]"
            elif current < 0 and previous >= 0:
                extra_info = " [死叉]"
        
        return f"{indicator_name}: {current:.2f} (趋势: {trend}, 变化: {change:+.2f}/{change_pct:+.2f}%){extra_info}"
    
    def _format_indicators_summary(self, indicators: Dict[str, Any]) -> str:
        """
        将指标数据格式化为简洁的总结
        """
        if not indicators:
            return "技术指标: 无数据"
        
        summary_lines = []
        for key, value in indicators.items():
            if isinstance(value, list) and value:
                summary_lines.append(self._summarize_indicator_trend(key, value))
            elif isinstance(value, (int, float)):
                summary_lines.append(f"{key}: {value:.2f}")
        
        return "\n".join(summary_lines)
    
    def _calculate_indicators(self, symbol: str) -> Dict[str, Any]:
        """
        获取指标数据（从DataFrame中读取）
        根据 self.indicators 列表动态计算指定的指标
        返回最近N个数据点的序列数据（N由indicator_window_size配置）
        """
        indicators = {}
        
        df = self.dfs.get(symbol)
        if df is None or len(df) == 0:
            return indicators
        
        # 获取最近N条数据
        df_tail = df.tail(self.indicator_window_size)
        
        # 根据 self.indicators 列表动态收集指标
        for indicator_name in self.indicators:
            indicator_lower = indicator_name.lower()
            
            # RSI
            if indicator_lower == 'rsi' and 'RSI' in df.columns:
                rsi_data = df_tail['RSI'].dropna().tolist()
                if rsi_data:
                    indicators['RSI'] = rsi_data
            
            # EMA
            elif indicator_lower == 'ema':
                if 'EMA_20' in df.columns:
                    ema20_data = df_tail['EMA_20'].dropna().tolist()
                    if ema20_data:
                        indicators['EMA_20'] = ema20_data
                if 'EMA_50' in df.columns:
                    ema50_data = df_tail['EMA_50'].dropna().tolist()
                    if ema50_data:
                        indicators['EMA_50'] = ema50_data
            
            # SMA
            elif indicator_lower == 'sma':
                if 'SMA_20' in df.columns:
                    sma20_data = df_tail['SMA_20'].dropna().tolist()
                    if sma20_data:
                        indicators['SMA_20'] = sma20_data
                if 'SMA_50' in df.columns:
                    sma50_data = df_tail['SMA_50'].dropna().tolist()
                    if sma50_data:
                        indicators['SMA_50'] = sma50_data
            
            # MACD
            elif indicator_lower == 'macd':
                if 'MACD' in df.columns:
                    macd_data = df_tail['MACD'].dropna().tolist()
                    if macd_data:
                        indicators['MACD'] = macd_data
                if 'MACD_Signal' in df.columns:
                    signal_data = df_tail['MACD_Signal'].dropna().tolist()
                    if signal_data:
                        indicators['MACD_Signal'] = signal_data
                if 'MACD_Histogram' in df.columns:
                    hist_data = df_tail['MACD_Histogram'].dropna().tolist()
                    if hist_data:
                        indicators['MACD_Histogram'] = hist_data
            
            # Bollinger Bands
            elif indicator_lower in ['bb', 'bollinger']:
                if 'BB_Upper' in df.columns:
                    bb_upper = df_tail['BB_Upper'].dropna().tolist()
                    if bb_upper:
                        indicators['BB_Upper'] = bb_upper
                if 'BB_Middle' in df.columns:
                    bb_middle = df_tail['BB_Middle'].dropna().tolist()
                    if bb_middle:
                        indicators['BB_Middle'] = bb_middle
                if 'BB_Lower' in df.columns:
                    bb_lower = df_tail['BB_Lower'].dropna().tolist()
                    if bb_lower:
                        indicators['BB_Lower'] = bb_lower
            
            # ATR
            elif indicator_lower == 'atr' and 'ATR' in df.columns:
                atr_data = df_tail['ATR'].dropna().tolist()
                if atr_data:
                    indicators['ATR'] = atr_data
            
            # KDJ / Stochastic
            elif indicator_lower in ['kdj', 'stoch', 'stochastic']:
                if 'K' in df.columns:
                    k_data = df_tail['K'].dropna().tolist()
                    if k_data:
                        indicators['K'] = k_data
                if 'D' in df.columns:
                    d_data = df_tail['D'].dropna().tolist()
                    if d_data:
                        indicators['D'] = d_data
            
            # ADX
            elif indicator_lower == 'adx' and 'ADX' in df.columns:
                adx_data = df_tail['ADX'].dropna().tolist()
                if adx_data:
                    indicators['ADX'] = adx_data
            
            # Volume
            elif indicator_lower == 'volume':
                if 'Volume' in df.columns:
                    vol_data = df_tail['Volume'].dropna().tolist()
                    if vol_data:
                        indicators['Volume'] = vol_data
                if 'AvgVolume_20' in df.columns:
                    avg_vol_data = df_tail['AvgVolume_20'].dropna().tolist()
                    if avg_vol_data:
                        indicators['AvgVolume_20'] = avg_vol_data
        
        return indicators
    
    
    async def _process_klines_batch(self, symbol: str, klines: List[List], is_history: bool = False):
        """批量处理K线数据（历史加载）"""
        try:
            # 构建DataFrame
            df_new = pd.DataFrame(
                klines,
                columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df_new["timestamp"] = pd.to_datetime(df_new["timestamp"], unit="ms")
            df_new.set_index("timestamp", inplace=True)
            
            if is_history:
                self.dfs[symbol] = df_new.copy()
            else:
                self.dfs[symbol] = pd.concat([self.dfs[symbol], df_new]).drop_duplicates()
            
            # 保持最多max_kline_history行
            if len(self.dfs[symbol]) > self.max_kline_history:
                self.dfs[symbol] = self.dfs[symbol].iloc[-self.max_kline_history:]
            
            # 计算所有指标
            await self._calculate_all_indicators(symbol)
            
            logger.debug(f"{symbol}: Processed {len(df_new)} klines, total in df: {len(self.dfs[symbol])}")
        except Exception as e:
            logger.error(f"Error processing klines batch for {symbol}: {e}", exc_info=True)
    
    async def _finalize_last_candle_indicators(self, symbol: str):
        """
        对前一条K线进行指标最终化
        当新K线到达时，使用完整的前一K线数据重新计算其指标
        确保每条K线有完整且准确的指标数据
        """
        try:
            df = self.dfs.get(symbol)
            if df is None or len(df) < 2:
                return
            
            # 只对前一条进行指标更新，使用完整的历史数据
            last_idx = df.index[-1]
            df_copy = df.copy()
            
            # 根据 self.indicators 列表动态更新
            for indicator_name in self.indicators:
                indicator_lower = indicator_name.lower()
                
                # RSI
                if indicator_lower == 'rsi':
                    rsi = ta.rsi(df_copy['close'], length=14)
                    if rsi is not None and len(rsi) >= 2:
                        self.dfs[symbol].loc[last_idx, 'RSI'] = rsi.iloc[-2]
                
                # EMA
                elif indicator_lower == 'ema':
                    ema20 = ta.ema(df_copy['close'], length=20)
                    ema50 = ta.ema(df_copy['close'], length=50)
                    if ema20 is not None and len(ema20) >= 2:
                        self.dfs[symbol].loc[last_idx, 'EMA_20'] = ema20.iloc[-2]
                    if ema50 is not None and len(ema50) >= 2:
                        self.dfs[symbol].loc[last_idx, 'EMA_50'] = ema50.iloc[-2]
                
                # MACD
                elif indicator_lower == 'macd':
                    macd_result = ta.macd(df_copy['close'])
                    if macd_result is not None and len(macd_result.columns) >= 3 and len(macd_result) >= 2:
                        self.dfs[symbol].loc[last_idx, 'MACD'] = macd_result.iloc[-2, 0]
                        self.dfs[symbol].loc[last_idx, 'MACD_Signal'] = macd_result.iloc[-2, 1]
                        self.dfs[symbol].loc[last_idx, 'MACD_Histogram'] = macd_result.iloc[-2, 2]
            
            logger.debug(f"{symbol}: Finalized indicators for candle {last_idx}")
        except Exception as e:
            logger.debug(f"{symbol}: Error finalizing last candle indicators: {e}")
    
    async def _process_kline_update(self, symbol: str, kline: List, is_new_candle: bool, current_time: float):
        """处理单条K线更新（动态更新）
        
        分两种情况处理：
        1. 新K线（新的时间）：保存前一K线指标，添加新K线，触发决策
        2. K线更新（同一时间更新）：更新当前K线，定时触发决策
        """
        try:
            df = self.dfs.get(symbol)
            if df is None:
                return
                
            ts = pd.Timestamp(kline[0], unit="ms")
            trigger_decision = False
            
            if is_new_candle and len(df) > 0:
                # ===== 新K线情况 =====
                # 1. 对前一条K线进行最终指标计算
                await self._finalize_last_candle_indicators(symbol)
                
                # 2. 添加新K线
                new_row = pd.Series({
                    'open': kline[1],
                    'high': kline[2],
                    'low': kline[3],
                    'close': kline[4],
                    'volume': kline[5],
                }, index=['open', 'high', 'low', 'close', 'volume'])
                
                self.dfs[symbol].loc[ts] = new_row
                
                # 3. 计算新K线的指标
                await self._calculate_all_indicators(symbol)
                
                # 4. 标记应该触发决策
                self.last_decision_time = current_time
                trigger_decision = True
                
                logger.info(f"{symbol}: New candle at {ts}, triggering decision")
                
            else:
                # ===== K线更新情况 =====
                # 当前K线还在形成中，仅更新数据
                if ts not in df.index:
                    new_row = pd.Series({
                        'open': kline[1],
                        'high': kline[2],
                        'low': kline[3],
                        'close': kline[4],
                        'volume': kline[5],
                    }, index=['open', 'high', 'low', 'close', 'volume'])
                    self.dfs[symbol].loc[ts] = new_row
                else:
                    # 更新现有行
                    self.dfs[symbol].loc[ts, 'open'] = kline[1]
                    self.dfs[symbol].loc[ts, 'high'] = kline[2]
                    self.dfs[symbol].loc[ts, 'low'] = kline[3]
                    self.dfs[symbol].loc[ts, 'close'] = kline[4]
                    self.dfs[symbol].loc[ts, 'volume'] = kline[5]
                
                # 计算最新指标（仅更新最后一行，提高性能）
                await self._calculate_all_indicators(symbol)
                
                # 定时触发决策（每5秒检查一次）
                if current_time - self.last_decision_time >= self.min_decision_interval:
                    self.last_decision_time = current_time
                    trigger_decision = True
                    logger.debug(f"{symbol}: Time-based decision trigger at {ts}")
            
            # 保持历史数据容量
            if len(self.dfs[symbol]) > self.max_kline_history:
                self.dfs[symbol] = self.dfs[symbol].iloc[-self.max_kline_history:]
            
            # 触发决策（如果条件满足）
            if trigger_decision:
                # 在后台执行，不阻塞数据更新
                asyncio.create_task(self._make_decision())
                
        except Exception as e:
            logger.error(f"{symbol}: Error processing kline update: {e}", exc_info=True)
    
    async def _calculate_all_indicators(self, symbol: str):
        """
        计算技术指标
        仅计算 self.indicators 中指定的指标
        """
        try:
            df = self.dfs.get(symbol)
            if df is None or len(df) < 20:
                return
            
            df_copy = df.copy()
            
            # 根据 self.indicators 列表动态计算
            for indicator_name in self.indicators:
                indicator_lower = indicator_name.lower()
                
                # RSI
                if indicator_lower == 'rsi':
                    rsi = ta.rsi(df_copy['close'], length=14)
                    if rsi is not None and len(rsi) > 0:
                        self.dfs[symbol]['RSI'] = rsi
                
                # EMA
                elif indicator_lower == 'ema':
                    ema20 = ta.ema(df_copy['close'], length=20)
                    ema50 = ta.ema(df_copy['close'], length=50)
                    if ema20 is not None:
                        self.dfs[symbol]['EMA_20'] = ema20
                    if ema50 is not None:
                        self.dfs[symbol]['EMA_50'] = ema50
                
                # SMA
                elif indicator_lower == 'sma':
                    sma20 = ta.sma(df_copy['close'], length=20)
                    sma50 = ta.sma(df_copy['close'], length=50)
                    if sma20 is not None:
                        self.dfs[symbol]['SMA_20'] = sma20
                    if sma50 is not None:
                        self.dfs[symbol]['SMA_50'] = sma50
                
                # MACD
                elif indicator_lower == 'macd':
                    macd_result = ta.macd(df_copy['close'])
                    if macd_result is not None and len(macd_result.columns) >= 3:
                        self.dfs[symbol]['MACD'] = macd_result.iloc[:, 0]
                        self.dfs[symbol]['MACD_Signal'] = macd_result.iloc[:, 1]
                        self.dfs[symbol]['MACD_Histogram'] = macd_result.iloc[:, 2]
                
                # Bollinger Bands
                elif indicator_lower in ['bb', 'bollinger']:
                    bb_result = ta.bbands(df_copy['close'], length=20, std=2)
                    if bb_result is not None and len(bb_result.columns) >= 3:
                        self.dfs[symbol]['BB_Upper'] = bb_result.iloc[:, 0]
                        self.dfs[symbol]['BB_Middle'] = bb_result.iloc[:, 1]
                        self.dfs[symbol]['BB_Lower'] = bb_result.iloc[:, 2]
                
                # ATR
                elif indicator_lower == 'atr':
                    atr = ta.atr(df_copy['high'], df_copy['low'], df_copy['close'], length=14)
                    if atr is not None:
                        self.dfs[symbol]['ATR'] = atr
                
                # KDJ / Stochastic
                elif indicator_lower in ['kdj', 'stoch', 'stochastic']:
                    stoch_result = ta.stoch(df_copy['high'], df_copy['low'], df_copy['close'], k=14, d=3)
                    if stoch_result is not None and len(stoch_result.columns) >= 2:
                        self.dfs[symbol]['K'] = stoch_result.iloc[:, 0]
                        self.dfs[symbol]['D'] = stoch_result.iloc[:, 1]
                
                # ADX
                elif indicator_lower == 'adx':
                    try:
                        adx_result = ta.adx(df_copy['high'], df_copy['low'], df_copy['close'], length=14)
                        adx_col = next((c for c in adx_result.columns if 'ADX' in c.upper()), None)
                        if adx_col:
                            self.dfs[symbol]['ADX'] = adx_result[adx_col]
                    except Exception:
                        pass
                
                # Volume
                elif indicator_lower == 'volume':
                    self.dfs[symbol]['Volume'] = df_copy['volume']
                    self.dfs[symbol]['AvgVolume_20'] = df_copy['volume'].rolling(window=20).mean()
            
            logger.debug(f"{symbol}: Indicators calculated for {len(self.dfs[symbol])} rows")
        except Exception as e:
            logger.error(f"{symbol}: Error calculating indicators: {e}", exc_info=True)
    
    def _build_llm_prompt(
        self,
        markets: List[MarketContext],
        position: PositionContext,
        account: AccountContext,
        orders: OrderContext
    ) -> str:
        """构建LLM提示词"""
        # 构建所有交易对的市场数据（使用优化后的显示）
        markets_str = "\n\n".join([
            market.to_llm_prompt(format_func=self._format_indicators_summary) 
            for market in markets
        ])
        
        prompt = f"""
{get_prompt_template()}

=== 监控的交易对 ===
{', '.join(self.symbols)}

=== 市场数据 ===
{markets_str}

{position.to_llm_prompt()}

{account.to_llm_prompt()}

{orders.to_llm_prompt()}

配置参数:
- 最大持仓规模: {self.max_position_size}
- 单笔风险比例: {self.risk_per_trade * 100}%
- 默认杠杆: {self.default_leverage}x

请分析以上所有交易对的市场状况，并决定下一步操作。你可以：
1. 开多仓 (LONG) - 看涨时建立多头仓位（需指定symbol）
2. 开空仓 (SHORT) - 看跌时建立空头仓位（需指定symbol）
3. 平仓 (CLOSE) - 关闭当前持仓（需指定symbol）
4. 设置条件止盈 (TAKE_PROFIT) - 价格达到目标时自动平仓
5. 设置条件止损 (STOP_LOSS) - 价格跌破止损位时自动平仓
6. 持有 (HOLD) - 保持当前状态，不做操作

注意：
- 如果已有未成交订单，请考虑是否需要取消或调整
- 每次开仓后应立即设置止损止盈
- 避免同时对同一交易对建立多个相同方向的仓位

如果需要执行交易，请使用相应的工具函数，并务必指定正确的symbol参数。
请给出你的分析和建议。
"""
        return prompt
    
    async def _process_llm_response(
        self,
        response: Dict[str, Any],
        markets: List[MarketContext],
        position: PositionContext
    ):
        """处理LLM响应"""
        # 记录LLM回复
        content = response.get('content', '')
        logger.info(f"LLM Response: {content[:200]}...")
        
        # 记录消息到对话历史
        self.add_message("assistant", content)
        
        # 检查是否有工具调用
        tool_calls = response.get('tool_calls', [])
        if tool_calls:
            self.set_status(AgentStatus.EXECUTING_TOOL, f"Executing {len(tool_calls)} tool(s)")
            
            # 执行工具调用
            from tools.tool_registry import ToolExecutor
            executor = ToolExecutor(self.tool_registry)
            
            results = []
            tool_results_summary = []  # 收集工具执行结果摘要
            
            for tool_call in tool_calls:
                tool_call_id = tool_call['id']
                tool_name = tool_call['function']['name']
                arguments = json.loads(tool_call['function']['arguments'])
                
                logger.info(f"Executing tool: {tool_name} with args: {arguments}")
                
                result = await executor.execute_tool_call(
                    tool_name=tool_name,
                    tool_call_id=tool_call_id,
                    arguments=arguments
                )
                
                results.append(result)
                
                # 记录工具调用到Agent统计
                self.record_tool_call(
                    tool_name=tool_name,
                    arguments=arguments,
                    result=result.get('result'),
                    error=result.get('error'),
                    duration_ms=result.get('execution_time', 0) * 1000
                )
                
                # 构建工具执行结果摘要
                if result['status'] == 'success':
                    logger.info(f"Tool {result['tool_name']} executed successfully")
                    tool_results_summary.append(
                        f"✓ {tool_name}({json.dumps(arguments, ensure_ascii=False)}): "
                        f"成功 - {json.dumps(result.get('result'), ensure_ascii=False)}"
                    )
                else:
                    logger.error(f"Tool {result['tool_name']} failed: {result.get('error')}")
                    tool_results_summary.append(
                        f"✗ {tool_name}({json.dumps(arguments, ensure_ascii=False)}): "
                        f"失败 - {result.get('error')}"
                    )
            
            # 将工具执行结果添加到对话历史
            if tool_results_summary:
                tool_results_msg = "工具执行结果:\n" + "\n".join(tool_results_summary)
                self.add_message("system", tool_results_msg)
                logger.info(f"Tool execution summary: {tool_results_msg}")
                
                # 可选：让LLM查看工具执行结果并给出反馈
                # 这样LLM可以基于执行结果调整后续决策
                try:
                    feedback_prompt = f"""
以上工具已执行完成。请总结执行情况：
{tool_results_msg}

如有需要，请说明下一步建议。
"""
                    feedback_response = await self.llm_model.chat_completion_async(
                        user_message=feedback_prompt,
                        tools=None  # 反馈阶段不需要工具
                    )
                    
                    feedback_content = feedback_response.get('content', '')
                    if feedback_content:
                        logger.info(f"LLM Feedback: {feedback_content[:200]}...")
                        self.add_message("assistant", feedback_content)
                except Exception as e:
                    logger.error(f"Error getting LLM feedback: {e}")
        else:
            logger.info("No tool calls in LLM response")

    async def on_data_event(self, event: DataEvent):
        try:
            symbol = event.symbol
      
            # 对于全局事件（如余额），分发到该交易所的所有策略
            if symbol and symbol in self.symbols and symbol in self.symbol_trackers:
                symbol_tracker = self.symbol_trackers[symbol]
                if symbol_tracker:
                    await symbol_tracker.on_data_event(event)                    
        except Exception as e:
            logging.error(f"处理数据事件失败: {e}", exc_info=False)
    
    def get_agent_info(self) -> Dict[str, Any]:
        """获取Agent信息"""
        # 收集每个symbol的K线数量和当前价格
        symbols_info = {}
        for symbol in self.symbols:
            df = self.dfs.get(symbol)
            symbols_info[symbol] = {
                'klines_count': len(df) if df is not None else 0,
                'current_price': float(df['close'].iloc[-1]) if df is not None and len(df) > 0 else None
            }
        
        return {
            **self.get_stats(),
            'exchange': self.exchange.exchange_id,
            'symbols': self.symbols,
            'timeframe': self.timeframe,
            'indicators': self.indicators,
            'symbols_info': symbols_info,
            'positions': self.current_positions,
        }
