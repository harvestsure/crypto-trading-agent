# config.py
# 后端配置文件

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ============== 交易所设置 ==============
EXCHANGE_SETTINGS = {
    'binance': {
        'default_leverage': 10,
        'hedge_mode': True,
    },
    'okx': {
        'default_leverage': 10,
        'hedge_mode': True,
    }
}

# ============== 交易所沙盒模式配置 ==============
EXCHANGE_SANDBOX_MODE = {
    'binance': os.getenv('BINANCE_TESTNET', 'false').lower() == 'true',
    'okx': os.getenv('OKX_TESTNET', 'false').lower() == 'true',
}

# ============== 代理配置 ==============
PROXY = {
    'enabled': os.getenv('PROXY_ENABLED', 'false').lower() == 'true',
    'url': os.getenv('PROXY_URL', ''),
}

# ============== 符号发现配置 ==============
SYMBOL_DISCOVERY = {
    'enabled': os.getenv('SYMBOL_DISCOVERY_ENABLED', 'true').lower() == 'true',
    'quote_currencies': ['USDT'],  # 默认只使用 USDT 交易对
    'top_n_symbols_per_currency': 10,  # 每个币种取前 10 个
    'min_24h_volume': 1000000,  # 最小 24 小时交易量（USDT）
}

# ============== 交易策略参数 ==============
STRATEGY_PARAMS = {
    'timeframe': '1h',  # 默认时间周期
    'max_open_positions': 5,  # 最大开仓数量
    'default_position_size': 1000.0,  # 默认仓位大小（USDT）
}

# ============== 风险管理参数 ==============
RISK_PARAMS = {
    'max_daily_loss_pct': 0.10,  # 单日最大亏损比例（10%）
    'max_position_size': 1000.0,  # 单个持仓最大金额（USDT）
    'max_leverage': 10,  # 最大杠杆倍数
    'stop_loss_pct': 0.05,  # 默认止损比例（5%）
    'take_profit_pct': 0.10,  # 默认止盈比例（10%）
}

# ============== 通知配置 ==============
NOTIFICATIONS = {
    'enabled': os.getenv('NOTIFICATIONS_ENABLED', 'false').lower() == 'true',
    'metrics_interval_seconds': 3600,  # 1小时
    'telegram_token': os.getenv('TELEGRAM_TOKEN', ''),
    'telegram_chat_id': os.getenv('TELEGRAM_CHAT_ID', ''),
}

# ============== 数据库配置 ==============
DATABASE = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'crypto_trading'),
}

# ============== 日志配置 ==============
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'crypto_trading.log')

# ============== 服务器配置 ==============
SERVER_HOST = os.getenv('SERVER_HOST', '0.0.0.0')
SERVER_PORT = int(os.getenv('SERVER_PORT', '8000'))
