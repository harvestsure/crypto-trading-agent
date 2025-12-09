"""
Prompt Caching Management
Support for LLM prompt caching to reduce costs and improve performance
Supports OpenAI, Anthropic, DeepSeek, and other providers
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import hashlib
import json


class CacheProvider(str, Enum):
    """Cache providers supported"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"


@dataclass
class CacheConfig:
    """Configuration for prompt caching"""
    enabled: bool = True
    provider: str = "openai"
    cache_control_type: str = "ephemeral"  # or "session" for persistent cache
    ttl_seconds: int = 300  # Time to live for cache (5 minutes default)
    min_cache_size: int = 1024  # Minimum token size to cache (1K tokens)


class PromptCacheManager:
    """Manages prompt caching for LLM requests"""
    
    def __init__(self, config: Optional[CacheConfig] = None):
        """
        Initialize cache manager
        
        Args:
            config: Cache configuration
        """
        self.config = config or CacheConfig()
        self.cache_stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "tokens_saved": 0,
            "cost_saved": 0.0,
        }
    
    def is_cache_enabled(self) -> bool:
        """Check if caching is enabled"""
        return self.config.enabled
    
    def get_cache_hash(self, content: str) -> str:
        """
        Get hash of content for cache identification
        
        Args:
            content: Content to hash
            
        Returns:
            SHA256 hash of content
        """
        return hashlib.sha256(content.encode()).hexdigest()
    
    def prepare_cached_message(
        self,
        content: str,
        role: str = "system",
        is_cache_point: bool = True,
    ) -> Dict[str, Any]:
        """
        Prepare a message with cache control headers
        
        Args:
            content: Message content
            role: Message role (system, user, assistant)
            is_cache_point: Whether to mark this as a cache point
            
        Returns:
            Message dict with cache control
        """
        if not self.config.enabled or not is_cache_point:
            return {
                "role": role,
                "content": content,
            }
        
        message = {
            "role": role,
            "content": content,
        }
        
        # Add cache control header based on provider
        if self.config.provider in [CacheProvider.OPENAI.value, CacheProvider.GEMINI.value]:
            message["cache_control"] = {"type": self.config.cache_control_type}
        elif self.config.provider == CacheProvider.ANTHROPIC.value:
            message["cache_control"] = {"type": self.config.cache_control_type}
        elif self.config.provider == CacheProvider.DEEPSEEK.value:
            message["cache_control"] = {"type": "ephemeral"}
        
        return message
    
    def build_cached_messages(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        cache_system_prompt: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Build messages list with cache control
        
        Args:
            system_prompt: System prompt to potentially cache
            messages: List of conversation messages
            cache_system_prompt: Whether to cache the system prompt
            
        Returns:
            Messages list ready for API call
        """
        if not self.config.enabled:
            cached_messages = []
            if system_prompt:
                cached_messages.append({"role": "system", "content": system_prompt})
            cached_messages.extend(messages)
            return cached_messages
        
        cached_messages = []
        
        # Add system prompt with cache control
        if system_prompt:
            cached_messages.append(
                self.prepare_cached_message(
                    system_prompt,
                    role="system",
                    is_cache_point=cache_system_prompt
                )
            )
        
        # Add regular messages (typically don't cache recent messages)
        for msg in messages:
            cached_messages.append({
                "role": msg.get("role"),
                "content": msg.get("content"),
            })
        
        return cached_messages
    
    def parse_cache_usage(
        self,
        response: Any,
        input_cost_per_1k: float = 0.003,
        cache_read_cost_per_1k: float = 0.0003,
    ) -> Dict[str, Any]:
        """
        Parse cache usage from API response
        
        Args:
            response: API response object
            input_cost_per_1k: Cost per 1K input tokens
            cache_read_cost_per_1k: Cost per 1K cached tokens read
            
        Returns:
            Cache usage statistics
        """
        usage = {
            "input_tokens": 0,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cache_hit": False,
            "cost_saved": 0.0,
        }
        
        if not hasattr(response, "usage"):
            return usage
        
        resp_usage = response.usage
        
        # Different providers expose cache stats differently
        if hasattr(resp_usage, "prompt_tokens"):
            usage["input_tokens"] = resp_usage.prompt_tokens
        
        if hasattr(resp_usage, "cache_creation_input_tokens"):
            # OpenAI format
            usage["cache_creation_tokens"] = resp_usage.cache_creation_input_tokens
        
        if hasattr(resp_usage, "cache_read_input_tokens"):
            # OpenAI format
            usage["cache_read_tokens"] = resp_usage.cache_read_input_tokens
            usage["cache_hit"] = usage["cache_read_tokens"] > 0
        
        if hasattr(resp_usage, "completion_tokens"):
            usage["output_tokens"] = resp_usage.completion_tokens
        
        usage["total_tokens"] = (
            usage["input_tokens"] +
            usage["cache_creation_tokens"] +
            usage["cache_read_tokens"] +
            usage["output_tokens"]
        )
        
        # Calculate cost savings
        if usage["cache_read_tokens"] > 0:
            regular_cost = (usage["cache_read_tokens"] / 1000) * input_cost_per_1k
            cached_cost = (usage["cache_read_tokens"] / 1000) * cache_read_cost_per_1k
            usage["cost_saved"] = round(regular_cost - cached_cost, 6)
            self.cache_stats["cache_hits"] += 1
            self.cache_stats["tokens_saved"] += usage["cache_read_tokens"]
            self.cache_stats["cost_saved"] += usage["cost_saved"]
        else:
            self.cache_stats["cache_misses"] += 1
        
        self.cache_stats["total_requests"] += 1
        
        return usage
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        hit_rate = 0.0
        if self.cache_stats["total_requests"] > 0:
            hit_rate = (
                self.cache_stats["cache_hits"] /
                self.cache_stats["total_requests"] * 100
            )
        
        return {
            **self.cache_stats,
            "hit_rate_percent": round(hit_rate, 2),
            "average_tokens_saved_per_hit": (
                self.cache_stats["tokens_saved"] // max(1, self.cache_stats["cache_hits"])
                if self.cache_stats["cache_hits"] > 0 else 0
            ),
        }
    
    def reset_stats(self) -> None:
        """Reset cache statistics"""
        self.cache_stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "tokens_saved": 0,
            "cost_saved": 0.0,
        }
    
    def update_config(self, **kwargs) -> None:
        """
        Update cache configuration
        
        Args:
            enabled: Whether caching is enabled
            provider: Cache provider type
            cache_control_type: Cache control type (ephemeral or session)
            ttl_seconds: Time to live for cache
            min_cache_size: Minimum tokens to cache
        """
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
    
    def get_config(self) -> Dict[str, Any]:
        """Get current cache configuration"""
        return {
            "enabled": self.config.enabled,
            "provider": self.config.provider,
            "cache_control_type": self.config.cache_control_type,
            "ttl_seconds": self.config.ttl_seconds,
            "min_cache_size": self.config.min_cache_size,
        }
