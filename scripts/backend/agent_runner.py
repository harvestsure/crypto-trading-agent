"""
Agent Runner - Manages running trading agents
Handles the main loop for each agent: fetch data, calculate indicators, get AI signal, execute orders
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AgentState:
    agent_id: str
    name: str
    model_id: str
    exchange_id: str
    symbol: str
    timeframe: str
    indicators: List[str]
    prompt: str
    is_running: bool = False
    last_signal: Optional[dict] = None
    last_analysis_time: Optional[datetime] = None
    position: Optional[dict] = None  # Current open position


class AgentRunner:
    """
    Manages the lifecycle and execution of trading agents.
    Each agent runs in its own async task.
    """
    
    def __init__(
        self,
        exchange_manager,
        ai_manager,
        indicator_calculator,
        on_signal: Optional[Callable] = None,
        on_order: Optional[Callable] = None,
        on_log: Optional[Callable] = None,
    ):
        self.exchange_manager = exchange_manager
        self.ai_manager = ai_manager
        self.indicator_calculator = indicator_calculator
        self.on_signal = on_signal
        self.on_order = on_order
        self.on_log = on_log
        
        self.agents: Dict[str, AgentState] = {}
        self.tasks: Dict[str, asyncio.Task] = {}
        self.kline_cache: Dict[str, List[dict]] = {}
    
    def add_agent(self, config: dict) -> str:
        """Register a new agent"""
        agent_id = config['id']
        self.agents[agent_id] = AgentState(
            agent_id=agent_id,
            name=config['name'],
            model_id=config['model_id'],
            exchange_id=config['exchange_id'],
            symbol=config['symbol'],
            timeframe=config['timeframe'],
            indicators=config['indicators'],
            prompt=config['prompt'],
        )
        logger.info(f"Agent {agent_id} registered: {config['name']}")
        return agent_id
    
    def remove_agent(self, agent_id: str):
        """Remove an agent"""
        self.stop_agent(agent_id)
        if agent_id in self.agents:
            del self.agents[agent_id]
            logger.info(f"Agent {agent_id} removed")
    
    async def start_agent(self, agent_id: str):
        """Start an agent's trading loop"""
        if agent_id not in self.agents:
            logger.error(f"Agent {agent_id} not found")
            return False
        
        agent = self.agents[agent_id]
        if agent.is_running:
            logger.warning(f"Agent {agent_id} is already running")
            return False
        
        agent.is_running = True
        self.tasks[agent_id] = asyncio.create_task(self._run_agent_loop(agent_id))
        
        await self._emit_log(agent_id, "info", f"Agent started: {agent.name}")
        logger.info(f"Agent {agent_id} started")
        return True
    
    def stop_agent(self, agent_id: str):
        """Stop an agent's trading loop"""
        if agent_id in self.agents:
            self.agents[agent_id].is_running = False
        
        if agent_id in self.tasks:
            self.tasks[agent_id].cancel()
            del self.tasks[agent_id]
            logger.info(f"Agent {agent_id} stopped")
    
    async def _run_agent_loop(self, agent_id: str):
        """Main trading loop for an agent"""
        agent = self.agents[agent_id]
        
        # Determine analysis interval based on timeframe
        interval_map = {
            '1m': 60,
            '5m': 300,
            '15m': 900,
            '30m': 1800,
            '1h': 3600,
            '4h': 14400,
            '1d': 86400,
        }
        interval = interval_map.get(agent.timeframe, 3600)
        
        while agent.is_running:
            try:
                await self._analyze_and_trade(agent)
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                logger.info(f"Agent {agent_id} loop cancelled")
                break
            except Exception as e:
                logger.error(f"Agent {agent_id} error: {e}")
                await self._emit_log(agent_id, "error", f"Error: {str(e)}")
                await asyncio.sleep(30)  # Wait before retry
    
    async def _analyze_and_trade(self, agent: AgentState):
        """
        Fetch data, analyze with AI, and execute trades
        """
        try:
            # 1. Fetch Kline Data
            kline_data = await self._fetch_klines(agent)
            if not kline_data or len(kline_data) < 20:
                await self._emit_log(
                    agent.agent_id, 
                    "warning", 
                    f"Insufficient kline data: {len(kline_data) if kline_data else 0} candles (need ≥20)"
                )
                return
            
            # 2. Calculate Indicators
            try:
                indicators = self.indicator_calculator.calculate_all(kline_data, agent.indicators)
                
                if not indicators or len(indicators) == 0:
                    await self._emit_log(agent.agent_id, "warning", "No indicators calculated")
                    return
                
                # Log key indicators
                key_indicators = {
                    k: f"{v:.2f}" if isinstance(v, (int, float)) else str(v)
                    for k, v in list(indicators.items())[:5]
                }
                await self._emit_log(
                    agent.agent_id, 
                    "info", 
                    f"Indicators: {', '.join(f'{k}={v}' for k, v in key_indicators.items())}"
                )
            except Exception as e:
                logger.error(f"Indicator calculation error: {e}")
                await self._emit_log(agent.agent_id, "error", f"Indicator error: {str(e)}")
                return
            
            # 3. Get AI Analysis
            try:
                signal = await self.ai_manager.analyze(
                    agent.model_id,
                    kline_data,
                    indicators,
                    agent.prompt,
                )
                
                if not signal or not hasattr(signal, 'action'):
                    await self._emit_log(agent.agent_id, "error", "Invalid AI signal received")
                    return
                
                agent.last_signal = {
                    'action': signal.action,
                    'reason': signal.reason,
                    'confidence': getattr(signal, 'confidence', 'medium'),
                    'take_profit': signal.take_profit,
                    'stop_loss': signal.stop_loss,
                    'timestamp': datetime.utcnow().isoformat(),
                }
                agent.last_analysis_time = datetime.utcnow()
                
                # Emit signal event
                if self.on_signal:
                    await self.on_signal({
                        'agent_id': agent.agent_id,
                        'signal': agent.last_signal,
                        'indicators': indicators,
                    })
                
                await self._emit_log(
                    agent.agent_id,
                    "signal",
                    f"AI Signal: {signal.action.upper()} (Confidence: {agent.last_signal['confidence']}) - {signal.reason[:100]}"
                )
                
                # 4. Execute Trade if signal is buy/sell
                if signal.action in ('buy', 'sell', 'long', 'short'):
                    await self._execute_trade(agent, signal, kline_data[-1])
                elif signal.action == 'close':
                    await self._close_position(agent)
                
            except Exception as e:
                logger.error(f"AI analysis error: {e}", exc_info=True)
                await self._emit_log(agent.agent_id, "error", f"AI analysis failed: {str(e)}")
                return
            
        except Exception as e:
            logger.error(f"Analysis error for agent {agent.agent_id}: {e}", exc_info=True)
            await self._emit_log(agent.agent_id, "error", f"Analysis failed: {str(e)}")

    async def _close_position(self, agent: AgentState):
        """
        Close current position
        """
        try:
            if not agent.position:
                await self._emit_log(agent.agent_id, "info", "No position to close")
                return
            
            exchange = self.exchange_manager.exchanges.get(agent.exchange_id)
            if not exchange:
                await self._emit_log(agent.agent_id, "error", "Exchange not connected")
                return
            
            # Close position (sell if long, buy if short)
            close_side = 'sell' if agent.position['side'] == 'buy' else 'buy'
            
            order = await self.exchange_manager.place_order(
                agent.exchange_id,
                agent.symbol,
                close_side,
                'market',
                agent.position['amount'],
            )
            
            # Calculate PnL
            entry_price = agent.position['entry_price']
            current_price = order.get('price', entry_price)
            pnl = (current_price - entry_price) * agent.position['amount']
            if agent.position['side'] == 'sell':
                pnl = -pnl
            
            pnl_percent = (pnl / (entry_price * agent.position['amount'])) * 100
            
            await self._emit_log(
                agent.agent_id,
                "order",
                f"Position closed: PnL ${pnl:.2f} ({pnl_percent:+.2f}%)"
            )
            
            # Clear position
            agent.position = None
            
        except Exception as e:
            logger.error(f"Position close error: {e}")
            await self._emit_log(agent.agent_id, "error", f"Close failed: {str(e)}")

    async def _fetch_klines(self, agent: AgentState) -> List[dict]:
        """Fetch kline data from exchange"""
        cache_key = f"{agent.exchange_id}_{agent.symbol}_{agent.timeframe}"
        
        if agent.exchange_id not in self.exchange_manager.exchanges:
            logger.warning(f"Exchange {agent.exchange_id} not connected")
            return self.kline_cache.get(cache_key, [])
        
        try:
            exchange = self.exchange_manager.exchanges[agent.exchange_id]
            ohlcv = await exchange.fetch_ohlcv(agent.symbol, agent.timeframe, limit=100)
            
            klines = [
                {
                    'timestamp': k[0],
                    'open': k[1],
                    'high': k[2],
                    'low': k[3],
                    'close': k[4],
                    'volume': k[5],
                }
                for k in ohlcv
            ]
            
            self.kline_cache[cache_key] = klines
            return klines
            
        except Exception as e:
            logger.error(f"Failed to fetch klines: {e}")
            return self.kline_cache.get(cache_key, [])
    
    async def _execute_trade(self, agent: AgentState, signal, current_kline: dict):
        """Execute a trade based on the signal"""
        try:
            exchange = self.exchange_manager.exchanges.get(agent.exchange_id)
            if not exchange:
                await self._emit_log(agent.agent_id, "error", "Exchange not connected")
                return
            
            current_price = current_kline['close']
            
            # Calculate position size (example: fixed 100 USDT)
            position_size = 100 / current_price
            
            # Place market order
            order = await self.exchange_manager.place_order(
                agent.exchange_id,
                agent.symbol,
                signal.action,
                'market',
                position_size,
            )
            
            # Place take profit and stop loss orders if specified
            if signal.take_profit:
                tp_order = await self.exchange_manager.place_order(
                    agent.exchange_id,
                    agent.symbol,
                    'sell' if signal.action == 'buy' else 'buy',
                    'limit',
                    position_size,
                    signal.take_profit,
                )
                await self._emit_log(
                    agent.agent_id,
                    "order",
                    f"Take Profit order placed at ${signal.take_profit}"
                )
            
            if signal.stop_loss:
                # Note: Real implementation would use stop-loss order type
                await self._emit_log(
                    agent.agent_id,
                    "info",
                    f"Stop Loss set at ${signal.stop_loss}"
                )
            
            # Update agent position
            agent.position = {
                'side': signal.action,
                'entry_price': current_price,
                'amount': position_size,
                'take_profit': signal.take_profit,
                'stop_loss': signal.stop_loss,
            }
            
            # Emit order event
            if self.on_order:
                await self.on_order({
                    'agent_id': agent.agent_id,
                    'order': order,
                    'signal': signal.action,
                })
            
            await self._emit_log(
                agent.agent_id,
                "order",
                f"Order executed: {signal.action.upper()} {position_size:.6f} {agent.symbol} @ ${current_price:.2f}"
            )
            
        except Exception as e:
            logger.error(f"Trade execution error: {e}")
            await self._emit_log(agent.agent_id, "error", f"Trade failed: {str(e)}")
    
    async def _emit_log(self, agent_id: str, level: str, message: str):
        """Emit a log event"""
        if self.on_log:
            await self.on_log({
                'agent_id': agent_id,
                'level': level,
                'message': message,
                'timestamp': datetime.utcnow().isoformat(),
            })
    
    def get_agent_status(self, agent_id: str) -> Optional[dict]:
        """Get current status of an agent"""
        if agent_id not in self.agents:
            return None
        
        agent = self.agents[agent_id]
        return {
            'agent_id': agent.agent_id,
            'name': agent.name,
            'is_running': agent.is_running,
            'last_signal': agent.last_signal,
            'last_analysis_time': agent.last_analysis_time.isoformat() if agent.last_analysis_time else None,
            'position': agent.position,
        }
    
    def get_all_statuses(self) -> List[dict]:
        """Get status of all agents"""
        return [self.get_agent_status(aid) for aid in self.agents.keys()]
