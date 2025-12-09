# bot_notifier.py
# 机器人通知模块（用于Telegram等）

import logging
import asyncio
from typing import Optional, Dict, Any
import config

logger = logging.getLogger(__name__)


class BotNotifier:
    """
    机器人通知类
    用于发送交易信号、风险警告等到Telegram或其他渠道
    """
    
    def __init__(self):
        self.enabled = config.NOTIFICATIONS.get('enabled', False)
        self.telegram_token = config.NOTIFICATIONS.get('telegram_token', '')
        self.telegram_chat_id = config.NOTIFICATIONS.get('telegram_chat_id', '')
        
    async def send_message(self, message: str, message_type: str = 'info') -> bool:
        """
        发送消息
        
        Args:
            message: 消息内容
            message_type: 消息类型 (info, warning, error)
        
        Returns:
            是否发送成功
        """
        if not self.enabled:
            return True
        
        try:
            if self.telegram_token and self.telegram_chat_id:
                await self._send_telegram(message)
            
            logger.info(f"[{message_type.upper()}] {message}")
            return True
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False
    
    async def _send_telegram(self, message: str) -> bool:
        """发送Telegram消息"""
        try:
            import aiohttp
            
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    return resp.status == 200
        except Exception as e:
            logger.error(f"Telegram sending failed: {e}")
            return False
    
    async def notify_trade(self, agent_id: str, symbol: str, side: str, 
                          quantity: float, price: float, reason: str = '') -> bool:
        """发送交易通知"""
        message = f"🔔 交易信号 [{agent_id}]\n"
        message += f"交易对: {symbol}\n"
        message += f"方向: {side.upper()}\n"
        message += f"数量: {quantity}\n"
        message += f"价格: {price}\n"
        if reason:
            message += f"原因: {reason}\n"
        
        return await self.send_message(message, 'info')
    
    async def notify_warning(self, title: str, message: str) -> bool:
        """发送警告通知"""
        full_message = f"⚠️ {title}\n{message}"
        return await self.send_message(full_message, 'warning')
    
    async def notify_error(self, title: str, message: str) -> bool:
        """发送错误通知"""
        full_message = f"❌ {title}\n{message}"
        return await self.send_message(full_message, 'error')


# 全局通知器实例
_notifier: Optional[BotNotifier] = None


def get_notifier() -> BotNotifier:
    """获取全局通知器实例"""
    global _notifier
    if _notifier is None:
        _notifier = BotNotifier()
    return _notifier
