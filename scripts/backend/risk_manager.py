# risk_manager.py
# This module is responsible for managing trade risk.

import config
import logging
from datetime import datetime
from typing import Dict, Optional

class RiskManager:
    """
    Manages risk for trades, such as calculating position size.
    增强版风险管理：
    - 单日亏损限制
    - 单symbol持仓限制
    - 交易暂停机制
    - 杠杆管理
    """
    def __init__(self):
        self.params = config.RISK_PARAMS
        
        # 单日盈亏跟踪
        self.daily_pnl = 0.0
        self.daily_pnl_reset_time = datetime.now().date()
        self.is_trading_halted = False  # 交易暂停标志
        
        # 各symbol持仓跟踪
        self.symbol_positions: Dict[str, float] = {}  # {symbol: position_value_usdt}
        
        logging.info("风险管理模块已初始化。")

    def check_daily_loss_limit(self, account_balance: float) -> bool:
        """
        检查单日亏损是否超过限制（默认10%）
        返回 True 表示可以继续交易，False 表示需要停止
        """
        # 检查是否需要重置每日盈亏
        current_date = datetime.now().date()
        if current_date > self.daily_pnl_reset_time:
            self.daily_pnl = 0.0
            self.daily_pnl_reset_time = current_date
            self.is_trading_halted = False
            logging.info("✅ 每日盈亏已重置")

        max_daily_loss_pct = self.params.get('max_daily_loss_pct', 0.10)
        max_daily_loss = account_balance * max_daily_loss_pct
        
        if self.daily_pnl <= -max_daily_loss:
            self.is_trading_halted = True
            logging.error(f"🚫 单日亏损 ${abs(self.daily_pnl):.2f} 已超过限制 ${max_daily_loss:.2f} ({max_daily_loss_pct*100}%)，停止所有交易！")
            return False
        
        return True

    def update_daily_pnl(self, pnl: float):
        """
        更新当日盈亏
        """
        self.daily_pnl += pnl
        max_daily_loss_pct = self.params.get('max_daily_loss_pct', 0.10)
        logging.info(f"📊 当日累计盈亏: ${self.daily_pnl:.2f} (限制: -{max_daily_loss_pct*100}%)")

    def check_symbol_position_limit(self, symbol: str, position_value: float, account_balance: float) -> bool:
        """
        检查单个symbol持仓是否超过总金额的限制（默认5%）
        """
        max_position_pct = self.params.get('max_position_per_symbol_pct', 0.05)
        max_position_value = account_balance * max_position_pct
        
        if position_value > max_position_value:
            logging.warning(f"⚠️ {symbol} 持仓金额 ${position_value:.2f} 超过限制 ${max_position_value:.2f} ({max_position_pct*100}%)")
            return False
        
        return True

    def can_open_position(self, symbol: str, position_value: float, account_balance: float) -> bool:
        """
        综合检查是否允许开仓
        
        Args:
            symbol: 交易对
            position_value: 拟开仓位的名义价值（USD）
            account_balance: 账户总余额（USD）
            
        Returns:
            True表示允许开仓，False表示拒绝
        """
        # 1. 检查交易是否被暂停
        if self.is_trading_halted:
            logging.warning(f"🚫 交易已暂停（达到单日亏损限制），拒绝开仓 {symbol}")
            return False
        
        # 2. 检查单日亏损限制
        if not self.check_daily_loss_limit(account_balance):
            logging.warning(f"🚫 达到单日亏损限制，拒绝开仓 {symbol}")
            return False
        
        # 3. 检查单symbol持仓限制
        current_position_value = self.symbol_positions.get(symbol, 0.0)
        total_position_value = current_position_value + position_value
        
        if not self.check_symbol_position_limit(symbol, total_position_value, account_balance):
            logging.warning(f"🚫 {symbol} 持仓超过限制，拒绝开仓")
            return False
        
        logging.info(f"✅ 风险检查通过: {symbol} 拟开仓 ${position_value:.2f}")
        return True

    def update_symbol_position(self, symbol: str, position_value: float):
        """
        更新symbol持仓金额
        
        Args:
            symbol: 交易对
            position_value: 持仓的名义价值（USD）
        """
        self.symbol_positions[symbol] = position_value
        logging.debug(f"更新持仓: {symbol} = ${position_value:.2f}")

    def reset_trading_halt(self):
        """手动重置交易暂停状态（谨慎使用）"""
        self.is_trading_halted = False
        logging.warning("⚠️ 手动重置交易暂停状态")

    def calculate_position_size(self, entry_price: float, account_balance: float = None, symbol: str = None, leverage: int = 1) -> float:
        """
        Calculates the position size in the base currency (e.g., BTC amount).
        
        Args:
            entry_price: 入场价格
            account_balance: 账户余额
            symbol: 交易对（用于风险检查）
            leverage: 杠杆倍数（默认1倍）
        
        Returns:
            仓位大小（币的数量）
        """
        if not entry_price or entry_price <= 0:
            logging.warning("无效的入场价，无法计算头寸大小。")
            return 0.0

        if self.params.get('fixed_trade_size'):
            # 固定仓位模式（币种无关）
            size = self.params['fixed_trade_size'] / entry_price
            notional_value = self.params['fixed_trade_size']
            required_margin = notional_value / leverage
            
            logging.info(f"固定仓位模式: 名义价值=${notional_value:.2f}, "
                        f"保证金=${required_margin:.2f} (杠杆{leverage}x)")
        elif account_balance:
            # 风险百分比模式
            risk_amount = account_balance * self.params['risk_per_trade']
            size = risk_amount / (entry_price * self.params['stop_loss_pct'])
            notional_value = size * entry_price
            required_margin = notional_value / leverage
            
            logging.info(f"风险仓位模式: 名义价值=${notional_value:.2f}, "
                        f"保证金=${required_margin:.2f} (杠杆{leverage}x)")
        else:
            logging.warning("无法计算头寸大小。账户余额未提供且未设置固定交易大小。")
            return 0.0

        # 风险检查（如果提供了必要信息）
        if symbol and account_balance:
            if not self.can_open_position(symbol, notional_value, account_balance):
                logging.warning(f"🚫 风险检查未通过，拒绝开仓 {symbol}")
                return 0.0

        logging.info(f"计算头寸大小：{size:.6f} @ 入场价 ${entry_price}")
        return size

    def get_stop_loss_price(self, entry_price: float, side: str) -> float:
        """
        Calculates the stop-loss price.
        """
        if side == 'buy':
            return entry_price * (1 - self.params['stop_loss_pct'])
        elif side == 'sell':
            return entry_price * (1 + self.params['stop_loss_pct'])
        return 0.0

    def get_take_profit_price(self, entry_price: float, side: str) -> float:
        """
        Calculates the take-profit price.
        """
        if side == 'buy':
            return entry_price * (1 + self.params['take_profit_pct'])
        elif side == 'sell':
            return entry_price * (1 - self.params['take_profit_pct'])
        return 0.0
    
    def get_status(self) -> Dict:
        """获取风险管理状态"""
        return {
            'is_trading_halted': self.is_trading_halted,
            'daily_pnl': self.daily_pnl,
            'daily_pnl_reset_time': self.daily_pnl_reset_time.isoformat(),
            'symbol_positions': self.symbol_positions.copy(),
            'max_daily_loss_pct': self.params.get('max_daily_loss_pct', 0.10),
            'max_position_per_symbol_pct': self.params.get('max_position_per_symbol_pct', 0.05),
        }
