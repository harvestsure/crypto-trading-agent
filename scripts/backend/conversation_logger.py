"""
Conversation Logger for LLM Interactions
Saves all LLM conversation input/output to separate log files per agent
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List


class ConversationLogger:
    """Logger for saving agent-specific conversation history"""
    
    def __init__(self, agent_id: str, agent_name: str, log_dir: Optional[str] = None):
        """
        Initialize conversation logger for an agent
        
        Args:
            agent_id: Unique agent identifier
            agent_name: Human-readable agent name
            log_dir: Directory to store logs (default: logs/conversations/)
        """
        self.agent_id = agent_id
        self.agent_name = agent_name
        
        # Create logs directory if not specified
        if log_dir is None:
            log_dir = os.path.join(os.path.dirname(__file__), "logs", "conversations")
        
        self.log_dir = log_dir
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        
        # Create agent-specific log file
        self.log_file = os.path.join(self.log_dir, f"{agent_id}_{agent_name}.jsonl")
        
        # Initialize logger
        self.logger = logging.getLogger(f"ConversationLogger.{agent_id}")
    
    def log_message(
        self,
        role: str,
        content: str,
        message_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None,
        tool_calls: Optional[List[Dict]] = None,
    ) -> None:
        """
        Log a single message to the conversation log
        
        Args:
            role: Message role ('user', 'assistant', 'system', 'tool')
            content: Message content
            message_type: Type of message ('text', 'tool_call', 'tool_result')
            metadata: Additional metadata to log
            tool_calls: Tool calls if applicable
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "role": role,
            "message_type": message_type,
            "content": content,
        }
        
        if tool_calls:
            log_entry["tool_calls"] = tool_calls
        
        if metadata:
            log_entry["metadata"] = metadata
        
        # Append to JSONL file
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            self.logger.error(f"Failed to write conversation log: {e}")
    
    def log_user_input(self, user_message: str, metadata: Optional[Dict] = None) -> None:
        """Log user input message"""
        self.log_message(
            role="user",
            content=user_message,
            message_type="text",
            metadata=metadata
        )
    
    def log_assistant_output(
        self,
        content: str,
        tool_calls: Optional[List[Dict]] = None,
        tokens_info: Optional[Dict[str, int]] = None,
        cost_info: Optional[Dict[str, float]] = None,
    ) -> None:
        """
        Log assistant output message
        
        Args:
            content: Assistant response content
            tool_calls: Any tool calls made by the assistant
            tokens_info: Token usage information
            cost_info: Cost information
        """
        metadata = {}
        if tokens_info:
            metadata["tokens"] = tokens_info
        if cost_info:
            metadata["cost"] = cost_info
        
        self.log_message(
            role="assistant",
            content=content,
            message_type="text",
            metadata=metadata if metadata else None,
            tool_calls=tool_calls
        )
    
    def log_tool_call(
        self,
        tool_call_id: str,
        tool_name: str,
        arguments: str,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Log tool call"""
        meta = metadata or {}
        meta["tool_call_id"] = tool_call_id
        meta["tool_name"] = tool_name
        
        self.log_message(
            role="assistant",
            content=arguments,
            message_type="tool_call",
            metadata=meta
        )
    
    def log_tool_result(
        self,
        tool_call_id: str,
        tool_name: str,
        result: str,
        status: str = "success",
    ) -> None:
        """
        Log tool execution result
        
        Args:
            tool_call_id: The tool call ID
            tool_name: Name of the tool executed
            result: The result/output from the tool
            status: Status of execution ('success' or 'error')
        """
        metadata = {
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "status": status,
        }
        
        self.log_message(
            role="tool",
            content=result,
            message_type="tool_result",
            metadata=metadata
        )
    
    def log_system_message(self, content: str, metadata: Optional[Dict] = None) -> None:
        """Log system message"""
        self.log_message(
            role="system",
            content=content,
            message_type="text",
            metadata=metadata
        )
    
    def log_conversation_round(
        self,
        user_message: str,
        assistant_response: str,
        tool_calls: Optional[List[Dict]] = None,
        tokens_info: Optional[Dict[str, int]] = None,
        cost_info: Optional[Dict[str, float]] = None,
    ) -> None:
        """
        Log a complete conversation round (user input + assistant output)
        
        Args:
            user_message: User's input
            assistant_response: Assistant's response
            tool_calls: Any tool calls made
            tokens_info: Token usage
            cost_info: Cost information
        """
        self.log_user_input(user_message)
        self.log_assistant_output(
            content=assistant_response,
            tool_calls=tool_calls,
            tokens_info=tokens_info,
            cost_info=cost_info
        )
    
    def get_conversation_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Read conversation history from log file
        
        Args:
            limit: Maximum number of recent entries to return
            
        Returns:
            List of conversation entries
        """
        if not os.path.exists(self.log_file):
            return []
        
        entries = []
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line))
            
            if limit:
                entries = entries[-limit:]
            
            return entries
        except Exception as e:
            self.logger.error(f"Failed to read conversation history: {e}")
            return []
    
    def export_conversation_summary(self, output_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Export conversation summary as a readable format
        
        Args:
            output_file: Optional file to write summary to
            
        Returns:
            Dictionary with conversation summary
        """
        entries = self.get_conversation_history()
        
        summary = {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "conversation_file": self.log_file,
            "total_messages": len(entries),
            "start_time": entries[0]["timestamp"] if entries else None,
            "end_time": entries[-1]["timestamp"] if entries else None,
            "message_breakdown": {
                "user": sum(1 for e in entries if e["role"] == "user"),
                "assistant": sum(1 for e in entries if e["role"] == "assistant"),
                "tool": sum(1 for e in entries if e["role"] == "tool"),
                "system": sum(1 for e in entries if e["role"] == "system"),
            },
            "messages": entries,
        }
        
        if output_file:
            try:
                output_path = Path(output_file)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(summary, f, ensure_ascii=False, indent=2)
            except Exception as e:
                self.logger.error(f"Failed to export conversation summary: {e}")
        
        return summary
    
    def clear_logs(self) -> None:
        """Clear the conversation log file for this agent"""
        try:
            if os.path.exists(self.log_file):
                os.remove(self.log_file)
                self.logger.info(f"Cleared conversation logs for agent {self.agent_id}")
        except Exception as e:
            self.logger.error(f"Failed to clear conversation logs: {e}")
    
    def get_log_file_path(self) -> str:
        """Get the full path to the conversation log file"""
        return self.log_file
    
    def get_file_size(self) -> int:
        """Get the size of the log file in bytes"""
        try:
            return os.path.getsize(self.log_file)
        except FileNotFoundError:
            return 0


class ConversationLoggerFactory:
    """Factory for creating and managing conversation loggers for multiple agents"""
    
    _loggers: Dict[str, ConversationLogger] = {}
    
    @classmethod
    def get_logger(
        cls,
        agent_id: str,
        agent_name: str,
        log_dir: Optional[str] = None,
    ) -> ConversationLogger:
        """
        Get or create a conversation logger for an agent
        
        Args:
            agent_id: Unique agent identifier
            agent_name: Human-readable agent name
            log_dir: Directory for storing logs
            
        Returns:
            ConversationLogger instance
        """
        if agent_id not in cls._loggers:
            cls._loggers[agent_id] = ConversationLogger(agent_id, agent_name, log_dir)
        
        return cls._loggers[agent_id]
    
    @classmethod
    def remove_logger(cls, agent_id: str) -> None:
        """Remove a logger from the factory"""
        if agent_id in cls._loggers:
            del cls._loggers[agent_id]
    
    @classmethod
    def get_all_loggers(cls) -> Dict[str, ConversationLogger]:
        """Get all active loggers"""
        return cls._loggers.copy()
