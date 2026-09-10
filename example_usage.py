"""
Example usage and documentation.
"""

import asyncio
import json
from pathlib import Path

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from agent import SupportAgent
from golden_set import GoldenSetBuilder, create_sample_golden_set
from llm_client import get_llm_client
from evaluator import EvaluationHarness


async def example_1_simple_classification():
    """Example 1: Simple message classification."""
    print("=" * 60)
    print("EXAMPLE 1: Intent Classification")
    print("=" * 60)
    
    llm = get_llm_client("mock")
    agent = SupportAgent(llm)
    
    message = "Where is my order? It's been 3 days!"
    result = await agent.process_message(
        customer_message=message,
        customer_id="example_user_1"
    )
    
    print(f"\nMessage: {message}")
    print(f"Predicted Intent: {result['classification']['intent']}")
    print(f"Confidence: {result['classification']['confidence']:.1%}")
    print(f"Should Escalate: {result['decision']['should_escalate']}")


async def example_2_escalation_decision():
    """Example 2: Escalation decision with signals."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Escalation Detection")
    print("=" * 60)
    
    llm = get_llm_client("mock")
    agent = SupportAgent(llm)
    
    angry_message = "THIS IS UNACCEPTABLE!!! WORST SERVICE EVER!!!"
    result = await agent.process_message(
        customer_message=angry_message,
        customer_id="example_user_2"
    )
    
    print(f"\nMessage: {angry_message}")
    print(f"Should Escalate: {result['decision']['should_escalate']}")
    print(f"Risk Score: {result['decision']['risk_score']:.2f}")
    print(f"Escalation Signals: {result['decision']['signals']}")
    print(f"Escalation Response:\n  {result['escalation_response']}")


async def example_3_reply_generation():
    """Example 3: Generate contextual reply."""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Reply Generation")
    print("=" * 60)
    
    llm = get_llm_client("mock")
    agent = SupportAgent(llm)
    
    # Load some knowledge base examples
    knowledge = [
        {
            'intent': 'order_status',
            'customer_message': 'Where is my order?',
            'brand_response': 'Your order is on the way! You can track it at: [tracking link]',
            'outcome': 'resolved'
        }
    ]
    agent.load_knowledge_base(knowledge)
    
    message = "Can you tell me when my package arrives?"
    result = await agent.process_message(
        customer_message=message,
        customer_id="example_user_3"
    )
    
    print(f"\nMessage: {message}")
    print(f"Intent: {result['classification']['intent']}")
    if result['reply']:
        print(f"Generated Reply:\n  {result['reply']['reply']}")
    else:
        print("(Message was escalated, no reply generated)")


async def example_4_batch_processing():
    """Example 4: Process multiple messages."""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Batch Processing")
    print("=" * 60)
    
    llm = get_llm_client("mock")
    agent = SupportAgent(llm)
    
    messages = [
        {'customer_id': 'user_1', 'customer_message': 'Where is my order?'},
        {'customer_id': 'user_2', 'customer_message': 'I want a refund'},
        {'customer_id': 'user_3', 'customer_message': 'This product is amazing!'},
        {'customer_id': 'user_4', 'customer_message': 'I DEMAND TO SPEAK TO A MANAGER!!!'},
    ]
    
    print(f"\nProcessing {len(messages)} messages...\n")
    results = await agent.process_batch(messages)
    
    for result in results:
        print(f"Message: {result['message'][:50]}...")
        print(f"  Intent: {result['classification']['intent']}")
        print(f"  Escalate: {result['decision']['should_escalate']}")
        print()


def example_5_golden_set_creation():
    """Example 5: Create and explore golden set."""
    print("=" * 60)
    print("EXAMPLE 5: Golden Evaluation Set")
    print("=" * 60)
    
    builder = GoldenSetBuilder()
    
    # Create sample set
    examples = create_sample_golden_set()
    builder.add_batch(examples)
    
    print(f"\nGolden set size: {len(builder.examples)}")
    print(f"Distribution: {builder.get_distribution()}")
    print(f"Is balanced: {builder.is_balanced()}")
    
    # Show a few examples
    print("\nSample examples:")
    for ex in builder.examples[:3]:
        print(f"\n[{ex['id']}] {ex['customer_message'][:50]}...")
        print(f"  Intent: {ex['ground_truth']['intent']}")
        print(f"  Escalate: {ex['ground_truth']['should_escalate']}")


if __name__ == "__main__":
    # Run all examples
    print("\nHIVER SUPPORT AGENT - USAGE EXAMPLES\n")
    
    asyncio.run(example_1_simple_classification())
    asyncio.run(example_2_escalation_decision())
    asyncio.run(example_3_reply_generation())
    asyncio.run(example_4_batch_processing())
    example_5_golden_set_creation()
    
    print("\n" + "=" * 60)
    print("Examples completed!")
    print("See src/main.py for full pipeline execution")
    print("=" * 60)
