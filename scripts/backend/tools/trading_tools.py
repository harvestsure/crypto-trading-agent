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


def create_trading_tools(exchange: CommonExchange) -> List[BaseTool]:
    """
    创建交易工具集
    
    Args:
        exchange: 交易所实例
        symbol: 交易对
    
    Returns:
        交易工具列表
    """
    return [
        OpenLongTool(exchange),
        OpenShortTool(exchange),
        ClosePositionTool(exchange),
        SetStopLossTool(exchange),
        SetTakeProfitTool(exchange),
        GetMarketInfoTool(exchange),
        CancelOrdersTool(exchange),
    ]
