# shared_state.py
# Defines a class to hold the application's shared state.

import asyncio
import logging
try:
    import config
except ImportError:
    config = None

from collections import deque
from typing import Dict, List, Optional, Any
import time
import math
import statistics
from datetime import datetime, timezone
from bot_notifier import BotNotifier

class SharedState:
    """
    非阻塞的状态管理类，用于 Web UI 显示，不影响交易流程
    """
    def __init__(self, notifier: Optional[BotNotifier] = None):
        self.lock = asyncio.Lock()
        self.account_balances = {} # {'exchange_id': {'total': ..., 'free': ..., 'USDT': ..., 'BTC': ...}}
        self.open_positions = {}   # {'exchange_id': {'symbol': position_info}}
        self.trade_history = deque(maxlen=500) # List of completed trades (increased capacity)
        self.logs = deque(maxlen=200) # Recent log messages
        self.indicator_data = {} # {'exchange_id': {'symbol': {'rsi': val, 'bbands':{...}}}}
        self.active_symbols = {} # {'exchange_id': ['SYMBOL1', 'SYMBOL2']}
        
        # === 新增：交易统计数据 ===
        self.order_history = deque(maxlen=1000)  # 订单历史记录
        self.trade_statistics = {}  # {'exchange_id': {'total_trades': 0, 'winning_trades': 0, ...}}
        self.daily_pnl = {}  # {'exchange_id': {'date': pnl_value}}
        self.equity_curve = deque(maxlen=1000)  # 权益曲线数据 [(timestamp, total_equity)]
        
        # === 详细财务指标 ===
        self.financial_metrics = {}  # {'exchange_id': {'total_profit': 0, 'total_loss': 0, ...}}
        
        # === 性能指标缓存 ===
        self.performance_metrics = {}  # {'exchange_id': {'sharpe_ratio': ..., 'max_drawdown': ...}}
        self.last_metrics_update = 0  # 上次更新时间戳
        
        # 非阻塞更新队列
        self.update_queue = asyncio.Queue(maxsize=500)
        self._update_task = None
        # === 报告器相关 ===
        self._reporter_task = None
        self.report_interval_seconds = 3600  # 默认 1 小时，可通过 start_metrics_reporter 配置
        # 使用外部传入的 notifier（例如 BotNotifier 实例），避免在此处直接创建
        self.notifier: BotNotifier = notifier

    def initialize(self):
        """初始化SharedState（应该在async context中调用）"""
        self.initialize_notifier()

    def start_background_updater(self):
        """启动后台更新任务"""
        if self._update_task is None:
            self._update_task = asyncio.create_task(self._background_updater())

    def initialize_notifier(self):
        notif = config.NOTIFICATIONS if config else {}
        interval = notif.get('metrics_interval_seconds') or notif.get('interval_seconds') or None

        # 启动 reporter（interval 为 None 则使用 SharedState 的默认）
        self.start_metrics_reporter(interval_seconds=interval)

    async def _background_updater(self):
        """后台处理更新队列，避免阻塞交易流程"""
        while True:
            try:
                update_func, args = await self.update_queue.get()
                await update_func(*args)
                self.update_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"SharedState 更新错误: {e}", exc_info=True)

    # === 非阻塞更新方法 ===
    
    def add_log_non_blocking(self, log_record):
        """非阻塞添加日志（从同步上下文调用）"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._add_log_internal(log_record), loop
                )
        except Exception:
            pass  # 静默失败，不影响主流程

    async def _add_log_internal(self, log_record):
        """内部日志添加方法"""
        async with self.lock:
            self.logs.appendleft(log_record)

    async def set_balance_non_blocking(self, exchange_id, balance):
        """非阻塞设置余额"""
        if self.update_queue.full():
            return  # 队列满时直接丢弃，不阻塞
        await self.update_queue.put((self.set_balance, (exchange_id, balance)))

    async def update_position_non_blocking(self, exchange_id, symbol, position_data):
        """非阻塞更新持仓"""
        if self.update_queue.full():
            return
        await self.update_queue.put((self.update_position, (exchange_id, symbol, position_data)))

    async def add_trade_history_non_blocking(self, trade):
        """非阻塞添加交易历史"""
        if self.update_queue.full():
            return
        await self.update_queue.put((self.add_trade_history, (trade,)))

    async def add_order_history_non_blocking(self, order):
        """非阻塞添加订单历史"""
        if self.update_queue.full():
            return
        await self.update_queue.put((self.add_order_history, (order,)))

    async def update_equity_non_blocking(self, timestamp: float, total_equity: float):
        """非阻塞更新权益曲线"""
        if self.update_queue.full():
            return
        await self.update_queue.put((self.update_equity_curve, (timestamp, total_equity)))
    
    # === 保留原有方法（用于非关键路径） ===

    # === 新增：接收交易/订单详情（包含手续费等），并更新统计） ===
    async def add_trade_detail(self, trade: Dict[str, Any]):
        """
        添加单笔成交详情，trade 应包含至少:
         - exchange_id
         - timestamp (秒)
         - pnl 或 profit（数值，可为负）
         - fee（数值，可无）
         - total_equity（可选，若提供会更新 equity_curve）
        """
        async with self.lock:
            self.trade_history.appendleft(trade)
            exchange_id = trade.get("exchange_id", "unknown")
            
            # 提取 pnl
            pnl = None
            for k in ("pnl", "profit", "realizedPnl", "net", "realizedProfit"):
                if trade.get(k) is not None:
                    try:
                        pnl = float(trade.get(k))
                        break
                    except Exception:
                        pass
            
            # 提取 fee
            fee = 0.0
            fee_obj = trade.get("fee")
            if fee_obj is not None:
                if isinstance(fee_obj, dict):
                    fee = float(fee_obj.get("cost", 0) or fee_obj.get("value", 0) or 0)
                else:
                    try:
                        fee = float(fee_obj)
                    except Exception:
                        fee = 0.0
            
            # Debug logging for fee extraction
            if fee == 0 and fee_obj is not None:
                logging.warning(f"[add_trade_detail] Fee extraction returned 0 for fee_obj: {fee_obj}")
            
            ts = trade.get("timestamp", time.time())
            # 更新订单历史也保留成交明细
            self.order_history.appendleft({"exchange_id": exchange_id, "trade": trade})
            
            # 更新统计
            stats = self.trade_statistics.setdefault(exchange_id, {
                "total_trades": 0, 
                "winning_trades": 0, 
                "losing_trades": 0, 
                "total_fee": 0.0
            })
            
            # update financial metrics
            fin_metrics = self.financial_metrics.setdefault(exchange_id, {
                "total_profit": 0.0,
                "total_loss": 0.0,
                "net_profit": 0.0,
                "total_fee": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
            })
            
            # Only count as a trade if there's actual PnL (not just a fee record)
            if pnl is not None and pnl != 0:
                stats["total_trades"] = stats.get("total_trades", 0) + 1
            
            if pnl is not None:
                if pnl > 0:
                    stats["winning_trades"] = stats.get("winning_trades", 0) + 1
                    fin_metrics["total_profit"] += pnl
                    fin_metrics["gross_profit"] += pnl
                elif pnl < 0:
                    stats["losing_trades"] = stats.get("losing_trades", 0) + 1
                    fin_metrics["total_loss"] += abs(pnl)
                    fin_metrics["gross_loss"] += pnl  # 负值
                
                # daily pnl (use timezone-aware UTC)
                # Convert milliseconds to seconds if needed
                ts_seconds = ts / 1000 if ts > 1e10 else ts
                day = datetime.fromtimestamp(ts_seconds, timezone.utc).strftime("%Y-%m-%d")
                day_map = self.daily_pnl.setdefault(exchange_id, {})
                day_map[day] = day_map.get(day, 0.0) + float(pnl)
            
            # 累计手续费
            if fee > 0:
                stats["total_fee"] = stats.get("total_fee", 0.0) + fee
                fin_metrics["total_fee"] += fee
                logging.debug(f"[add_trade_detail] 累计手续费: {exchange_id} +{fee:.4f} USDT, 总计: {fin_metrics['total_fee']:.4f} USDT")
            
            # 计算净利润 = 总盈利 - 总亏损 - 手续费
            fin_metrics["net_profit"] = fin_metrics["total_profit"] - fin_metrics["total_loss"] - fin_metrics["total_fee"]
            
            # 如果提供 total_equity，则更新权益曲线
            total_equity = trade.get("total_equity")
            if total_equity is not None:
                try:
                    self.equity_curve.append((ts, float(total_equity)))
                except Exception:
                    pass

    async def add_trade_detail_non_blocking(self, trade: Dict[str, Any]):
        """将 add_trade_detail 放到更新队列中以非阻塞方式处理"""
        if self.update_queue.full():
            return
        await self.update_queue.put((self.add_trade_detail, (trade,)))

    # === 指标计算辅助方法 ===
    def _compute_win_rate(self, exchange_id: Optional[str] = None) -> float:
        """基于 trade_history 计算胜率"""
        wins = 0
        total = 0
        for t in list(self.trade_history):
            if exchange_id and t.get("exchange_id") != exchange_id:
                continue
            pnl = t.get("pnl") if t.get("pnl") is not None else t.get("profit")
            if pnl is None:
                continue
            total += 1
            if pnl > 0:
                wins += 1
        return (wins / total) if total > 0 else 0.0

    def _compute_max_drawdown(self, equity_points: List[tuple]) -> float:
        """计算最大回撤，equity_points = [(ts, equity), ...]"""
        if not equity_points:
            return 0.0
        peak = -math.inf
        max_dd = 0.0
        for _, eq in equity_points:
            if eq > peak:
                peak = eq
            drawdown = (peak - eq) / peak if peak > 0 else 0.0
            if drawdown > max_dd:
                max_dd = drawdown
        return max_dd

    def _compute_sharpe(self, equity_points: List[tuple], risk_free_rate: float = 0.0) -> float:
        """基于权益曲线近似计算年化夏普比（使用等间隔收益率近似）"""
        if len(equity_points) < 2:
            return 0.0
        # 计算收益率序列
        eq_sorted = sorted(equity_points, key=lambda x: x[0])
        returns = []
        intervals = []
        for i in range(1, len(eq_sorted)):
            prev_t, prev_eq = eq_sorted[i-1]
            t, eq = eq_sorted[i]
            if prev_eq == 0:
                continue
            r = (eq - prev_eq) / prev_eq
            returns.append(r)
            intervals.append(t - prev_t)
        if not returns:
            return 0.0
        mean_r = statistics.mean(returns)
        std_r = statistics.pstdev(returns) if len(returns) > 1 else 0.0
        # 年化因子：根据平均间隔估算每年周期数
        avg_interval = statistics.mean(intervals) if intervals else 0.0
        seconds_per_year = 365 * 24 * 3600
        periods_per_year = (seconds_per_year / avg_interval) if avg_interval > 0 else 252
        if std_r == 0:
            return 0.0
        sharpe = (mean_r - risk_free_rate/periods_per_year) / std_r * math.sqrt(periods_per_year)
        return sharpe

    # === 周期性上报器 ===
    def start_metrics_reporter(self, interval_seconds: Optional[int] = None):
        """
        启动周期性指标上报任务。
        interval_seconds: 报告间隔，默认使用 self.report_interval_seconds
        enable_telegram: 如果为 True 尝试通过 `BotNotifier` 发送（BotNotifier 自行读取配置）
        """
        logging.info(f"Metrics reporter started (interval={interval_seconds})")
        if interval_seconds:
            self.report_interval_seconds = interval_seconds
        if self._reporter_task is None:
            self._reporter_task = asyncio.create_task(self._metrics_reporter_loop())

    async def _metrics_reporter_loop(self):
        while True:
            try:
                await asyncio.sleep(self.report_interval_seconds)
                # 生成报告并记录到 logs
                async with self.lock:
                    msg_lines = []
                    exchanges = set(list(self.trade_statistics.keys()) + list(self.account_balances.keys()))
                    if not exchanges:
                        exchanges = {"global"}
                    for ex in exchanges:
                        # 过滤 equity_curve 到该交易所（如果曲线中保存了exchange info则需适配；当前为全局）
                        eq = list(self.equity_curve)
                        max_dd = self._compute_max_drawdown(eq)
                        sharpe = self._compute_sharpe(eq)
                        
                        stats = self.trade_statistics.get(ex, {})
                        fin_metrics = self.financial_metrics.get(ex, {})
                        
                        total = stats.get("total_trades", 0)
                        wins = stats.get("winning_trades", 0)
                        losses = stats.get("losing_trades", 0)
                        total_fee = stats.get("total_fee", 0.0)
                        
                        # 使用统计数据直接计算胜率，而不是重新遍历 trade_history
                        win_rate = (wins / total) if total > 0 else 0.0
                        
                        total_profit = fin_metrics.get("total_profit", 0.0)
                        total_loss = fin_metrics.get("total_loss", 0.0)
                        net_profit = fin_metrics.get("net_profit", 0.0)
                        
                        # 计算平均盈利和平均亏损
                        avg_profit = total_profit / wins if wins > 0 else 0.0
                        avg_loss = total_loss / losses if losses > 0 else 0.0
                        
                        # 盈亏比 (平均盈利/平均亏损)
                        profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0.0
                        
                        # 构建详细报告
                        line = (f"[{ex}] 交易统计:\n"
                                f"  总交易: {total} | 盈利: {wins} | 亏损: {losses} | 胜率: {win_rate:.2%}\n"
                                f"  总盈利: {total_profit:.4f} USDT | 总亏损: {total_loss:.4f} USDT\n"
                                f"  净利润: {net_profit:.4f} USDT | 手续费: {total_fee:.4f} USDT\n"
                                f"  平均盈利: {avg_profit:.4f} | 平均亏损: {avg_loss:.4f} | 盈亏比: {profit_loss_ratio:.2f}\n"
                                f"  最大回撤: {max_dd:.2%} | 夏普比率: {sharpe:.3f}")
                        msg_lines.append(line)
                    
                    report = "\n".join(msg_lines)
                    # 写入 log (timezone-aware UTC)
                    timestamp = datetime.now(timezone.utc).isoformat()
                    log_record = {"ts": timestamp, "type": "metrics_report", "text": report}
                    self.logs.appendleft(log_record)

                    logging.info(f"📊 财务指标报告 @ {timestamp}\n{report}")

                if self.notifier:
                    try:
                        await self.notifier.send_telegram_message(f"Metrics Report @ {timestamp}\n{report}")
                    except Exception:
                        # 不阻塞主循环，将错误记录到 logs
                        async with self.lock:
                            self.logs.appendleft({"ts": datetime.now(timezone.utc).isoformat(), "type": "notifier_error", "text": "failed to send notifier message"})
            except asyncio.CancelledError:
                break
            except Exception as e:
                # 报错写日志，但不抛出以保持循环
                async with self.lock:
                    self.logs.appendleft({"ts": datetime.now(timezone.utc).isoformat(), "type": "metrics_error", "text": str(e)})

    # (Telegram sending is handled by BotNotifier; no direct aiohttp usage here)

    async def set_balance(self, exchange_id, balance):
        async with self.lock:
            self.account_balances[exchange_id] = balance

    async def update_position(self, exchange_id, symbol, position_data):
        async with self.lock:
            if exchange_id not in self.open_positions:
                self.open_positions[exchange_id] = {}
            if position_data:
                self.open_positions[exchange_id][symbol] = position_data
            else: # position_data is None, meaning it's closed
                self.open_positions[exchange_id].pop(symbol, None)

    async def get_position(self, exchange_id, symbol):
        async with self.lock:
            return self.open_positions.get(exchange_id, {}).get(symbol) 

    async def add_trade_history(self, trade):
        async with self.lock:
            # Always keep raw trade in history
            self.trade_history.appendleft(trade)
            # Also treat this as a trade detail update to keep statistics in sync.
            exchange_id = trade.get("exchange_id", "unknown")
            
            # pnl can be under several common keys depending on exchange/format
            pnl = None
            for k in ("pnl", "profit", "realizedPnl", "net", "realizedProfit"):
                if trade.get(k) is not None:
                    try:
                        pnl = float(trade.get(k))
                        break
                    except Exception:
                        pass
            
            # fees likewise may be under different keys or nested fills
            fee = 0.0
            fee_obj = trade.get("fee")
            if fee_obj is not None:
                if isinstance(fee_obj, dict):
                    # 尝试从字典中提取fee
                    fee = float(fee_obj.get("cost", 0) or fee_obj.get("value", 0) or 0)
                else:
                    try:
                        fee = float(fee_obj)
                    except Exception:
                        fee = 0.0
            
            ts = trade.get("timestamp", time.time())
            # add to order_history as well for a full record
            self.order_history.appendleft({"exchange_id": exchange_id, "trade": trade})
            
            # update aggregate statistics
            stats = self.trade_statistics.setdefault(exchange_id, {
                "total_trades": 0, 
                "winning_trades": 0, 
                "losing_trades": 0, 
                "total_fee": 0.0
            })
            
            # update financial metrics
            fin_metrics = self.financial_metrics.setdefault(exchange_id, {
                "total_profit": 0.0,
                "total_loss": 0.0,
                "net_profit": 0.0,
                "total_fee": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
            })
            
            stats["total_trades"] = stats.get("total_trades", 0) + 1
            
            if pnl is not None:
                if pnl > 0:
                    stats["winning_trades"] = stats.get("winning_trades", 0) + 1
                    fin_metrics["total_profit"] += pnl
                    fin_metrics["gross_profit"] += pnl
                elif pnl < 0:
                    stats["losing_trades"] = stats.get("losing_trades", 0) + 1
                    fin_metrics["total_loss"] += abs(pnl)
                    fin_metrics["gross_loss"] += pnl  # 负值
                
                # 更新每日PnL
                # Convert milliseconds to seconds if needed
                ts_seconds = ts / 1000 if ts > 1e10 else ts
                day = datetime.fromtimestamp(ts_seconds, timezone.utc).strftime("%Y-%m-%d")
                day_map = self.daily_pnl.setdefault(exchange_id, {})
                day_map[day] = day_map.get(day, 0.0) + float(pnl)
            
            # 累计手续费
            if fee > 0:
                stats["total_fee"] = stats.get("total_fee", 0.0) + fee
                fin_metrics["total_fee"] += fee
            
            # 计算净利润 = 总盈利 - 总亏损 - 手续费
            fin_metrics["net_profit"] = fin_metrics["total_profit"] - fin_metrics["total_loss"] - fin_metrics["total_fee"]
            
            # update equity curve if provided
            total_equity = trade.get("total_equity")
            if total_equity is not None:
                try:
                    self.equity_curve.append((ts, float(total_equity)))
                except Exception:
                    pass

    async def add_order_history(self, order):
        """添加订单历史"""
        async with self.lock:
            # keep raw order
            self.order_history.appendleft(order)
            # attempt to extract fees from common fields/fills/trades and aggregate
            exchange_id = order.get("exchange_id", "unknown")
            fee = 0.0
            raw_fee = order.get("fee")
            if raw_fee is not None:
                if isinstance(raw_fee, dict):
                    for fk in ("cost", "value", "amount"):
                        if raw_fee.get(fk) is not None:
                            try:
                                fee = float(raw_fee.get(fk))
                                break
                            except Exception:
                                continue
                else:
                    try:
                        fee = float(raw_fee)
                    except Exception:
                        fee = 0.0
            elif order.get("fees") is not None:
                try:
                    fee = float(order.get("fees"))
                except Exception:
                    fee = 0.0
            else:
                for container_key in ("fills", "trades", "executions"):
                    items = order.get(container_key)
                    if isinstance(items, (list, tuple)):
                        for it in items:
                            if not it:
                                continue
                            f = it.get("fee") or it.get("commission") or 0.0
                            if isinstance(f, dict):
                                try:
                                    fee += float(f.get('cost') or f.get('value') or 0.0)
                                except Exception:
                                    pass
                            else:
                                try:
                                    fee += float(f)
                                except Exception:
                                    pass
            if fee:
                stats = self.trade_statistics.setdefault(exchange_id, {"total_trades": 0, "winning_trades": 0, "losing_trades": 0, "total_fee": 0.0})
                try:
                    stats["total_fee"] = stats.get("total_fee", 0.0) + float(fee)
                except Exception:
                    pass

    async def update_equity_curve(self, timestamp: float, total_equity: float):
        """更新权益曲线"""
        async with self.lock:
            self.equity_curve.append((timestamp, total_equity))

    async def update_trade_statistics(self, exchange_id: str, stats: Dict[str, Any]):
        """更新交易统计数据"""
        async with self.lock:
            if exchange_id not in self.trade_statistics:
                self.trade_statistics[exchange_id] = {}
            self.trade_statistics[exchange_id].update(stats)

    async def update_performance_metrics(self, exchange_id: str, metrics: Dict[str, Any]):
        """更新性能指标"""
        async with self.lock:
            if exchange_id not in self.performance_metrics:
                self.performance_metrics[exchange_id] = {}
            self.performance_metrics[exchange_id].update(metrics)
            self.last_metrics_update = time.time()

    async def add_log(self, log_record):
        async with self.lock:
            self.logs.appendleft(log_record)
            
    async def update_indicator_data(self, exchange_id, symbol, data):
        async with self.lock:
            if exchange_id not in self.indicator_data:
                self.indicator_data[exchange_id] = {}
            self.indicator_data[exchange_id][symbol] = data

    async def get_full_state(self, exchange_id: Optional[str] = None):
        """
        获取完整状态数据，支持按交易所过滤
        
        Args:
            exchange_id: 可选，指定交易所ID进行过滤
        """
        async with self.lock:
            if exchange_id:
                # 过滤指定交易所的数据
                return {
                    "account_balances": {exchange_id: self.account_balances.get(exchange_id, {})},
                    "open_positions": {exchange_id: self.open_positions.get(exchange_id, {})},
                    "trade_history": [t for t in self.trade_history if t.get('exchange_id') == exchange_id or t.get('info', {}).get('instId', '').startswith(exchange_id.upper())],
                    "order_history": [o for o in self.order_history if o.get('exchange_id') == exchange_id],
                    "logs": list(self.logs),
                    "indicator_data": {exchange_id: self.indicator_data.get(exchange_id, {})},
                    "trade_statistics": {exchange_id: self.trade_statistics.get(exchange_id, {})},
                    "financial_metrics": {exchange_id: self.financial_metrics.get(exchange_id, {})},
                    "performance_metrics": {exchange_id: self.performance_metrics.get(exchange_id, {})},
                    "equity_curve": list(self.equity_curve),
                }
            else:
                # 返回所有数据
                return {
                    "account_balances": self.account_balances,
                    "open_positions": self.open_positions,
                    "trade_history": list(self.trade_history),
                    "order_history": list(self.order_history),
                    "logs": list(self.logs),
                    "indicator_data": self.indicator_data,
                    "trade_statistics": self.trade_statistics,
                    "financial_metrics": self.financial_metrics,
                    "performance_metrics": self.performance_metrics,
                    "equity_curve": list(self.equity_curve),
                }

    async def set_active_symbols(self, active_symbols):
        async with self.lock:
            self.active_symbols = active_symbols

    async def stop(self):
        """停止后台更新任务"""
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        if self._reporter_task:
            self._reporter_task.cancel()
            try:
                await self._reporter_task
            except asyncio.CancelledError:
                pass
