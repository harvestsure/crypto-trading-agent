"""
Trading Agent with OpenAI Agents SDK
Implements tool-based AI agent for cryptocurrency trading

This module uses OpenAI's official Agents SDK to create a trading agent
that can execute trades, set stop-loss/take-profit, manage positions, etc.
"""

import json
import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

# OpenAI Agents SDK imports
from agents import Agent, Runner, function_tool, FunctionTool, RunContextWrapper

logger = logging.getLogger(__name__)


# ============== Tool Output Models ==============

class OrderResult(BaseModel):
    success: bool
    order_id: Optional[str] = None
    symbol: str
    side: str
    amount: float
    price: Optional[float] = None
    error: Optional[str] = None


class PositionInfo(BaseModel):
    symbol: str
    side: str  # long, short, none
    size: float
    entry_price: float
    unrealized_pnl: float
    leverage: int


class MarketData(BaseModel):
    symbol: str
    last_price: float
    bid: float
    ask: float
    volume_24h: float
    change_24h: float


# ============== Trading Context ==============

class TradingContext(BaseModel):
    """Context passed to the agent with exchange and config info"""
    exchange_id: str
    symbol: str
    timeframe: str
    max_position_size: float = 1000.0  # USD
    default_leverage: int = 1
    risk_per_trade: float = 0.02  # 2% risk per trade


# ============== Trading Tools ==============

class TradingTools:
    """
    Trading tools for the AI agent to use.
    These are the actions the agent can take to interact with the exchange.
    """
    
    def __init__(self, exchange_manager, connection_manager):
        self.exchange_manager = exchange_manager
        self.connection_manager = connection_manager
        self._positions: Dict[str, Dict] = {}  # symbol -> position
        self._orders: Dict[str, Dict] = {}  # order_id -> order
    
    def create_tools(self) -> List[FunctionTool]:
        """Create all trading tools for the agent"""
        
        exchange_manager = self.exchange_manager
        connection_manager = self.connection_manager
        positions = self._positions
        orders = self._orders
        
        @function_tool
        async def place_market_order(
            ctx: RunContextWrapper[TradingContext],
            side: str,
            amount_usd: float,
            reason: str
        ) -> str:
            """
            Place a market order on the exchange.
            
            Args:
                side: Order side, must be 'buy' or 'sell'
                amount_usd: Position size in USD
                reason: Brief explanation for this trade decision
            """
            context = ctx.context
            
            if side not in ('buy', 'sell'):
                return json.dumps({"success": False, "error": "Invalid side. Must be 'buy' or 'sell'"})
            
            if amount_usd > context.max_position_size:
                return json.dumps({"success": False, "error": f"Amount exceeds max position size of ${context.max_position_size}"})
            
            try:
                # Get current price
                ticker = await exchange_manager.get_ticker(context.exchange_id, context.symbol)
                current_price = ticker.get('last', 0)
                
                if current_price <= 0:
                    return json.dumps({"success": False, "error": "Unable to get current price"})
                
                # Calculate amount in base currency
                amount = amount_usd / current_price
                
                # Place order
                order = await exchange_manager.place_order(
                    context.exchange_id,
                    context.symbol,
                    side,
                    'market',
                    amount
                )
                
                order_id = order.get('id', f"order_{datetime.utcnow().timestamp()}")
                
                # Track position
                if context.symbol not in positions:
                    positions[context.symbol] = {'side': 'none', 'size': 0, 'entry_price': 0}
                
                pos = positions[context.symbol]
                if side == 'buy':
                    if pos['side'] == 'short':
                        pos['size'] -= amount
                        if pos['size'] <= 0:
                            pos['side'] = 'long' if pos['size'] < 0 else 'none'
                            pos['size'] = abs(pos['size'])
                            pos['entry_price'] = current_price
                    else:
                        pos['side'] = 'long'
                        pos['size'] += amount
                        pos['entry_price'] = current_price
                else:  # sell
                    if pos['side'] == 'long':
                        pos['size'] -= amount
                        if pos['size'] <= 0:
                            pos['side'] = 'short' if pos['size'] < 0 else 'none'
                            pos['size'] = abs(pos['size'])
                            pos['entry_price'] = current_price
                    else:
                        pos['side'] = 'short'
                        pos['size'] += amount
                        pos['entry_price'] = current_price
                
                # Store order
                orders[order_id] = {
                    'id': order_id,
                    'symbol': context.symbol,
                    'side': side,
                    'type': 'market',
                    'amount': amount,
                    'price': current_price,
                    'status': 'filled',
                    'reason': reason,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                # Broadcast to clients
                await connection_manager.broadcast({
                    'type': 'order',
                    'order': orders[order_id]
                })
                
                return json.dumps({
                    "success": True,
                    "order_id": order_id,
                    "symbol": context.symbol,
                    "side": side,
                    "amount": amount,
                    "price": current_price,
                    "amount_usd": amount_usd,
                    "reason": reason
                })
                
            except Exception as e:
                logger.error(f"Market order error: {e}")
                return json.dumps({"success": False, "error": str(e)})
        
        @function_tool
        async def place_limit_order(
            ctx: RunContextWrapper[TradingContext],
            side: str,
            amount_usd: float,
            price: float,
            reason: str
        ) -> str:
            """
            Place a limit order on the exchange.
            
            Args:
                side: Order side, must be 'buy' or 'sell'
                amount_usd: Position size in USD
                price: Limit price for the order
                reason: Brief explanation for this order
            """
            context = ctx.context
            
            if side not in ('buy', 'sell'):
                return json.dumps({"success": False, "error": "Invalid side"})
            
            try:
                amount = amount_usd / price
                
                order = await exchange_manager.place_order(
                    context.exchange_id,
                    context.symbol,
                    side,
                    'limit',
                    amount,
                    price
                )
                
                order_id = order.get('id', f"limit_{datetime.utcnow().timestamp()}")
                
                orders[order_id] = {
                    'id': order_id,
                    'symbol': context.symbol,
                    'side': side,
                    'type': 'limit',
                    'amount': amount,
                    'price': price,
                    'status': 'open',
                    'reason': reason,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                await connection_manager.broadcast({
                    'type': 'order',
                    'order': orders[order_id]
                })
                
                return json.dumps({
                    "success": True,
                    "order_id": order_id,
                    "symbol": context.symbol,
                    "side": side,
                    "amount": amount,
                    "price": price,
                    "status": "open"
                })
                
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)})
        
        @function_tool
        async def set_stop_loss(
            ctx: RunContextWrapper[TradingContext],
            stop_price: float,
            reason: str
        ) -> str:
            """
            Set a stop-loss order to limit losses on the current position.
            
            Args:
                stop_price: Price at which to trigger the stop-loss
                reason: Brief explanation for this stop-loss level
            """
            context = ctx.context
            
            if context.symbol not in positions or positions[context.symbol]['side'] == 'none':
                return json.dumps({"success": False, "error": "No open position to set stop-loss"})
            
            pos = positions[context.symbol]
            
            try:
                # Determine stop-loss side (opposite of position)
                sl_side = 'sell' if pos['side'] == 'long' else 'buy'
                
                order = await exchange_manager.place_stop_order(
                    context.exchange_id,
                    context.symbol,
                    sl_side,
                    pos['size'],
                    stop_price
                )
                
                order_id = order.get('id', f"sl_{datetime.utcnow().timestamp()}")
                
                orders[order_id] = {
                    'id': order_id,
                    'symbol': context.symbol,
                    'side': sl_side,
                    'type': 'stop_loss',
                    'amount': pos['size'],
                    'stop_price': stop_price,
                    'status': 'open',
                    'reason': reason,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                await connection_manager.broadcast({
                    'type': 'stop_loss_set',
                    'order': orders[order_id]
                })
                
                return json.dumps({
                    "success": True,
                    "order_id": order_id,
                    "type": "stop_loss",
                    "stop_price": stop_price,
                    "position_side": pos['side'],
                    "position_size": pos['size']
                })
                
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)})
        
        @function_tool
        async def set_take_profit(
            ctx: RunContextWrapper[TradingContext],
            target_price: float,
            reason: str
        ) -> str:
            """
            Set a take-profit order to lock in gains on the current position.
            
            Args:
                target_price: Price at which to take profit
                reason: Brief explanation for this take-profit level
            """
            context = ctx.context
            
            if context.symbol not in positions or positions[context.symbol]['side'] == 'none':
                return json.dumps({"success": False, "error": "No open position to set take-profit"})
            
            pos = positions[context.symbol]
            
            try:
                # Determine take-profit side (opposite of position)
                tp_side = 'sell' if pos['side'] == 'long' else 'buy'
                
                order = await exchange_manager.place_limit_order(
                    context.exchange_id,
                    context.symbol,
                    tp_side,
                    pos['size'],
                    target_price
                )
                
                order_id = order.get('id', f"tp_{datetime.utcnow().timestamp()}")
                
                orders[order_id] = {
                    'id': order_id,
                    'symbol': context.symbol,
                    'side': tp_side,
                    'type': 'take_profit',
                    'amount': pos['size'],
                    'target_price': target_price,
                    'status': 'open',
                    'reason': reason,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                await connection_manager.broadcast({
                    'type': 'take_profit_set',
                    'order': orders[order_id]
                })
                
                return json.dumps({
                    "success": True,
                    "order_id": order_id,
                    "type": "take_profit",
                    "target_price": target_price,
                    "position_side": pos['side'],
                    "position_size": pos['size']
                })
                
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)})
        
        @function_tool
        async def get_current_position(
            ctx: RunContextWrapper[TradingContext]
        ) -> str:
            """
            Get the current position for the trading symbol.
            Returns position side (long/short/none), size, entry price, and unrealized PnL.
            """
            context = ctx.context
            
            try:
                ticker = await exchange_manager.get_ticker(context.exchange_id, context.symbol)
                current_price = ticker.get('last', 0)
                
                if context.symbol not in positions or positions[context.symbol]['side'] == 'none':
                    return json.dumps({
                        "symbol": context.symbol,
                        "side": "none",
                        "size": 0,
                        "entry_price": 0,
                        "current_price": current_price,
                        "unrealized_pnl": 0,
                        "unrealized_pnl_percent": 0
                    })
                
                pos = positions[context.symbol]
                
                # Calculate unrealized PnL
                if pos['side'] == 'long':
                    pnl = (current_price - pos['entry_price']) * pos['size']
                    pnl_percent = ((current_price / pos['entry_price']) - 1) * 100
                else:  # short
                    pnl = (pos['entry_price'] - current_price) * pos['size']
                    pnl_percent = ((pos['entry_price'] / current_price) - 1) * 100
                
                return json.dumps({
                    "symbol": context.symbol,
                    "side": pos['side'],
                    "size": pos['size'],
                    "entry_price": pos['entry_price'],
                    "current_price": current_price,
                    "unrealized_pnl": round(pnl, 2),
                    "unrealized_pnl_percent": round(pnl_percent, 2)
                })
                
            except Exception as e:
                return json.dumps({"error": str(e)})
        
        @function_tool
        async def get_open_orders(
            ctx: RunContextWrapper[TradingContext]
        ) -> str:
            """
            Get all open orders for the trading symbol.
            """
            context = ctx.context
            
            open_orders = [
                order for order in orders.values()
                if order['symbol'] == context.symbol and order['status'] == 'open'
            ]
            
            return json.dumps({
                "symbol": context.symbol,
                "open_orders": open_orders,
                "count": len(open_orders)
            })
        
        @function_tool
        async def cancel_order(
            ctx: RunContextWrapper[TradingContext],
            order_id: str,
            reason: str
        ) -> str:
            """
            Cancel an open order.
            
            Args:
                order_id: The ID of the order to cancel
                reason: Brief explanation for cancellation
            """
            context = ctx.context
            
            if order_id not in orders:
                return json.dumps({"success": False, "error": "Order not found"})
            
            order = orders[order_id]
            if order['status'] != 'open':
                return json.dumps({"success": False, "error": f"Order is already {order['status']}"})
            
            try:
                await exchange_manager.cancel_order(
                    context.exchange_id,
                    order_id,
                    context.symbol
                )
                
                orders[order_id]['status'] = 'cancelled'
                orders[order_id]['cancel_reason'] = reason
                
                await connection_manager.broadcast({
                    'type': 'order_cancelled',
                    'order_id': order_id,
                    'reason': reason
                })
                
                return json.dumps({
                    "success": True,
                    "order_id": order_id,
                    "status": "cancelled"
                })
                
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)})
        
        @function_tool
        async def close_position(
            ctx: RunContextWrapper[TradingContext],
            reason: str
        ) -> str:
            """
            Close the entire current position at market price.
            
            Args:
                reason: Brief explanation for closing the position
            """
            context = ctx.context
            
            if context.symbol not in positions or positions[context.symbol]['side'] == 'none':
                return json.dumps({"success": False, "error": "No open position to close"})
            
            pos = positions[context.symbol]
            
            try:
                # Close by placing opposite market order
                close_side = 'sell' if pos['side'] == 'long' else 'buy'
                
                ticker = await exchange_manager.get_ticker(context.exchange_id, context.symbol)
                current_price = ticker.get('last', 0)
                
                order = await exchange_manager.place_order(
                    context.exchange_id,
                    context.symbol,
                    close_side,
                    'market',
                    pos['size']
                )
                
                # Calculate realized PnL
                if pos['side'] == 'long':
                    realized_pnl = (current_price - pos['entry_price']) * pos['size']
                else:
                    realized_pnl = (pos['entry_price'] - current_price) * pos['size']
                
                order_id = order.get('id', f"close_{datetime.utcnow().timestamp()}")
                
                orders[order_id] = {
                    'id': order_id,
                    'symbol': context.symbol,
                    'side': close_side,
                    'type': 'close_position',
                    'amount': pos['size'],
                    'price': current_price,
                    'status': 'filled',
                    'reason': reason,
                    'realized_pnl': realized_pnl,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                # Reset position
                positions[context.symbol] = {'side': 'none', 'size': 0, 'entry_price': 0}
                
                await connection_manager.broadcast({
                    'type': 'position_closed',
                    'order': orders[order_id],
                    'realized_pnl': realized_pnl
                })
                
                return json.dumps({
                    "success": True,
                    "order_id": order_id,
                    "closed_side": pos['side'],
                    "closed_size": pos['size'],
                    "close_price": current_price,
                    "realized_pnl": round(realized_pnl, 2),
                    "reason": reason
                })
                
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)})
        
        @function_tool
        async def get_account_balance(
            ctx: RunContextWrapper[TradingContext]
        ) -> str:
            """
            Get account balance and margin information.
            """
            context = ctx.context
            
            try:
                balance = await exchange_manager.get_balance(context.exchange_id)
                
                return json.dumps({
                    "total_equity": balance.get('total', 0),
                    "available_balance": balance.get('free', 0),
                    "used_margin": balance.get('used', 0),
                    "currency": "USDT"
                })
                
            except Exception as e:
                return json.dumps({"error": str(e)})
        
        @function_tool
        async def analyze_and_wait(
            ctx: RunContextWrapper[TradingContext],
            analysis_summary: str,
            wait_reason: str
        ) -> str:
            """
            Record analysis and wait without taking action.
            Use this when market conditions are unclear or don't meet trading criteria.
            
            Args:
                analysis_summary: Summary of current market analysis
                wait_reason: Reason for not taking action
            """
            await connection_manager.broadcast({
                'type': 'analysis',
                'symbol': ctx.context.symbol,
                'summary': analysis_summary,
                'action': 'wait',
                'reason': wait_reason,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            return json.dumps({
                "action": "wait",
                "analysis": analysis_summary,
                "reason": wait_reason
            })
        
        return [
            place_market_order,
            place_limit_order,
            set_stop_loss,
            set_take_profit,
            get_current_position,
            get_open_orders,
            cancel_order,
            close_position,
            get_account_balance,
            analyze_and_wait,
        ]


# ============== AI Trading Agent ==============

class AITradingAgent:
    """
    AI Trading Agent using OpenAI Agents SDK.
    This agent can analyze market data and execute trading decisions using tools.
    """
    
    def __init__(
        self,
        agent_id: str,
        model_config: dict,
        exchange_manager,
        connection_manager,
        trading_context: TradingContext,
        system_prompt: str
    ):
        self.agent_id = agent_id
        self.model_config = model_config
        self.trading_context = trading_context
        self.exchange_manager = exchange_manager
        self.connection_manager = connection_manager
        
        # Create trading tools
        self.trading_tools = TradingTools(exchange_manager, connection_manager)
        
        # Build the complete system prompt
        self.system_prompt = self._build_system_prompt(system_prompt)
        
        # Create the agent
        self.agent = Agent(
            name=f"TradingAgent_{agent_id}",
            instructions=self.system_prompt,
            tools=self.trading_tools.create_tools(),
            model=model_config.get('model', 'gpt-4o')
        )
        
        self.is_running = False
        self.last_analysis = None
    
    def _build_system_prompt(self, user_prompt: str) -> str:
        """Build complete system prompt for the trading agent"""
        return f"""You are a professional cryptocurrency trading agent. Your job is to analyze market data and make trading decisions.

## Your Trading Rules:
{user_prompt}

## Available Actions:
You have access to the following tools to manage trades:
1. place_market_order - Open a position at market price
2. place_limit_order - Place a limit order at a specific price
3. set_stop_loss - Set stop-loss to limit losses
4. set_take_profit - Set take-profit to lock in gains
5. get_current_position - Check your current position
6. get_open_orders - View open orders
7. cancel_order - Cancel an open order
8. close_position - Close entire position
9. get_account_balance - Check available funds
10. analyze_and_wait - Record analysis without trading

## Decision Process:
1. First, check your current position using get_current_position
2. Analyze the provided market data and indicators
3. If you have a position, evaluate if you should:
   - Hold and adjust stop-loss/take-profit
   - Close the position
   - Wait
4. If you have no position, evaluate if you should:
   - Open a new position (with stop-loss and take-profit)
   - Wait for better conditions

## Risk Management Rules:
- Always set stop-loss when opening a position
- Never risk more than the configured max position size
- Consider the risk/reward ratio before entering trades
- Close positions when conditions change significantly

## Important:
- Always provide clear reasoning for your decisions
- Be conservative - it's better to miss a trade than to lose money
- Consider market volatility and trend strength
- Factor in support/resistance levels from the indicators

Symbol: {self.trading_context.symbol}
Timeframe: {self.trading_context.timeframe}
Max Position Size: ${self.trading_context.max_position_size}
"""
    
    async def analyze(self, market_data: dict) -> dict:
        """
        Analyze market data and execute trading decisions.
        
        Args:
            market_data: Dict containing klines, indicators, and current price info
        
        Returns:
            Analysis result with actions taken
        """
        # Build the analysis message
        analysis_message = self._build_analysis_message(market_data)
        
        try:
            # Run the agent
            result = await Runner.run(
                self.agent,
                input=analysis_message,
                context=self.trading_context
            )
            
            self.last_analysis = {
                'timestamp': datetime.utcnow().isoformat(),
                'market_data': market_data,
                'result': result.final_output,
                'new_items': [str(item) for item in result.new_items]
            }
            
            # Broadcast analysis result
            await self.connection_manager.broadcast({
                'type': 'agent_analysis',
                'agent_id': self.agent_id,
                'result': result.final_output,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            return {
                'success': True,
                'output': result.final_output,
                'actions_taken': len([i for i in result.new_items if 'tool' in str(type(i)).lower()])
            }
            
        except Exception as e:
            logger.error(f"Agent analysis error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _build_analysis_message(self, market_data: dict) -> str:
        """Build the market analysis message for the agent"""
        klines = market_data.get('klines', [])
        indicators = market_data.get('indicators', {})
        
        last_kline = klines[-1] if klines else {}
        
        return f"""
## Current Market Analysis Request

**Symbol:** {self.trading_context.symbol}
**Timeframe:** {self.trading_context.timeframe}
**Current Time:** {datetime.utcnow().isoformat()}

### Price Information:
- Current Price: ${last_kline.get('close', 'N/A')}
- Open: ${last_kline.get('open', 'N/A')}
- High: ${last_kline.get('high', 'N/A')}
- Low: ${last_kline.get('low', 'N/A')}
- Volume: {last_kline.get('volume', 'N/A')}

### Technical Indicators:
{json.dumps(indicators, indent=2)}

### Recent Price Action (Last 10 Candles):
{json.dumps(klines[-10:] if len(klines) >= 10 else klines, indent=2)}

### Price Statistics (Last 24 Candles):
- 24-Period High: ${max(k.get('high', 0) for k in klines[-24:]) if len(klines) >= 24 else 'N/A'}
- 24-Period Low: ${min(k.get('low', float('inf')) for k in klines[-24:]) if len(klines) >= 24 else 'N/A'}
- Average Volume: {sum(k.get('volume', 0) for k in klines[-24:]) / min(24, len(klines)) if klines else 'N/A'}

---

Please analyze this data and make a trading decision. 
First check your current position, then decide what action to take.
Always explain your reasoning.
"""


# ============== Agent Manager ==============

class AgentManager:
    """
    Manages multiple AI Trading Agents
    """
    
    def __init__(self, exchange_manager, connection_manager):
        self.exchange_manager = exchange_manager
        self.connection_manager = connection_manager
        self.agents: Dict[str, AITradingAgent] = {}
        self.tasks: Dict[str, asyncio.Task] = {}
    
    def create_agent(
        self,
        agent_id: str,
        model_config: dict,
        trading_context: TradingContext,
        system_prompt: str
    ) -> AITradingAgent:
        """Create a new trading agent"""
        agent = AITradingAgent(
            agent_id=agent_id,
            model_config=model_config,
            exchange_manager=self.exchange_manager,
            connection_manager=self.connection_manager,
            trading_context=trading_context,
            system_prompt=system_prompt
        )
        self.agents[agent_id] = agent
        return agent
    
    def get_agent(self, agent_id: str) -> Optional[AITradingAgent]:
        """Get an agent by ID"""
        return self.agents.get(agent_id)
    
    def remove_agent(self, agent_id: str):
        """Remove an agent"""
        self.stop_agent(agent_id)
        if agent_id in self.agents:
            del self.agents[agent_id]
    
    async def start_agent(self, agent_id: str, interval_seconds: int = 60):
        """Start an agent's trading loop"""
        if agent_id not in self.agents:
            return False
        
        agent = self.agents[agent_id]
        agent.is_running = True
        
        async def run_loop():
            while agent.is_running:
                try:
                    # Fetch market data
                    klines = await self.exchange_manager.fetch_ohlcv(
                        agent.trading_context.exchange_id,
                        agent.trading_context.symbol,
                        agent.trading_context.timeframe,
                        100
                    )
                    
                    # Calculate indicators
                    from main import IndicatorCalculator
                    indicators = IndicatorCalculator.calculate_all(
                        klines,
                        ['RSI', 'ADX', 'CHOP', 'KAMA', 'BOLLINGER', 'MACD', 'EMA']
                    )
                    
                    # Run agent analysis
                    await agent.analyze({
                        'klines': klines,
                        'indicators': indicators
                    })
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Agent {agent_id} loop error: {e}")
                    await self.connection_manager.broadcast({
                        'type': 'agent_error',
                        'agent_id': agent_id,
                        'error': str(e)
                    })
                
                await asyncio.sleep(interval_seconds)
        
        self.tasks[agent_id] = asyncio.create_task(run_loop())
        return True
    
    def stop_agent(self, agent_id: str):
        """Stop an agent's trading loop"""
        if agent_id in self.agents:
            self.agents[agent_id].is_running = False
        
        if agent_id in self.tasks:
            self.tasks[agent_id].cancel()
            del self.tasks[agent_id]
    
    def get_all_status(self) -> List[dict]:
        """Get status of all agents"""
        return [
            {
                'agent_id': aid,
                'is_running': agent.is_running,
                'symbol': agent.trading_context.symbol,
                'timeframe': agent.trading_context.timeframe,
                'last_analysis': agent.last_analysis
            }
            for aid, agent in self.agents.items()
        ]
