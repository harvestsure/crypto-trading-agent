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

from agents.base_agent import BaseAgent, AgentStatus
from models.llm_model import LLMModel
from tools.tool_registry import ToolRegistry
from exchanges.common_exchange import CommonExchange
from common.data_types import DataEventType, DataEvent

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
        timeframe: str,
        indicators: List[str],
        llm_model: LLMModel,
        tool_registry: ToolRegistry,
        system_prompt: str,
        config: Dict[str, Any] = None,
    ):
        super().__init__(agent_id, name)
        
        self.exchange = exchange
        self.symbol = symbol
        self.timeframe = timeframe
        self.indicators = indicators
        self.llm_model = llm_model
        self.tool_registry = tool_registry
        self.system_prompt = system_prompt
        self.config = config or {}
        
        # 数据缓存
        self.klines_history: List[List] = []
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
        
        logger.info(f"SmartTradingAgent {self.name} initialized for {symbol} @ {timeframe}")
    
    async def _on_initialize(self):
        """初始化 Agent"""
        # 1. 加载历史K线
        await self._load_historical_klines()
        
        # 2. 订阅实时数据
        await self._subscribe_market_data()
        
        # 3. 启动决策循环
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
        
        # 取消所有订阅
        await self._unsubscribe_market_data()
        
        logger.info(f"Agent {self.name} cleaned up")
    
    async def _load_historical_klines(self):
        """加载历史K线数据"""
        try:
            logger.info(f"Loading historical klines for {self.symbol} @ {self.timeframe}")
            
            # 加载最近200根K线
            klines = await self.exchange.fetch_ohlcv(
                symbol=self.symbol,
                timeframe=self.timeframe,
                limit=200
            )
            
            if klines:
                self.klines_history = klines
                logger.info(f"Loaded {len(klines)} historical klines")
            else:
                logger.warning("No historical klines loaded")
                
        except Exception as e:
            logger.error(f"Error loading historical klines: {e}", exc_info=True)
    
    async def _subscribe_market_data(self):
        """订阅实时市场数据"""
        try:
            logger.info(f"Subscribing to market data for {self.symbol}")
            
            # 订阅K线
            await self.exchange.subscribe_data(DataEventType.OHLCV, [self.symbol])
            
            # 订阅Ticker
            await self.exchange.subscribe_data(DataEventType.TICKER, [self.symbol])
            
            # 订阅订单簿
            await self.exchange.subscribe_data(DataEventType.ORDERBOOK, [self.symbol])
            
            # 订阅成交数据
            await self.exchange.subscribe_data(DataEventType.TRADE, [self.symbol])
            
            # 注册数据事件回调
            self.exchange.event_bus.subscribe(
                DataEventType.OHLCV,
                self.symbol,
                self._on_kline_update
            )
            self.exchange.event_bus.subscribe(
                DataEventType.TICKER,
                self.symbol,
                self._on_ticker_update
            )
            self.exchange.event_bus.subscribe(
                DataEventType.ORDERBOOK,
                self.symbol,
                self._on_orderbook_update
            )
            
            # 订阅账户数据 (持仓、订单、余额)
            self.exchange.event_bus.subscribe(
                DataEventType.POSITION,
                self.symbol,
                self._on_position_update
            )
            self.exchange.event_bus.subscribe(
                DataEventType.ORDER,
                self.symbol,
                self._on_order_update
            )
            
            logger.info(f"Successfully subscribed to market data for {self.symbol}")
            
        except Exception as e:
            logger.error(f"Error subscribing to market data: {e}", exc_info=True)
    
    async def _unsubscribe_market_data(self):
        """取消订阅市场数据"""
        try:
            await self.exchange.unsubscribe_data(DataEventType.OHLCV, [self.symbol])
            await self.exchange.unsubscribe_data(DataEventType.TICKER, [self.symbol])
            await self.exchange.unsubscribe_data(DataEventType.ORDERBOOK, [self.symbol])
            await self.exchange.unsubscribe_data(DataEventType.TRADE, [self.symbol])
            
            logger.info(f"Unsubscribed from market data for {self.symbol}")
        except Exception as e:
            logger.error(f"Error unsubscribing from market data: {e}", exc_info=True)
    
    # ========== 数据事件回调 ==========
    
    async def _on_kline_update(self, event: DataEvent):
        """K线更新回调"""
        try:
            kline = event.data
            # 更新K线历史
            if self.klines_history:
                # 检查是否是新K线
                last_kline = self.klines_history[-1]
                if kline[0] > last_kline[0]:  # 新K线
                    self.klines_history.append(kline)
                    # 保持最多200根K线
                    if len(self.klines_history) > 200:
                        self.klines_history.pop(0)
                else:  # 更新当前K线
                    self.klines_history[-1] = kline
            else:
                self.klines_history = [kline]
                
            logger.debug(f"Kline updated: {kline}")
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
            
            # 6. 调用 LLM
            logger.info(f"Calling LLM for decision...")
            response = self.llm_model.chat_completion(
                user_message=prompt,
                tools=tools if tools else None,
            )
            
            # 7. 处理 LLM 响应
            await self._process_llm_response(response, market_context, position_context)
            
            self.set_status(AgentStatus.IDLE)
            
        except Exception as e:
            logger.error(f"Error making decision: {e}", exc_info=True)
            raise
    
    def _build_market_context(self) -> MarketContext:
        """构建市场上下文"""
        # 计算技术指标
        indicators = self._calculate_indicators()
        
        # 获取当前价格
        current_price = 0.0
        if self.current_ticker:
            current_price = self.current_ticker.get('last', 0)
        elif self.klines_history:
            current_price = self.klines_history[-1][4]  # 收盘价
        
        return MarketContext(
            symbol=self.symbol,
            timeframe=self.timeframe,
            current_price=current_price,
            klines=self.klines_history[-50:],  # 最近50根K线
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
            balance = await self.exchange.ccxt_exchange.fetch_balance()
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
        """计算技术指标"""
        indicators = {}
        
        if not self.klines_history or len(self.klines_history) < 20:
            return indicators
        
        closes = [k[4] for k in self.klines_history]
        highs = [k[2] for k in self.klines_history]
        lows = [k[3] for k in self.klines_history]
        volumes = [k[5] for k in self.klines_history]
        
        # RSI
        if 'rsi' in self.indicators or 'RSI' in self.indicators:
            indicators['RSI'] = self._calculate_rsi(closes)
        
        # EMA
        if 'ema' in self.indicators or 'EMA' in self.indicators:
            indicators['EMA_20'] = self._calculate_ema(closes, 20)
            indicators['EMA_50'] = self._calculate_ema(closes, 50)
        
        # MACD
        if 'macd' in self.indicators or 'MACD' in self.indicators:
            macd_data = self._calculate_macd(closes)
            indicators.update(macd_data)
        
        # Bollinger Bands
        if 'bb' in self.indicators or 'BB' in self.indicators:
            bb_data = self._calculate_bollinger_bands(closes)
            indicators.update(bb_data)
        
        # ATR
        if 'atr' in self.indicators or 'ATR' in self.indicators:
            indicators['ATR'] = self._calculate_atr(highs, lows, closes)
        
        # 成交量
        indicators['Volume'] = volumes[-1] if volumes else 0
        indicators['AvgVolume_20'] = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else 0
        
        return indicators
    
    @staticmethod
    def _calculate_rsi(closes: List[float], period: int = 14) -> float:
        """计算RSI"""
        if len(closes) < period + 1:
            return 50.0
        
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def _calculate_ema(data: List[float], period: int) -> float:
        """计算EMA"""
        if len(data) < period:
            return data[-1] if data else 0
        
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    @staticmethod
    def _calculate_macd(closes: List[float]) -> Dict[str, float]:
        """计算MACD"""
        if len(closes) < 26:
            return {'MACD': 0, 'MACD_Signal': 0, 'MACD_Histogram': 0}
        
        ema12 = SmartTradingAgent._calculate_ema(closes, 12)
        ema26 = SmartTradingAgent._calculate_ema(closes, 26)
        macd = ema12 - ema26
        
        # 简化：使用最近9个MACD值计算信号线
        signal = macd * 0.8  # 简化处理
        histogram = macd - signal
        
        return {
            'MACD': macd,
            'MACD_Signal': signal,
            'MACD_Histogram': histogram
        }
    
    @staticmethod
    def _calculate_bollinger_bands(closes: List[float], period: int = 20, std_dev: int = 2) -> Dict[str, float]:
        """计算布林带"""
        if len(closes) < period:
            return {'BB_Upper': 0, 'BB_Middle': 0, 'BB_Lower': 0}
        
        recent = closes[-period:]
        middle = sum(recent) / period
        
        variance = sum((x - middle) ** 2 for x in recent) / period
        std = variance ** 0.5
        
        return {
            'BB_Upper': middle + (std_dev * std),
            'BB_Middle': middle,
            'BB_Lower': middle - (std_dev * std)
        }
    
    @staticmethod
    def _calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """计算ATR"""
        if len(closes) < period + 1:
            return 0.0
        
        tr_list = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            tr_list.append(tr)
        
        if len(tr_list) < period:
            return 0.0
        
        return sum(tr_list[-period:]) / period
    
    def _build_llm_prompt(
        self,
        market: MarketContext,
        position: PositionContext,
        account: AccountContext
    ) -> str:
        """构建LLM提示词"""
        prompt = f"""
你是一个专业的加密货币交易助手。请根据以下信息分析市场并给出交易建议。

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
            'klines_count': len(self.klines_history),
        }
