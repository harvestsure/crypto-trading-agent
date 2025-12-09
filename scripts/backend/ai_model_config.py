"""
AI Model Configuration Management
Handles default URLs and configuration for different LLM providers
"""

from typing import Optional
from enum import Enum


class AIProvider(str, Enum):
    """Supported AI providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    CUSTOM = "custom"


# Default base URLs for each provider
PROVIDER_BASE_URLS: dict[str, str] = {
    AIProvider.OPENAI: "https://api.openai.com/v1",
    AIProvider.DEEPSEEK: "https://api.deepseek.com",
    AIProvider.ANTHROPIC: "https://api.anthropic.com",
}


def get_default_base_url(provider: str) -> Optional[str]:
    """
    Get default base URL for a provider if not custom.
    
    Args:
        provider: The provider name (openai, deepseek, anthropic, custom, etc.)
        
    Returns:
        Default base URL for the provider, or None if not applicable
    """
    provider_lower = provider.lower()
    
    # Custom providers don't have defaults
    if provider_lower == AIProvider.CUSTOM:
        return None
    
    return PROVIDER_BASE_URLS.get(provider_lower)


def get_or_set_base_url(provider: str, base_url: Optional[str]) -> Optional[str]:
    """
    Get the base URL, using provided value or default for the provider.
    
    Args:
        provider: The provider name
        base_url: User-provided base URL (if any)
        
    Returns:
        The base URL to use (user-provided, default, or None)
    """
    if base_url:
        return base_url
    return get_default_base_url(provider)


def is_valid_provider(provider: str) -> bool:
    """Check if the provider is valid"""
    valid_providers = [p.value for p in AIProvider]
    return provider.lower() in valid_providers
