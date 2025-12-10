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
from dataclasses import dataclass, asdict

import pandas as pd
import pandas_ta as ta
import numpy as np

from agents.base_agent import BaseAgent, AgentStatus
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
    
    def to_llm_prompt(self) -> str:
        """转换为 LLM 提示词"""
        klines_summary = f"最近{len(self.klines)}根K线数据"
        if self.klines:
            last_kline = self.klines[-1]
            klines_summary += f"\n最新K线: 开{last_kline[1]}, 高{last_kline[2]}, 低{last_kline[3]}, 收{last_kline[4]}, 量{last_kline[5]}"
        
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
        symbol: str,
        symbols: Optional[List[str]],
        timeframe: str,
        indicators: List[str],
        llm_model: LLMModel,
        tool_registry: ToolRegistry,
        system_prompt: str,
        config: Dict[str, Any] = None,
    ):
        super().__init__(agent_id, name)
        
        self.exchange = exchange
        # support multiple symbols; keep primary symbol for backward compatibility
        self.symbols = symbols or ([symbol] if symbol else [])
        self.symbol = self.symbols[0] if self.symbols else symbol
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
        
        # 订阅任务
        self.subscription_tasks: List[asyncio.Task] = []
        
        # 决策循环任务
        self.decision_loop_task: Optional[asyncio.Task] = None
        
        # 配置参数
        self.max_position_size = self.config.get('max_position_size', 1000.0)
        self.risk_per_trade = self.config.get('risk_per_trade', 0.02)
        self.default_leverage = self.config.get('default_leverage', 1)
        self.decision_interval = self.config.get('decision_interval', 60)  # 决策间隔(秒)
        
        # 初始化对话
        self.llm_model.create_conversation(self.system_prompt)
        
        # K线数据管理（使用DataFrame）
        self.df = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
        self.df.set_index('timestamp', inplace=True)
        
        # 数据处理参数
        self.max_kline_history = self.config.get('max_kline_history', 500)
        self.last_kline_timestamp = None
        self.last_decision_time = 0  # 上次决策时间
        self.min_decision_interval = self.config.get('min_decision_interval', 120)  # 最小决策间隔(秒)
        self.lock = asyncio.Lock()
        
        logger.info(f"SmartTradingAgent {self.name} initialized for {self.symbol} (symbols={self.symbols}) @ {timeframe}")
    
    async def _on_initialize(self):
        """初始化 Agent"""
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
            logger.info(f"Loading historical klines for {self.symbol} @ {self.timeframe}")
            
            # 加载最近500根K线
            klines = await self.exchange.fetch_ohlcv(
                symbol=self.symbol,
                timeframe=self.timeframe,
                limit=self.max_kline_history
            )
            
            if klines:
                logger.info(f"Loaded {len(klines)} historical klines")
                
                # 构建DataFrame并计算指标
                await self._process_klines_batch(klines, is_history=True)
            else:
                logger.warning("No historical klines loaded")
                
        except Exception as e:
            logger.error(f"Error loading historical klines: {e}", exc_info=True)   


    # ========== 数据事件回调 ==========
    
    async def _on_kline_update(self, event: DataEvent):
        """K线更新回调 - 处理新K线和K线更新"""
        try:
            kline = event.data
            current_time = datetime.now().timestamp()
            
            async with self.lock:
                # 检查是否是新K线：比较时间戳
                is_new_candle = False
                if self.last_kline_timestamp is None or kline[0] > self.last_kline_timestamp:
                    is_new_candle = True
                    self.last_kline_timestamp = kline[0]
                
                # 处理K线数据
                await self._process_kline_update(kline, is_new_candle, current_time)
                
                logger.debug(f"Kline {'new' if is_new_candle else 'updated'}: O={kline[1]}, H={kline[2]}, L={kline[3]}, C={kline[4]}")
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
            # 1. 收集市场数据
            market_context = self._build_market_context()
            
            # 2. 收集持仓数据
            position_context = self._build_position_context()
            
            # 3. 收集账户数据
            account_context = await self._build_account_context()
            
            # 4. 构建 LLM 提示词
            prompt = self._build_llm_prompt(market_context, position_context, account_context)
            
            # 5. 获取工具定义
            tools = self.tool_registry.get_openai_tools()
            
            # 6. 调用 LLM (使用异步调用避免阻塞事件循环)
            logger.info(f"Calling LLM for decision...")
            response = await self.llm_model.chat_completion_async(
                user_message=prompt,
                tools=tools if tools else None,
            )
            
            # 7. 处理 LLM 响应
            await self._process_llm_response(response, market_context, position_context)
            
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
    
    def _build_market_context(self) -> MarketContext:
        """构建市场上下文"""
        # 计算技术指标
        indicators = self._calculate_indicators()
        
        # 获取当前价格
        current_price = 0.0
        if len(self.df) > 0:
            current_price = self.df['close'].iloc[-1]
        elif self.current_ticker:
            current_price = self.current_ticker.get('last', 0)
        
        # 获取最近50根K线数据
        klines = []
        if len(self.df) > 0:
            for idx, row in self.df.tail(50).iterrows():
                klines.append([
                    int(idx.timestamp() * 1000),
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    float(row['volume'])
                ])
        
        return MarketContext(
            symbol=self.symbol,
            timeframe=self.timeframe,
            current_price=current_price,
            klines=klines,
            indicators=indicators,
            ticker=self.current_ticker,
            orderbook=self.current_orderbook,
        )
    
    def _build_position_context(self) -> PositionContext:
        """构建持仓上下文"""
        total_value = 0.0
        total_pnl = 0.0
        
        # 只计算当前symbol的持仓
        symbol_positions = [p for p in self.current_positions if p.get('symbol') == self.symbol]
        
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
    
    def _get_settlement_currency(self) -> str:
        """获取结算币种"""
        # 从 symbol 中提取，例如 BTC/USDT:USDT -> USDT
        if ':' in self.symbol:
            return self.symbol.split(':')[1]
        elif '/' in self.symbol:
            return self.symbol.split('/')[1]
        return 'USDT'
    
    def _calculate_indicators(self) -> Dict[str, Any]:
        """获取最新指标值（从DataFrame中读取）"""
        indicators = {}
        
        if len(self.df) == 0:
            return indicators
        
        last_row = self.df.iloc[-1]
        
        # 收集所有可用的指标
        indicator_cols = ['RSI', 'EMA_20', 'EMA_50', 'SMA_20', 'SMA_50', 
                         'MACD', 'MACD_Signal', 'MACD_Histogram',
                         'BB_Upper', 'BB_Middle', 'BB_Lower',
                         'ATR', 'K', 'D', 'ADX', 'Volume', 'AvgVolume_20']
        
        for col in indicator_cols:
            if col in self.df.columns:
                val = last_row[col]
                if not pd.isna(val):
                    indicators[col] = float(val)
        
        return indicators
    
    
    async def _process_klines_batch(self, klines: List[List], is_history: bool = False):
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
                self.df = df_new.copy()
            else:
                self.df = pd.concat([self.df, df_new]).drop_duplicates()
            
            # 保持最多max_kline_history行
            if len(self.df) > self.max_kline_history:
                self.df = self.df.iloc[-self.max_kline_history:]
            
            # 计算所有指标
            await self._calculate_all_indicators()
            
            logger.debug(f"Processed {len(df_new)} klines, total in df: {len(self.df)}")
        except Exception as e:
            logger.error(f"Error processing klines batch: {e}", exc_info=True)
    
    async def _finalize_last_candle_indicators(self):
        """对前一条K线进行指标最终化
        
        当新K线到达时，使用完整的前一K线数据重新计算其指标
        确保每条K线有完整且准确的指标数据
        """
        try:
            if len(self.df) < 2:
                return
            
            # 只对前一条进行指标更新，使用完整的历史数据
            last_idx = self.df.index[-1]
            
            # 重新计算所有指标（基于完整历史数据）
            df = self.df.copy()
            
            # === 逐个指标更新前一行 ===
            # RSI
            if any(ind.lower() == 'rsi' for ind in self.indicators):
                rsi = ta.rsi(df['close'], length=14)
                if rsi is not None and len(rsi) >= 2:
                    self.df.loc[last_idx, 'RSI'] = rsi.iloc[-2]
            
            # EMA
            if any(ind.lower() == 'ema' for ind in self.indicators):
                ema20 = ta.ema(df['close'], length=20)
                ema50 = ta.ema(df['close'], length=50)
                if ema20 is not None and len(ema20) >= 2:
                    self.df.loc[last_idx, 'EMA_20'] = ema20.iloc[-2]
                if ema50 is not None and len(ema50) >= 2:
                    self.df.loc[last_idx, 'EMA_50'] = ema50.iloc[-2]
            
            # MACD
            if any(ind.lower() == 'macd' for ind in self.indicators):
                macd_result = ta.macd(df['close'])
                if macd_result is not None and len(macd_result.columns) >= 3 and len(macd_result) >= 2:
                    self.df.loc[last_idx, 'MACD'] = macd_result.iloc[-2, 0]
                    self.df.loc[last_idx, 'MACD_Signal'] = macd_result.iloc[-2, 1]
                    self.df.loc[last_idx, 'MACD_Histogram'] = macd_result.iloc[-2, 2]
            
            logger.debug(f"Finalized indicators for candle {last_idx}")
        except Exception as e:
            logger.debug(f"Error finalizing last candle indicators: {e}")
    
    async def _process_kline_update(self, kline: List, is_new_candle: bool, current_time: float):
        """处理单条K线更新（动态更新）
        
        分两种情况处理：
        1. 新K线（新的时间）：保存前一K线指标，添加新K线，触发决策
        2. K线更新（同一时间更新）：更新当前K线，定时触发决策
        """
        try:
            ts = pd.Timestamp(kline[0], unit="ms")
            trigger_decision = False
            
            if is_new_candle and len(self.df) > 0:
                # ===== 新K线情况 =====
                # 1. 对前一条K线进行最终指标计算
                await self._finalize_last_candle_indicators()
                
                # 2. 添加新K线
                new_row = pd.Series({
                    'open': kline[1],
                    'high': kline[2],
                    'low': kline[3],
                    'close': kline[4],
                    'volume': kline[5],
                }, index=['open', 'high', 'low', 'close', 'volume'])
                
                self.df.loc[ts] = new_row
                
                # 3. 计算新K线的指标
                await self._calculate_all_indicators()
                
                # 4. 标记应该触发决策
                self.last_decision_time = current_time
                trigger_decision = True
                
                logger.info(f"New candle at {ts}, triggering decision")
                
            else:
                # ===== K线更新情况 =====
                # 当前K线还在形成中，仅更新数据
                if ts not in self.df.index:
                    new_row = pd.Series({
                        'open': kline[1],
                        'high': kline[2],
                        'low': kline[3],
                        'close': kline[4],
                        'volume': kline[5],
                    }, index=['open', 'high', 'low', 'close', 'volume'])
                    self.df.loc[ts] = new_row
                else:
                    # 更新现有行
                    self.df.loc[ts, 'open'] = kline[1]
                    self.df.loc[ts, 'high'] = kline[2]
                    self.df.loc[ts, 'low'] = kline[3]
                    self.df.loc[ts, 'close'] = kline[4]
                    self.df.loc[ts, 'volume'] = kline[5]
                
                # 计算最新指标（仅更新最后一行，提高性能）
                await self._calculate_all_indicators()
                
                # 定时触发决策（每5秒检查一次）
                if current_time - self.last_decision_time >= self.min_decision_interval:
                    self.last_decision_time = current_time
                    trigger_decision = True
                    logger.debug(f"Time-based decision trigger at {ts}")
            
            # 保持历史数据容量
            if len(self.df) > self.max_kline_history:
                self.df = self.df.iloc[-self.max_kline_history:]
            
            # 触发决策（如果条件满足）
            if trigger_decision:
                # 在后台执行，不阻塞数据更新
                asyncio.create_task(self._make_decision())
                
        except Exception as e:
            logger.error(f"Error processing kline update: {e}", exc_info=True)
    
    async def _calculate_all_indicators(self):
        """计算所有技术指标"""
        try:
            if len(self.df) < 20:
                return
            
            df = self.df.copy()
            
            # === 基础指标 ===
            # RSI
            if any(ind.lower() == 'rsi' for ind in self.indicators):
                rsi = ta.rsi(df['close'], length=14)
                if rsi is not None and len(rsi) > 0:
                    self.df['RSI'] = rsi
            
            # EMA
            if any(ind.lower() == 'ema' for ind in self.indicators):
                ema20 = ta.ema(df['close'], length=20)
                ema50 = ta.ema(df['close'], length=50)
                if ema20 is not None:
                    self.df['EMA_20'] = ema20
                if ema50 is not None:
                    self.df['EMA_50'] = ema50
            
            # SMA
            if any(ind.lower() == 'sma' for ind in self.indicators):
                sma20 = ta.sma(df['close'], length=20)
                sma50 = ta.sma(df['close'], length=50)
                if sma20 is not None:
                    self.df['SMA_20'] = sma20
                if sma50 is not None:
                    self.df['SMA_50'] = sma50
            
            # MACD
            if any(ind.lower() == 'macd' for ind in self.indicators):
                macd_result = ta.macd(df['close'])
                if macd_result is not None and len(macd_result.columns) >= 3:
                    self.df['MACD'] = macd_result.iloc[:, 0]
                    self.df['MACD_Signal'] = macd_result.iloc[:, 1]
                    self.df['MACD_Histogram'] = macd_result.iloc[:, 2]
            
            # Bollinger Bands
            if any(ind.lower() == 'bb' for ind in self.indicators):
                bb_result = ta.bbands(df['close'], length=20, std=2)
                if bb_result is not None and len(bb_result.columns) >= 3:
                    self.df['BB_Upper'] = bb_result.iloc[:, 0]
                    self.df['BB_Middle'] = bb_result.iloc[:, 1]
                    self.df['BB_Lower'] = bb_result.iloc[:, 2]
            
            # ATR
            if any(ind.lower() == 'atr' for ind in self.indicators):
                atr = ta.atr(df['high'], df['low'], df['close'], length=14)
                if atr is not None:
                    self.df['ATR'] = atr
            
            # KDJ / Stochastic
            if any(ind.lower() in ['kdj', 'stoch'] for ind in self.indicators):
                stoch_result = ta.stoch(df['high'], df['low'], df['close'], k=14, d=3)
                if stoch_result is not None and len(stoch_result.columns) >= 2:
                    self.df['K'] = stoch_result.iloc[:, 0]
                    self.df['D'] = stoch_result.iloc[:, 1]
            
            # ADX
            if any(ind.lower() == 'adx' for ind in self.indicators):
                try:
                    adx_result = ta.adx(df['high'], df['low'], df['close'], length=14)
                    adx_col = next((c for c in adx_result.columns if 'ADX' in c.upper()), None)
                    if adx_col:
                        self.df['ADX'] = adx_result[adx_col]
                except Exception:
                    pass
            
            # 成交量指标
            self.df['Volume'] = df['volume']
            self.df['AvgVolume_20'] = df['volume'].rolling(window=20).mean()
            
            logger.debug(f"Indicators calculated for {len(self.df)} rows")
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}", exc_info=True)
    
    def _build_llm_prompt(
        self,
        market: MarketContext,
        position: PositionContext,
        account: AccountContext
    ) -> str:
        """构建LLM提示词"""
        prompt = f"""
{get_prompt_template()}

{market.to_llm_prompt()}

{position.to_llm_prompt()}

{account.to_llm_prompt()}

配置参数:
- 最大持仓规模: {self.max_position_size}
- 单笔风险比例: {self.risk_per_trade * 100}%
- 默认杠杆: {self.default_leverage}x

请分析当前市场状况，并决定下一步操作。你可以：
1. 开多仓 (LONG) - 看涨时建立多头仓位
2. 开空仓 (SHORT) - 看跌时建立空头仓位
3. 平仓 (CLOSE) - 关闭当前持仓
4. 设置条件止盈 (TAKE_PROFIT) - 价格达到目标时自动平仓
5. 设置条件止损 (STOP_LOSS) - 价格跌破止损位时自动平仓
6. 持有 (HOLD) - 保持当前状态，不做操作

如果需要执行交易，请使用相应的工具函数。
请给出你的分析和建议。
"""
        return prompt
    
    async def _process_llm_response(
        self,
        response: Dict[str, Any],
        market: MarketContext,
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
                
                # 记录工具调用
                self.record_tool_call(
                    tool_name=tool_name,
                    arguments=arguments,
                    result=result.get('result'),
                    error=result.get('error'),
                    duration_ms=result.get('execution_time', 0) * 1000
                )
            
            # 处理工具执行结果
            for result in results:
                if result['status'] == 'success':
                    logger.info(f"Tool {result['tool_name']} executed successfully")
                else:
                    logger.error(f"Tool {result['tool_name']} failed: {result.get('error')}")
        else:
            logger.info("No tool calls in LLM response")
    
    def get_agent_info(self) -> Dict[str, Any]:
        """获取Agent信息"""
        return {
            **self.get_stats(),
            'exchange': self.exchange.exchange_id,
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'indicators': self.indicators,
            'current_price': self.current_ticker.get('last') if self.current_ticker else None,
            'positions': self.current_positions,
            'klines_count': len(self.df),
        }
