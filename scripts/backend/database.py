"""
SQLite Database Layer for CryptoAgent
Provides persistent storage for models, exchanges, agents, orders, and conversations
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
import os

DATABASE_PATH = os.environ.get("DATABASE_PATH", "crypto_agent.db")


@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_database():
    """Initialize database tables"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # AI Models table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_models (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                provider TEXT NOT NULL,
                api_key TEXT NOT NULL,
                base_url TEXT,
                model TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Exchanges table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exchanges (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                exchange TEXT NOT NULL,
                api_key TEXT NOT NULL,
                secret_key TEXT NOT NULL,
                passphrase TEXT,
                testnet BOOLEAN DEFAULT TRUE,
                status TEXT DEFAULT 'disconnected',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Agents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                model_id TEXT NOT NULL,
                exchange_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                indicators TEXT NOT NULL,
                prompt TEXT NOT NULL,
                max_position_size REAL DEFAULT 1000.0,
                risk_per_trade REAL DEFAULT 0.02,
                default_leverage INTEGER DEFAULT 1,
                status TEXT DEFAULT 'stopped',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (model_id) REFERENCES ai_models(id),
                FOREIGN KEY (exchange_id) REFERENCES exchanges(id)
            )
        """)
        
        # Orders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                order_type TEXT NOT NULL,
                amount REAL NOT NULL,
                price REAL,
                status TEXT DEFAULT 'pending',
                exchange_order_id TEXT,
                filled_amount REAL DEFAULT 0,
                filled_price REAL,
                pnl REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            )
        """)
        
        # Positions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                size REAL NOT NULL,
                entry_price REAL NOT NULL,
                current_price REAL,
                leverage INTEGER DEFAULT 1,
                unrealized_pnl REAL DEFAULT 0,
                liquidation_price REAL,
                margin REAL,
                opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                status TEXT DEFAULT 'open',
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            )
        """)
        
        # Conversations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tool_call TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            )
        """)
        
        # Tool calls table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tool_calls (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                conversation_id TEXT,
                name TEXT NOT NULL,
                arguments TEXT NOT NULL,
                result TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (agent_id) REFERENCES agents(id),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
        """)
        
        # Signals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                action TEXT NOT NULL,
                reason TEXT,
                take_profit REAL,
                stop_loss REAL,
                confidence REAL,
                indicators_snapshot TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            )
        """)
        
        # Balance history table (for profit charts)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS balance_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                exchange_id TEXT NOT NULL,
                total_balance REAL NOT NULL,
                available_balance REAL NOT NULL,
                unrealized_pnl REAL DEFAULT 0,
                realized_pnl REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (agent_id) REFERENCES agents(id),
                FOREIGN KEY (exchange_id) REFERENCES exchanges(id)
            )
        """)
        
        # Activity logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        print("Database initialized successfully")


# ============== AI Models CRUD ==============

class AIModelRepository:
    @staticmethod
    def create(model_data: Dict[str, Any]) -> Dict[str, Any]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ai_models (id, name, provider, api_key, base_url, model, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                model_data['id'],
                model_data['name'],
                model_data['provider'],
                model_data['api_key'],
                model_data.get('base_url'),
                model_data['model'],
                model_data.get('status', 'active')
            ))
            return AIModelRepository.get_by_id(model_data['id'])
    
    @staticmethod
    def get_by_id(model_id: str) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ai_models WHERE id = ?", (model_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def get_all() -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ai_models ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    def update(model_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            fields = []
            values = []
            for key, value in data.items():
                if key != 'id':
                    fields.append(f"{key} = ?")
                    values.append(value)
            values.append(model_id)
            cursor.execute(f"UPDATE ai_models SET {', '.join(fields)} WHERE id = ?", values)
            return AIModelRepository.get_by_id(model_id)
    
    @staticmethod
    def delete(model_id: str) -> bool:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ai_models WHERE id = ?", (model_id,))
            return cursor.rowcount > 0


# ============== Exchanges CRUD ==============

class ExchangeRepository:
    @staticmethod
    def create(exchange_data: Dict[str, Any]) -> Dict[str, Any]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO exchanges (id, name, exchange, api_key, secret_key, passphrase, testnet, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                exchange_data['id'],
                exchange_data['name'],
                exchange_data['exchange'],
                exchange_data['api_key'],
                exchange_data['secret_key'],
                exchange_data.get('passphrase'),
                exchange_data.get('testnet', True),
                exchange_data.get('status', 'disconnected')
            ))
            return ExchangeRepository.get_by_id(exchange_data['id'])
    
    @staticmethod
    def get_by_id(exchange_id: str) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM exchanges WHERE id = ?", (exchange_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def get_all() -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM exchanges ORDER BY created_at DESC")
            return [dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    def update(exchange_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            fields = []
            values = []
            for key, value in data.items():
                if key != 'id':
                    fields.append(f"{key} = ?")
                    values.append(value)
            values.append(exchange_id)
            cursor.execute(f"UPDATE exchanges SET {', '.join(fields)} WHERE id = ?", values)
            return ExchangeRepository.get_by_id(exchange_id)
    
    @staticmethod
    def delete(exchange_id: str) -> bool:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM exchanges WHERE id = ?", (exchange_id,))
            return cursor.rowcount > 0


# ============== Agents CRUD ==============

class AgentRepository:
    @staticmethod
    def create(agent_data: Dict[str, Any]) -> Dict[str, Any]:
        with get_db() as conn:
            cursor = conn.cursor()
            indicators = json.dumps(agent_data.get('indicators', []))
            cursor.execute("""
                INSERT INTO agents (id, name, model_id, exchange_id, symbol, timeframe, indicators, prompt, 
                                   max_position_size, risk_per_trade, default_leverage, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                agent_data['id'],
                agent_data['name'],
                agent_data['model_id'],
                agent_data['exchange_id'],
                agent_data['symbol'],
                agent_data['timeframe'],
                indicators,
                agent_data['prompt'],
                agent_data.get('max_position_size', 1000.0),
                agent_data.get('risk_per_trade', 0.02),
                agent_data.get('default_leverage', 1),
                agent_data.get('status', 'stopped')
            ))
            return AgentRepository.get_by_id(agent_data['id'])
    
    @staticmethod
    def get_by_id(agent_id: str) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
            row = cursor.fetchone()
            if row:
                data = dict(row)
                data['indicators'] = json.loads(data['indicators'])
                return data
            return None
    
    @staticmethod
    def get_all() -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agents ORDER BY created_at DESC")
            results = []
            for row in cursor.fetchall():
                data = dict(row)
                data['indicators'] = json.loads(data['indicators'])
                results.append(data)
            return results
    
    @staticmethod
    def update(agent_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            fields = []
            values = []
            for key, value in data.items():
                if key != 'id':
                    if key == 'indicators':
                        value = json.dumps(value)
                    fields.append(f"{key} = ?")
                    values.append(value)
            values.append(agent_id)
            cursor.execute(f"UPDATE agents SET {', '.join(fields)} WHERE id = ?", values)
            return AgentRepository.get_by_id(agent_id)
    
    @staticmethod
    def delete(agent_id: str) -> bool:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
            return cursor.rowcount > 0
    
    @staticmethod
    def get_by_model_id(model_id: str) -> List[Dict[str, Any]]:
        """获取使用指定model的所有agents"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agents WHERE model_id = ?", (model_id,))
            results = []
            for row in cursor.fetchall():
                data = dict(row)
                data['indicators'] = json.loads(data['indicators'])
                results.append(data)
            return results
    
    @staticmethod
    def get_by_exchange_id(exchange_id: str) -> List[Dict[str, Any]]:
        """获取使用指定exchange的所有agents"""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agents WHERE exchange_id = ?", (exchange_id,))
            results = []
            for row in cursor.fetchall():
                data = dict(row)
                data['indicators'] = json.loads(data['indicators'])
                results.append(data)
            return results


# ============== Orders CRUD ==============

class OrderRepository:
    @staticmethod
    def create(order_data: Dict[str, Any]) -> Dict[str, Any]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO orders (id, agent_id, symbol, side, order_type, amount, price, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order_data['id'],
                order_data['agent_id'],
                order_data['symbol'],
                order_data['side'],
                order_data['order_type'],
                order_data['amount'],
                order_data.get('price'),
                order_data.get('status', 'pending')
            ))
            return OrderRepository.get_by_id(order_data['id'])
    
    @staticmethod
    def get_by_id(order_id: str) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    @staticmethod
    def get_by_agent(agent_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM orders WHERE agent_id = ? ORDER BY created_at DESC LIMIT ?",
                (agent_id, limit)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    def update(order_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            data['updated_at'] = datetime.now().isoformat()
            fields = []
            values = []
            for key, value in data.items():
                if key != 'id':
                    fields.append(f"{key} = ?")
                    values.append(value)
            values.append(order_id)
            cursor.execute(f"UPDATE orders SET {', '.join(fields)} WHERE id = ?", values)
            return OrderRepository.get_by_id(order_id)


# ============== Positions CRUD ==============

class PositionRepository:
    @staticmethod
    def create(position_data: Dict[str, Any]) -> Dict[str, Any]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO positions (agent_id, symbol, side, size, entry_price, current_price, 
                                       leverage, unrealized_pnl, liquidation_price, margin, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position_data['agent_id'],
                position_data['symbol'],
                position_data['side'],
                position_data['size'],
                position_data['entry_price'],
                position_data.get('current_price', position_data['entry_price']),
                position_data.get('leverage', 1),
                position_data.get('unrealized_pnl', 0),
                position_data.get('liquidation_price'),
                position_data.get('margin'),
                'open'
            ))
            return PositionRepository.get_open_by_agent(position_data['agent_id'])[-1]
    
    @staticmethod
    def get_open_by_agent(agent_id: str) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM positions WHERE agent_id = ? AND status = 'open' ORDER BY opened_at DESC",
                (agent_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    def update_price(position_id: int, current_price: float, unrealized_pnl: float):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE positions SET current_price = ?, unrealized_pnl = ? WHERE id = ?",
                (current_price, unrealized_pnl, position_id)
            )
    
    @staticmethod
    def close_position(position_id: int):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE positions SET status = 'closed', closed_at = ? WHERE id = ?",
                (datetime.now().isoformat(), position_id)
            )


# ============== Conversations CRUD ==============

class ConversationRepository:
    @staticmethod
    def add_message(agent_id: str, role: str, content: str, tool_call: Optional[Dict] = None) -> Dict[str, Any]:
        with get_db() as conn:
            cursor = conn.cursor()
            message_id = f"msg_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            tool_call_json = json.dumps(tool_call) if tool_call else None
            cursor.execute("""
                INSERT INTO conversations (id, agent_id, role, content, tool_call)
                VALUES (?, ?, ?, ?, ?)
            """, (message_id, agent_id, role, content, tool_call_json))
            return ConversationRepository.get_by_id(message_id)
    
    @staticmethod
    def get_by_id(message_id: str) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM conversations WHERE id = ?", (message_id,))
            row = cursor.fetchone()
            if row:
                data = dict(row)
                if data.get('tool_call'):
                    data['tool_call'] = json.loads(data['tool_call'])
                return data
            return None
    
    @staticmethod
    def get_by_agent(agent_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM conversations WHERE agent_id = ? ORDER BY created_at DESC LIMIT ?",
                (agent_id, limit)
            )
            results = []
            for row in cursor.fetchall():
                data = dict(row)
                if data.get('tool_call'):
                    data['tool_call'] = json.loads(data['tool_call'])
                results.append(data)
            return results[::-1]  # Return in chronological order


# ============== Tool Calls CRUD ==============

class ToolCallRepository:
    @staticmethod
    def create(tool_data: Dict[str, Any]) -> Dict[str, Any]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tool_calls (id, agent_id, conversation_id, name, arguments, result, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                tool_data['id'],
                tool_data['agent_id'],
                tool_data.get('conversation_id'),
                tool_data['name'],
                json.dumps(tool_data['arguments']),
                tool_data.get('result'),
                tool_data.get('status', 'pending')
            ))
            return ToolCallRepository.get_by_id(tool_data['id'])
    
    @staticmethod
    def get_by_id(tool_id: str) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tool_calls WHERE id = ?", (tool_id,))
            row = cursor.fetchone()
            if row:
                data = dict(row)
                data['arguments'] = json.loads(data['arguments'])
                return data
            return None
    
    @staticmethod
    def get_by_agent(agent_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM tool_calls WHERE agent_id = ? ORDER BY created_at DESC LIMIT ?",
                (agent_id, limit)
            )
            results = []
            for row in cursor.fetchall():
                data = dict(row)
                data['arguments'] = json.loads(data['arguments'])
                results.append(data)
            return results
    
    @staticmethod
    def update_result(tool_id: str, result: str, status: str):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE tool_calls SET result = ?, status = ? WHERE id = ?",
                (result, status, tool_id)
            )


# ============== Signals CRUD ==============

class SignalRepository:
    @staticmethod
    def create(signal_data: Dict[str, Any]) -> Dict[str, Any]:
        with get_db() as conn:
            cursor = conn.cursor()
            indicators_json = json.dumps(signal_data.get('indicators_snapshot', {}))
            cursor.execute("""
                INSERT INTO signals (agent_id, action, reason, take_profit, stop_loss, confidence, indicators_snapshot)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                signal_data['agent_id'],
                signal_data['action'],
                signal_data.get('reason'),
                signal_data.get('take_profit'),
                signal_data.get('stop_loss'),
                signal_data.get('confidence'),
                indicators_json
            ))
            return {"id": cursor.lastrowid, **signal_data}
    
    @staticmethod
    def get_by_agent(agent_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM signals WHERE agent_id = ? ORDER BY created_at DESC LIMIT ?",
                (agent_id, limit)
            )
            results = []
            for row in cursor.fetchall():
                data = dict(row)
                if data.get('indicators_snapshot'):
                    data['indicators_snapshot'] = json.loads(data['indicators_snapshot'])
                results.append(data)
            return results


# ============== Balance History CRUD ==============

class BalanceHistoryRepository:
    @staticmethod
    def record(agent_id: str, exchange_id: str, balance_data: Dict[str, Any]):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO balance_history (agent_id, exchange_id, total_balance, available_balance, 
                                            unrealized_pnl, realized_pnl)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                agent_id,
                exchange_id,
                balance_data['total_balance'],
                balance_data['available_balance'],
                balance_data.get('unrealized_pnl', 0),
                balance_data.get('realized_pnl', 0)
            ))
    
    @staticmethod
    def get_history(agent_id: str, days: int = 30) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM balance_history 
                WHERE agent_id = ? AND created_at >= datetime('now', ?)
                ORDER BY created_at ASC
            """, (agent_id, f'-{days} days'))
            return [dict(row) for row in cursor.fetchall()]


# ============== Activity Logs CRUD ==============

class ActivityLogRepository:
    @staticmethod
    def log(level: str, message: str, agent_id: Optional[str] = None, details: Optional[Dict] = None):
        with get_db() as conn:
            cursor = conn.cursor()
            details_json = json.dumps(details) if details else None
            cursor.execute("""
                INSERT INTO activity_logs (agent_id, level, message, details)
                VALUES (?, ?, ?, ?)
            """, (agent_id, level, message, details_json))
    
    @staticmethod
    def get_recent(limit: int = 100, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with get_db() as conn:
            cursor = conn.cursor()
            if agent_id:
                cursor.execute(
                    "SELECT * FROM activity_logs WHERE agent_id = ? ORDER BY created_at DESC LIMIT ?",
                    (agent_id, limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM activity_logs ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )
            results = []
            for row in cursor.fetchall():
                data = dict(row)
                if data.get('details'):
                    data['details'] = json.loads(data['details'])
                results.append(data)
            return results


# Initialize database on import
if __name__ == "__main__":
    init_database()
    print("Database tables created successfully")
