"""
LLM client abstraction layer supporting multiple providers.
"""

import os
import asyncio
from typing import Optional
from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Abstract LLM client interface."""
    
    @abstractmethod
    async def call(self, prompt: str, model: str, temperature: float, max_tokens: int) -> str:
        """Call LLM and return response text."""
        pass


class OpenAIClient(LLMClient):
    """OpenAI API client."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")
        
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("openai library not installed")
    
    async def call(self, prompt: str, model: str = "gpt-4", 
                  temperature: float = 0.7, max_tokens: int = 500) -> str:
        """Call OpenAI API."""
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"✗ OpenAI API error: {e}")
            raise


class AnthropicClient(LLMClient):
    """Anthropic Claude API client."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic library not installed")
    
    async def call(self, prompt: str, model: str = "claude-3-sonnet-20240229",
                  temperature: float = 0.7, max_tokens: int = 500) -> str:
        """Call Anthropic API."""
        try:
            message = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except Exception as e:
            print(f"✗ Anthropic API error: {e}")
            raise


class MockLLMClient(LLMClient):
    """Mock LLM for testing without API calls."""
    
    def __init__(self):
        self.call_count = 0
    
    async def call(self, prompt: str, model: str = "mock", 
                  temperature: float = 0.7, max_tokens: int = 500) -> str:
        """Return mock response."""
        self.call_count += 1
        
        if "intent" in prompt.lower() and "order" in prompt.lower():
            return '{"intent": "order_status", "confidence": 0.95, "reasoning": "Clear order inquiry"}'
        elif "refund" in prompt.lower():
            return '{"intent": "refund", "confidence": 0.9, "reasoning": "Refund request"}'
        else:
            return '{"intent": "general_inquiry", "confidence": 0.7, "reasoning": "Generic inquiry"}'


def get_llm_client(provider: str = "openai", api_key: Optional[str] = None) -> LLMClient:
    """Factory function to get appropriate LLM client."""
    if provider.lower() == "openai":
        return OpenAIClient(api_key)
    elif provider.lower() == "anthropic":
        return AnthropicClient(api_key)
    elif provider.lower() == "mock":
        return MockLLMClient()
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
