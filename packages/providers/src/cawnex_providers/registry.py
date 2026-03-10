"""Provider registry — resolves provider enum to concrete LLMProvider."""

from __future__ import annotations

from cryptography.fernet import Fernet

from cawnex_providers.base import LLMProvider
from cawnex_providers.anthropic import AnthropicProvider


class ProviderRegistry:
    """Factory for LLM providers. Decrypts API keys and returns the right provider."""

    _PROVIDERS = {
        "anthropic": AnthropicProvider,
    }

    @classmethod
    def get(cls, provider: str, api_key: str) -> LLMProvider:
        """Get a provider instance with a plain-text API key."""
        provider_cls = cls._PROVIDERS.get(provider)
        if not provider_cls:
            raise ValueError(f"Unknown provider: {provider}. Available: {list(cls._PROVIDERS)}")
        return provider_cls(api_key=api_key)

    @classmethod
    def get_from_encrypted(
        cls, provider: str, encrypted_key: bytes, fernet_key: bytes
    ) -> LLMProvider:
        """Get a provider instance, decrypting the stored API key."""
        fernet = Fernet(fernet_key)
        api_key = fernet.decrypt(encrypted_key).decode()
        return cls.get(provider, api_key)

    @classmethod
    def available_providers(cls) -> list[str]:
        return list(cls._PROVIDERS.keys())


def get_provider(provider: str, api_key: str) -> LLMProvider:
    """Convenience function."""
    return ProviderRegistry.get(provider, api_key)
