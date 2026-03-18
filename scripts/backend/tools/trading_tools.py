"""
交易工具集
提供给 LLM 调用的交易相关工具
"""

import logging
from typing import Dict, Any, Optional, List
from tools.tool_registry import BaseTool, ToolDefinition, ToolParameter
from exchanges.common_exchange import CommonExchange
from common.data_types import OrderSide, OrderType

logger = logging.getLogger(__name__)


class OpenLongTool(BaseTool):
    """开多仓工具"""
    
    def __init__(self, exchange: CommonExchange):
        definition = ToolDefinition(
            name="open_long",
            description="开立多头仓位。当市场看涨时使用此工具建立多仓。",
            parameters=[
                ToolParameter(
                    name="symbol",
                    type="string",
                    description="交易对符号，例如 BTC/USDT",
                    required=True
                ),
                ToolParameter(
                    name="amount",
                    type="number",
                    description="开仓数量(合约张数)",
                    required=True
                ),
                ToolParameter(
                    name="price",
                    type="number",
                    description="限价单价格。如果不指定则使用市价单",
                    required=False
                ),
                ToolParameter(
                    name="leverage",
                    type="integer",
                    description="杠杆倍数，默认1倍",
                    required=False,
                    default=1
                ),
                ToolParameter(
                    name="stop_loss",
                    type="number",
                    description="止损价格（可选）",
                    required=False
                ),
                ToolParameter(
                    name="take_profit",
                    type="number",
                    description="止盈价格（可选）",
                    required=False
                )
            ],
            category="trading",
            timeout=30
        )
        super().__init__(definition)
        self.exchange = exchange
    
    async def execute(self, **kwargs) -> str:
        """执行开多仓操作"""
        symbol = kwargs.get('symbol')
        amount = kwargs.get('amount')
        price = kwargs.get('price')
        leverage = kwargs.get('leverage', 1)
        stop_loss = kwargs.get('stop_loss')
        take_profit = kwargs.get('take_profit')
        
        try:
            # 设置杠杆
            if leverage > 1:
                await self.exchange.set_leverage(symbol, leverage)
            
            # 确定订单类型
            order_type = OrderType.LIMIT if price else OrderType.MARKET
            
            # 构建订单参数
            params = self.exchange.build_order_params(
                side=OrderSide.BUY,
                pos_side='long',
                reduce_only=False
            )
            
            # 创建订单
            order = await self.exchange.create_order(
                symbol=symbol,
                order_type=order_type,
                side=OrderSide.BUY,
                amount=amount,
                price=price,
                params=params
            )
            
            if not order:
                return f'{{"status": "error", "message": "Failed to create long order"}}'
            
            order_id = order.get('id')
            result = {
                "status": "success",
                "action": "open_long",
                "order_id": order_id,
                "symbol": symbol,
                "amount": amount,
                "price": price or "market",
                "leverage": leverage
            }
            
            # 如果设置了止损止盈，创建条件订单
            if stop_loss:
                await self._create_stop_loss(symbol, amount, stop_loss)
                result["stop_loss"] = stop_loss
            
            if take_profit:
                await self._create_take_profit(symbol, amount, take_profit)
                result["take_profit"] = take_profit
            
            logger.info(f"✅ Opened long position: {result}")
            return f'{result}'
            
        except Exception as e:
            logger.error(f"❌ Error opening long position: {e}", exc_info=True)
            return f'{{"status": "error", "message": "{str(e)}"}}'
    
    async def _create_stop_loss(self, symbol: str, amount: float, stop_price: float):
        """创建止损订单"""
        try:
            params = self.exchange.build_order_params(
                side=OrderSide.SELL,
                pos_side='long',
                reduce_only=True,
                extra_params={'stopPrice': stop_price}
            )
            
            await self.exchange.create_order(
                symbol=symbol,
                order_type=OrderType.STOP_MARKET,
                side=OrderSide.SELL,
                amount=amount,
                params=params
            )
            logger.info(f"✅ Stop loss set at {stop_price}")
        except Exception as e:
            logger.error(f"❌ Error creating stop loss: {e}")
    
    async def _create_take_profit(self, symbol: str, amount: float, take_profit_price: float):
        """创建止盈订单"""
        try:
            params = self.exchange.build_order_params(
                side=OrderSide.SELL,
                pos_side='long',
                reduce_only=True,
                extra_params={'stopPrice': take_profit_price}
            )
            
            await self.exchange.create_order(
                symbol=symbol,
                order_type=OrderType.TAKE_PROFIT_MARKET,
                side=OrderSide.SELL,
                amount=amount,
                params=params
            )
            logger.info(f"✅ Take profit set at {take_profit_price}")
        except Exception as e:
            logger.error(f"❌ Error creating take profit: {e}")


class OpenShortTool(BaseTool):
    """开空仓工具"""
    
    def __init__(self, exchange: CommonExchange):
        definition = ToolDefinition(
            name="open_short",
            description="开立空头仓位。当市场看跌时使用此工具建立空仓。",
            parameters=[
                ToolParameter(
                    name="symbol",
                    type="string",
                    description="交易对符号，例如 BTC/USDT",
                    required=True
                ),
                ToolParameter(
                    name="amount",
                    type="number",
                    description="开仓数量(合约张数)",
                    required=True
                ),
                ToolParameter(
                    name="price",
                    type="number",
                    description="限价单价格。如果不指定则使用市价单",
                    required=False
                ),
                ToolParameter(
                    name="leverage",
                    type="integer",
                    description="杠杆倍数，默认1倍",
                    required=False,
                    default=1
                ),
                ToolParameter(
                    name="stop_loss",
                    type="number",
                    description="止损价格（可选）",
                    required=False
                ),
                ToolParameter(
                    name="take_profit",
                    type="number",
                    description="止盈价格（可选）",
                    required=False
                )
            ],
            category="trading",
            timeout=30
        )
        super().__init__(definition)
        self.exchange = exchange
    
    async def execute(self, **kwargs) -> str:
        """执行开空仓操作"""
        symbol = kwargs.get('symbol')
        amount = kwargs.get('amount')
        price = kwargs.get('price')
        leverage = kwargs.get('leverage', 1)
        stop_loss = kwargs.get('stop_loss')
        take_profit = kwargs.get('take_profit')
        
        try:
            # 设置杠杆
            if leverage > 1:
                await self.exchange.set_leverage(symbol, leverage)
            
            # 确定订单类型
            order_type = OrderType.LIMIT if price else OrderType.MARKET
            
            # 构建订单参数
            params = self.exchange.build_order_params(
                side=OrderSide.SELL,
                pos_side='short',
                reduce_only=False
            )
            
            # 创建订单
            order = await self.exchange.create_order(
                symbol=symbol,
                order_type=order_type,
                side=OrderSide.SELL,
                amount=amount,
                price=price,
                params=params
            )
            
            if not order:
                return f'{{"status": "error", "message": "Failed to create short order"}}'
            
            order_id = order.get('id')
            result = {
                "status": "success",
                "action": "open_short",
                "order_id": order_id,
                "symbol": symbol,
                "amount": amount,
                "price": price or "market",
                "leverage": leverage
            }
            
            # 如果设置了止损止盈，创建条件订单
            if stop_loss:
                await self._create_stop_loss(symbol, amount, stop_loss)
                result["stop_loss"] = stop_loss
            
            if take_profit:
                await self._create_take_profit(symbol, amount, take_profit)
                result["take_profit"] = take_profit
            
            logger.info(f"✅ Opened short position: {result}")
            return f'{result}'
            
        except Exception as e:
            logger.error(f"❌ Error opening short position: {e}", exc_info=True)
            return f'{{"status": "error", "message": "{str(e)}"}}'
    
    async def _create_stop_loss(self, symbol: str, amount: float, stop_price: float):
        """创建止损订单"""
        try:
            params = self.exchange.build_order_params(
                side=OrderSide.BUY,
                pos_side='short',
                reduce_only=True,
                extra_params={'stopPrice': stop_price}
            )
            
            await self.exchange.create_order(
                symbol=symbol,
                order_type=OrderType.STOP_MARKET,
                side=OrderSide.BUY,
                amount=amount,
                params=params
            )
            logger.info(f"✅ Stop loss set at {stop_price}")
        except Exception as e:
            logger.error(f"❌ Error creating stop loss: {e}")
    
    async def _create_take_profit(self, symbol: str, amount: float, take_profit_price: float):
        """创建止盈订单"""
        try:
            params = self.exchange.build_order_params(
                side=OrderSide.BUY,
                pos_side='short',
                reduce_only=True,
                extra_params={'stopPrice': take_profit_price}
            )
            
            await self.exchange.create_order(
                symbol=symbol,
                order_type=OrderType.TAKE_PROFIT_MARKET,
                side=OrderSide.BUY,
                amount=amount,
                params=params
            )
            logger.info(f"✅ Take profit set at {take_profit_price}")
        except Exception as e:
            logger.error(f"❌ Error creating take profit: {e}")


class ClosePositionTool(BaseTool):
    """平仓工具"""
    
    def __init__(self, exchange: CommonExchange):
        definition = ToolDefinition(
            name="close_position",
            description="平仓当前持仓。可以选择平多仓、平空仓或全部平仓。",
            parameters=[
                ToolParameter(
                    name="symbol",
                    type="string",
                    description="交易对符号，例如 BTC/USDT",
                    required=True
                ),
                ToolParameter(
                    name="side",
                    type="string",
                    description="要平仓的方向: 'long' (平多仓), 'short' (平空仓), 'all' (全部平仓)",
                    required=True,
                    enum=["long", "short", "all"]
                ),
                ToolParameter(
                    name="amount",
                    type="number",
                    description="平仓数量。如果不指定则全部平仓",
                    required=False
                ),
                ToolParameter(
                    name="price",
                    type="number",
                    description="限价单价格。如果不指定则使用市价单",
                    required=False
                )
            ],
            category="trading",
            timeout=30
        )
        super().__init__(definition)
        self.exchange = exchange
    
    async def execute(self, **kwargs) -> str:
        """执行平仓操作"""
        symbol = kwargs.get('symbol')
        side = kwargs.get('side')
        amount = kwargs.get('amount')
        price = kwargs.get('price')
        
        try:
            # 获取当前持仓
            positions = await self.exchange.fetch_positions([symbol])
            
            results = []
            
            for position in positions:
                pos_side = position.get('side')
                pos_contracts = abs(position.get('contracts', 0))
                
                if pos_contracts == 0:
                    continue
                
                # 判断是否需要平这个仓位
                if side == 'all' or side == pos_side:
                    close_amount = amount if amount else pos_contracts
                    
                    # 确定平仓方向（多仓用SELL平，空仓用BUY平）
                    close_side = OrderSide.SELL if pos_side == 'long' else OrderSide.BUY
                    order_type = OrderType.LIMIT if price else OrderType.MARKET
                    
                    params = self.exchange.build_order_params(
                        side=close_side,
                        pos_side=pos_side,
                        reduce_only=True
                    )
                    
                    order = await self.exchange.create_order(
                        symbol=symbol,
                        order_type=order_type,
                        side=close_side,
                        amount=close_amount,
                        price=price,
                        params=params
                    )
                    
                    if order:
                        results.append({
                            "side": pos_side,
                            "amount": close_amount,
                            "order_id": order.get('id')
                        })
            
            if results:
                return f'{{"status": "success", "action": "close_position", "closed": {results}}}'
            else:
                return f'{{"status": "info", "message": "No positions to close"}}'
            
        except Exception as e:
            logger.error(f"❌ Error closing position: {e}", exc_info=True)
            return f'{{"status": "error", "message": "{str(e)}"}}'


class SetStopLossTool(BaseTool):
    """设置止损工具"""
    
    def __init__(self, exchange: CommonExchange):
        definition = ToolDefinition(
            name="set_stop_loss",
            description="为现有持仓设置止损价格。价格触达时自动平仓止损。",
            parameters=[
                ToolParameter(
                    name="symbol",
                    type="string",
                    description="交易对符号，例如 BTC/USDT",
                    required=True
                ),
                ToolParameter(
                    name="side",
                    type="string",
                    description="持仓方向: 'long' 或 'short'",
                    required=True,
                    enum=["long", "short"]
                ),
                ToolParameter(
                    name="stop_price",
                    type="number",
                    description="止损触发价格",
                    required=True
                ),
                ToolParameter(
                    name="amount",
                    type="number",
                    description="止损数量。如果不指定则为全部持仓",
                    required=False
                )
            ],
            category="trading",
            timeout=30
        )
        super().__init__(definition)
        self.exchange = exchange
    
    async def execute(self, **kwargs) -> str:
        """执行设置止损操作"""
        symbol = kwargs.get('symbol')
        side = kwargs.get('side')
        stop_price = kwargs.get('stop_price')
        amount = kwargs.get('amount')
        
        try:
            # 获取当前持仓
            positions = await self.exchange.fetch_positions([symbol])
            position = next((p for p in positions if p.get('side') == side), None)
            
            if not position or position.get('contracts', 0) == 0:
                return f'{{"status": "error", "message": "No {side} position found"}}'
            
            pos_amount = abs(position.get('contracts', 0))
            stop_amount = amount if amount else pos_amount
            
            # 确定平仓方向
            close_side = OrderSide.SELL if side == 'long' else OrderSide.BUY
            
            params = self.exchange.build_order_params(
                side=close_side,
                pos_side=side,
                reduce_only=True,
                extra_params={'stopPrice': stop_price}
            )
            
            order = await self.exchange.create_order(
                symbol=symbol,
                order_type=OrderType.STOP_MARKET,
                side=close_side,
                amount=stop_amount,
                params=params
            )
            
            if order:
                return f'{{"status": "success", "action": "set_stop_loss", "side": "{side}", "stop_price": {stop_price}, "amount": {stop_amount}, "order_id": "{order.get("id")}"}}'
            else:
                return f'{{"status": "error", "message": "Failed to create stop loss order"}}'
            
        except Exception as e:
            logger.error(f"❌ Error setting stop loss: {e}", exc_info=True)
            return f'{{"status": "error", "message": "{str(e)}"}}'


class SetTakeProfitTool(BaseTool):
    """设置止盈工具"""
    
    def __init__(self, exchange: CommonExchange):
        definition = ToolDefinition(
            name="set_take_profit",
            description="为现有持仓设置止盈价格。价格触达时自动平仓获利。",
            parameters=[
                ToolParameter(
                    name="symbol",
                    type="string",
                    description="交易对符号，例如 BTC/USDT",
                    required=True
                ),
                ToolParameter(
                    name="side",
                    type="string",
                    description="持仓方向: 'long' 或 'short'",
                    required=True,
                    enum=["long", "short"]
                ),
                ToolParameter(
                    name="take_profit_price",
                    type="number",
                    description="止盈触发价格",
                    required=True
                ),
                ToolParameter(
                    name="amount",
                    type="number",
                    description="止盈数量。如果不指定则为全部持仓",
                    required=False
                )
            ],
            category="trading",
            timeout=30
        )
        super().__init__(definition)
        self.exchange = exchange
    
    async def execute(self, **kwargs) -> str:
        """执行设置止盈操作"""
        symbol = kwargs.get('symbol')
        side = kwargs.get('side')
        take_profit_price = kwargs.get('take_profit_price')
        amount = kwargs.get('amount')
        
        try:
            # 获取当前持仓
            positions = await self.exchange.fetch_positions([symbol])
            position = next((p for p in positions if p.get('side') == side), None)
            
            if not position or position.get('contracts', 0) == 0:
                return f'{{"status": "error", "message": "No {side} position found"}}'
            
            pos_amount = abs(position.get('contracts', 0))
            tp_amount = amount if amount else pos_amount
            
            # 确定平仓方向
            close_side = OrderSide.SELL if side == 'long' else OrderSide.BUY
            
            params = self.exchange.build_order_params(
                side=close_side,
                pos_side=side,
                reduce_only=True,
                extra_params={'stopPrice': take_profit_price}
            )
            
            order = await self.exchange.create_order(
                symbol=symbol,
                order_type=OrderType.TAKE_PROFIT_MARKET,
                side=close_side,
                amount=tp_amount,
                params=params
            )
            
            if order:
                return f'{{"status": "success", "action": "set_take_profit", "side": "{side}", "take_profit_price": {take_profit_price}, "amount": {tp_amount}, "order_id": "{order.get("id")}"}}'
            else:
                return f'{{"status": "error", "message": "Failed to create take profit order"}}'
            
        except Exception as e:
            logger.error(f"❌ Error setting take profit: {e}", exc_info=True)
            return f'{{"status": "error", "message": "{str(e)}"}}'


class GetMarketInfoTool(BaseTool):
    """获取市场信息工具"""
    
    def __init__(self, exchange: CommonExchange):
        definition = ToolDefinition(
            name="get_market_info",
            description="获取当前市场的详细信息，包括价格、成交量、24小时涨跌幅等。",
            parameters=[
                ToolParameter(
                    name="symbol",
                    type="string",
                    description="交易对符号，例如 BTC/USDT",
                    required=True
                )
            ],
            category="query",
            timeout=10
        )
        super().__init__(definition)
        self.exchange = exchange
    
    async def execute(self, **kwargs) -> str:
        """获取市场信息"""
        symbol = kwargs.get('symbol')
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            
            if ticker:
                info = {
                    "symbol": symbol,
                    "last": ticker.get('last'),
                    "bid": ticker.get('bid'),
                    "ask": ticker.get('ask'),
                    "high": ticker.get('high'),
                    "low": ticker.get('low'),
                    "volume": ticker.get('volume'),
                    "change_percent": ticker.get('percentage'),
                }
                return f'{info}'
            else:
                return f'{{"status": "error", "message": "Failed to fetch market info"}}'
            
        except Exception as e:
            logger.error(f"❌ Error getting market info: {e}", exc_info=True)
            return f'{{"status": "error", "message": "{str(e)}"}}'


class CancelOrdersTool(BaseTool):
    """取消订单工具"""
    
    def __init__(self, exchange: CommonExchange):
        definition = ToolDefinition(
            name="cancel_orders",
            description="取消指定的订单或取消所有未成交订单。",
            parameters=[
                ToolParameter(
                    name="symbol",
                    type="string",
                    description="交易对符号，例如 BTC/USDT",
                    required=True
                ),
                ToolParameter(
                    name="order_id",
                    type="string",
                    description="要取消的订单ID。如果不指定则取消所有订单",
                    required=False
                )
            ],
            category="trading",
            timeout=30
        )
        super().__init__(definition)
        self.exchange = exchange
    
    async def execute(self, **kwargs) -> str:
        """执行取消订单操作"""
        symbol = kwargs.get('symbol')
        order_id = kwargs.get('order_id')
        
        try:
            if order_id:
                # 取消单个订单
                result = await self.exchange.cancel_order(order_id, symbol)
                if result:
                    return f'{{"status": "success", "action": "cancel_order", "order_id": "{order_id}"}}'
                else:
                    return f'{{"status": "error", "message": "Failed to cancel order {order_id}"}}'
            else:
                # 取消所有订单
                result = await self.exchange.cancel_all_orders(symbol)
                return f'{{"status": "success", "action": "cancel_all_orders", "symbol": "{symbol}"}}'
            
        except Exception as e:
            logger.error(f"❌ Error canceling orders: {e}", exc_info=True)
            return f'{{"status": "error", "message": "{str(e)}"}}'


class ScaleInTool(BaseTool):
    """
    Scale into an existing position (pyramid / add-to-winner).
    Institutional swing traders scale in at confirmed breakouts or pullbacks
    to key EMA levels, increasing size when the trade is working.
    """

    def __init__(self, exchange: CommonExchange):
        definition = ToolDefinition(
            name="scale_in",
            description=(
                "Add to an existing profitable position (scale in / pyramid). "
                "Use when price has confirmed the trend direction and is pulling back to a key level "
                "(e.g. EMA-21, Kijun, VWAP). Adds additional contracts to the existing position."
            ),
            parameters=[
                ToolParameter("symbol", "string", "Trading pair, e.g. BTC/USDT", required=True),
                ToolParameter("side", "string", "Direction to add: 'long' or 'short'", required=True, enum=["long", "short"]),
                ToolParameter("amount", "number", "Number of contracts to add", required=True),
                ToolParameter("price", "number", "Limit price. Omit for market.", required=False),
                ToolParameter("stop_loss", "number", "Revised stop loss for the combined position", required=False),
                ToolParameter("reason", "string", "Why you are scaling in (used for logging)", required=False),
            ],
            category="trading",
            timeout=30,
        )
        super().__init__(definition)
        self.exchange = exchange

    async def execute(self, **kwargs) -> str:
        symbol = kwargs.get("symbol")
        side = kwargs.get("side")
        amount = kwargs.get("amount")
        price = kwargs.get("price")
        stop_loss = kwargs.get("stop_loss")
        reason = kwargs.get("reason", "scale in")

        try:
            order_side = OrderSide.BUY if side == "long" else OrderSide.SELL
            order_type = OrderType.LIMIT if price else OrderType.MARKET
            params = self.exchange.build_order_params(side=order_side, pos_side=side, reduce_only=False)

            order = await self.exchange.create_order(
                symbol=symbol, order_type=order_type, side=order_side,
                amount=amount, price=price, params=params
            )
            if not order:
                return '{"status": "error", "message": "Scale-in order failed"}'

            result = {
                "status": "success", "action": "scale_in",
                "order_id": order.get("id"), "symbol": symbol,
                "side": side, "amount": amount, "reason": reason,
            }
            if stop_loss:
                await self._adjust_stop(symbol, side, amount, stop_loss)
                result["revised_stop_loss"] = stop_loss

            logger.info(f"Scale-in executed: {result}")
            return str(result)
        except Exception as e:
            logger.error(f"Error scaling in: {e}", exc_info=True)
            return f'{{"status": "error", "message": "{str(e)}"}}'

    async def _adjust_stop(self, symbol, side, amount, stop_price):
        try:
            close_side = OrderSide.SELL if side == "long" else OrderSide.BUY
            params = self.exchange.build_order_params(
                side=close_side, pos_side=side, reduce_only=True,
                extra_params={"stopPrice": stop_price}
            )
            await self.exchange.create_order(
                symbol=symbol, order_type=OrderType.STOP_MARKET,
                side=close_side, amount=amount, params=params
            )
        except Exception as e:
            logger.warning(f"Failed to adjust stop on scale-in: {e}")


class PartialCloseTool(BaseTool):
    """
    Partially close a position to lock in profits at target levels.
    Institutional practice: close 1/3 at first target, 1/3 at second target,
    let the runner go with a trailing stop.
    """

    def __init__(self, exchange: CommonExchange):
        definition = ToolDefinition(
            name="partial_close",
            description=(
                "Partially close a position to lock in profits. "
                "Best practice: close 33% at R1, 33% at R2, trail the remaining 33%. "
                "Provide a percentage (0–100) or absolute amount."
            ),
            parameters=[
                ToolParameter("symbol", "string", "Trading pair, e.g. BTC/USDT", required=True),
                ToolParameter("side", "string", "Position side: 'long' or 'short'", required=True, enum=["long", "short"]),
                ToolParameter("close_percent", "number", "Percentage of position to close (0-100). Mutually exclusive with amount.", required=False),
                ToolParameter("amount", "number", "Absolute number of contracts to close. Mutually exclusive with close_percent.", required=False),
                ToolParameter("price", "number", "Limit price. Omit for market.", required=False),
                ToolParameter("reason", "string", "Target level description, e.g. 'R1 pivot at 74500'", required=False),
            ],
            category="trading",
            timeout=30,
        )
        super().__init__(definition)
        self.exchange = exchange

    async def execute(self, **kwargs) -> str:
        symbol = kwargs.get("symbol")
        side = kwargs.get("side")
        close_percent = kwargs.get("close_percent")
        amount = kwargs.get("amount")
        price = kwargs.get("price")
        reason = kwargs.get("reason", "take partial profit")

        try:
            positions = await self.exchange.fetch_positions([symbol])
            pos = next((p for p in positions if p.get("side") == side and abs(p.get("contracts", 0)) > 0), None)
            if not pos:
                return f'{{"status": "error", "message": "No {side} position found for {symbol}"}}'

            total = abs(pos.get("contracts", 0))
            if close_percent:
                close_amount = round(total * close_percent / 100, 8)
            elif amount:
                close_amount = min(amount, total)
            else:
                close_amount = total / 3  # default: close 1/3

            close_side = OrderSide.SELL if side == "long" else OrderSide.BUY
            order_type = OrderType.LIMIT if price else OrderType.MARKET
            params = self.exchange.build_order_params(side=close_side, pos_side=side, reduce_only=True)

            order = await self.exchange.create_order(
                symbol=symbol, order_type=order_type, side=close_side,
                amount=close_amount, price=price, params=params
            )
            if not order:
                return '{"status": "error", "message": "Partial close order failed"}'

            result = {
                "status": "success", "action": "partial_close",
                "order_id": order.get("id"), "symbol": symbol,
                "side": side, "closed_amount": close_amount,
                "remaining": round(total - close_amount, 8), "reason": reason,
            }
            logger.info(f"Partial close executed: {result}")
            return str(result)
        except Exception as e:
            logger.error(f"Error partial closing: {e}", exc_info=True)
            return f'{{"status": "error", "message": "{str(e)}"}}'


class TrailingStopTool(BaseTool):
    """
    Set a trailing stop to protect profits while letting winners run.
    Institutional use case: after 2R profit, move stop to break-even
    then activate a % or ATR-based trailing stop.
    """

    def __init__(self, exchange: CommonExchange):
        definition = ToolDefinition(
            name="set_trailing_stop",
            description=(
                "Set a trailing stop loss that moves with price. "
                "Use after the position moves 1.5–2R in profit to lock gains. "
                "Specify either a fixed callback rate (%) or an ATR multiplier."
            ),
            parameters=[
                ToolParameter("symbol", "string", "Trading pair, e.g. BTC/USDT", required=True),
                ToolParameter("side", "string", "Position side: 'long' or 'short'", required=True, enum=["long", "short"]),
                ToolParameter("callback_rate", "number", "Trailing distance as percentage of price (e.g. 1.5 = 1.5%)", required=False),
                ToolParameter("activation_price", "number", "Price at which the trailing stop activates", required=False),
                ToolParameter("amount", "number", "Contracts to protect. Omit for full position.", required=False),
            ],
            category="trading",
            timeout=30,
        )
        super().__init__(definition)
        self.exchange = exchange

    async def execute(self, **kwargs) -> str:
        symbol = kwargs.get("symbol")
        side = kwargs.get("side")
        callback_rate = kwargs.get("callback_rate", 1.5)
        activation_price = kwargs.get("activation_price")
        amount = kwargs.get("amount")

        try:
            if not amount:
                positions = await self.exchange.fetch_positions([symbol])
                pos = next((p for p in positions if p.get("side") == side and abs(p.get("contracts", 0)) > 0), None)
                amount = abs(pos.get("contracts", 0)) if pos else 0

            if not amount:
                return f'{{"status": "error", "message": "No {side} position to protect"}}'

            close_side = OrderSide.SELL if side == "long" else OrderSide.BUY
            extra: dict = {"callbackRate": callback_rate}
            if activation_price:
                extra["activationPrice"] = activation_price

            params = self.exchange.build_order_params(
                side=close_side, pos_side=side, reduce_only=True,
                extra_params=extra
            )

            order = await self.exchange.create_order(
                symbol=symbol, order_type=OrderType.TRAILING_STOP_MARKET,
                side=close_side, amount=amount, params=params
            )

            if not order:
                return '{"status": "error", "message": "Trailing stop order failed"}'

            result = {
                "status": "success", "action": "set_trailing_stop",
                "order_id": order.get("id"), "symbol": symbol,
                "side": side, "callback_rate_pct": callback_rate,
                "activation_price": activation_price,
            }
            logger.info(f"Trailing stop set: {result}")
            return str(result)
        except Exception as e:
            logger.error(f"Error setting trailing stop: {e}", exc_info=True)
            return f'{{"status": "error", "message": "{str(e)}"}}'


class GetSwingLevelsTool(BaseTool):
    """
    Fetch key swing high/low levels from recent OHLCV data.
    Used by the LLM to identify optimal entry zones, stop placements,
    and profit targets based on market structure.
    """

    def __init__(self, exchange: CommonExchange):
        definition = ToolDefinition(
            name="get_swing_levels",
            description=(
                "Analyze recent price action to identify key swing highs and lows, "
                "support/resistance zones, and suggest optimal stop and target levels. "
                "Essential for swing trade entry planning."
            ),
            parameters=[
                ToolParameter("symbol", "string", "Trading pair, e.g. BTC/USDT", required=True),
                ToolParameter("timeframe", "string", "Candle timeframe, e.g. '4h', '1d'", required=False),
                ToolParameter("lookback", "integer", "Number of candles to analyze (default 50)", required=False),
            ],
            category="analysis",
            timeout=15,
        )
        super().__init__(definition)
        self.exchange = exchange

    async def execute(self, **kwargs) -> str:
        symbol = kwargs.get("symbol")
        timeframe = kwargs.get("timeframe", "4h")
        lookback = kwargs.get("lookback", 50)

        try:
            klines = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=lookback)
            if not klines or len(klines) < 10:
                return '{"status": "error", "message": "Insufficient kline data"}'

            highs  = [k[2] for k in klines]
            lows   = [k[3] for k in klines]
            closes = [k[4] for k in klines]

            # Identify swing highs/lows with a 5-bar pivot window
            pivot_highs, pivot_lows = [], []
            window = 5
            for i in range(window, len(klines) - window):
                if highs[i] == max(highs[i - window: i + window + 1]):
                    pivot_highs.append(round(highs[i], 4))
                if lows[i] == min(lows[i - window: i + window + 1]):
                    pivot_lows.append(round(lows[i], 4))

            current_price = closes[-1]
            recent_high = max(highs[-20:])
            recent_low  = min(lows[-20:])

            # Key resistances above price
            resistances = sorted([h for h in pivot_highs if h > current_price])[:3]
            # Key supports below price
            supports    = sorted([l for l in pivot_lows if l < current_price], reverse=True)[:3]

            # ATR for stop sizing
            from utils.indicator_calculator import IndicatorCalculator
            atr_vals = IndicatorCalculator.atr(highs, lows, closes, 14)
            atr = next((v for v in reversed(atr_vals) if v and not (v != v)), 0)

            result = {
                "status": "success",
                "symbol": symbol,
                "timeframe": timeframe,
                "current_price": round(current_price, 4),
                "recent_range": {"high": round(recent_high, 4), "low": round(recent_low, 4)},
                "resistances": resistances,
                "supports": supports,
                "atr_14": round(atr, 4),
                "suggested_stop_long":   round(current_price - 1.5 * atr, 4),
                "suggested_stop_short":  round(current_price + 1.5 * atr, 4),
                "suggested_target_1x":   round(current_price + 2 * atr, 4),
                "suggested_target_2x":   round(current_price + 4 * atr, 4),
            }
            return str(result)
        except Exception as e:
            logger.error(f"Error getting swing levels: {e}", exc_info=True)
            return f'{{"status": "error", "message": "{str(e)}"}}'


def create_trading_tools(exchange: CommonExchange) -> List[BaseTool]:
    """
    Create the full institutional swing-trading tool set.
    """
    return [
        OpenLongTool(exchange),
        OpenShortTool(exchange),
        ClosePositionTool(exchange),
        SetStopLossTool(exchange),
        SetTakeProfitTool(exchange),
        ScaleInTool(exchange),
        PartialCloseTool(exchange),
        TrailingStopTool(exchange),
        GetSwingLevelsTool(exchange),
        CancelOrdersTool(exchange),
    ]
