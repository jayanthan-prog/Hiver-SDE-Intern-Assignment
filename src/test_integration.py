"""
Integration tests for the support agent.
"""

import asyncio
import pytest
from config import Intent
from llm_client import MockLLMClient
from agent import SupportAgent
from golden_set import GoldenSetBuilder


@pytest.mark.asyncio
async def test_end_to_end_processing():
    """Test full pipeline on a single message."""
    
    llm = MockLLMClient()
    agent = SupportAgent(llm)
    
    result = await agent.process_message(
        customer_message="Where's my order? I ordered it 2 weeks ago!",
        customer_id="user_1"
    )
    
    # Validate structure
    assert 'timestamp' in result
    assert 'classification' in result
    assert 'decision' in result
    assert 'reply' in result or 'escalation_response' in result
    
    # Check classification
    assert result['classification']['intent'] in [i.value for i in Intent]
    assert 0 <= result['classification']['confidence'] <= 1
    
    # Check escalation decision
    assert isinstance(result['decision']['should_escalate'], bool)
    assert 'reason' in result['decision']
    assert 0 <= result['decision']['risk_score'] <= 1


@pytest.mark.asyncio
async def test_batch_processing():
    """Test batch processing."""
    
    llm = MockLLMClient()
    agent = SupportAgent(llm)
    
    messages = [
        {'customer_id': 'user_1', 'customer_message': 'Where is my order?'},
        {'customer_id': 'user_2', 'customer_message': 'Can I get a refund?'},
        {'customer_id': 'user_3', 'customer_message': 'Product is broken'},
    ]
    
    results = await agent.process_batch(messages)
    
    assert len(results) == 3
    assert all('classification' in r for r in results)
    assert all('decision' in r for r in results)


def test_golden_set_balancing():
    """Test golden set is balanced across intents."""
    
    builder = GoldenSetBuilder()
    
    # Add examples for each intent
    for intent in Intent:
        for i in range(15):
            builder.add_example(
                customer_message=f"Test message {i} for {intent.value}",
                intent=intent.value,
                should_escalate=False
            )
    
    assert builder.is_balanced()
    dist = builder.get_distribution()
    assert all(count >= 15 for count in dist.values())


def test_mock_llm_client():
    """Test mock LLM works without API keys."""
    
    llm = MockLLMClient()
    
    # Should work without raising errors
    async def test():
        result = await llm.call(
            prompt="classify this",
            model="mock",
            temperature=0.5,
            max_tokens=100
        )
        assert isinstance(result, str)
        assert len(result) > 0
    
    asyncio.run(test())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
