"""Provider registry — resolves provider enum to concrete LLMProvider."""

from __future__ import annotations

from cryptography.fernet import Fernet

from cawnex_providers.base import LLMProvider
from cawnex_providers.anthropic import AnthropicProvider
from cawnex_providers.subscription import SubscriptionProvider


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
    def get_subscription(cls, model: str = "claude-sonnet-4-6") -> LLMProvider:
        """Get a subscription provider (Claude Max via CLI). No API key needed."""
        return SubscriptionProvider(model=model)

    @classmethod
    def get_from_encrypted(
        cls, provider: str, encrypted_key: bytes, fernet_key: bytes
    ) -> LLMProvider:
        """Get a provider instance, decrypting the stored API key."""
        fernet = Fernet(fernet_key)
        api_key = fernet.decrypt(encrypted_key).decode()
        return cls.get(provider, api_key)

    @classmethod
    def get_for_tenant(
        cls,
        *,
        mode: str,
        provider: str = "anthropic",
        encrypted_key: bytes | None = None,
        fernet_key: bytes | None = None,
    ) -> LLMProvider:
        """Smart resolver — picks the right provider based on tenant's config mode."""
        if mode == "subscription_relay" or mode == "subscription":
            return cls.get_subscription()
        elif mode == "api_key":
            if not encrypted_key or not fernet_key:
                raise ValueError("API key mode requires encrypted_key and fernet_key")
            return cls.get_from_encrypted(provider, encrypted_key, fernet_key)
        else:
            raise ValueError(f"Unknown LLM mode: {mode}")

    @classmethod
    def available_providers(cls) -> list[str]:
        return list(cls._PROVIDERS.keys()) + ["subscription"]


def get_provider(provider: str, api_key: str) -> LLMProvider:
    """Convenience function."""
    return ProviderRegistry.get(provider, api_key)
