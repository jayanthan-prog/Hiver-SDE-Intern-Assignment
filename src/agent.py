"""
Main support agent orchestrator.
"""

import json
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from config import Intent
from llm_client import LLMClient
from classifier import IntentClassifier
from reply_generator import ReplyGenerator, ReplyValidator
from escalator import EscalationDecider, EscalationValidator


class SupportAgent:
    """Main orchestrator for the support agent pipeline."""
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self.classifier = IntentClassifier(llm_client)
        self.reply_generator = ReplyGenerator(llm_client)
        self.escalation_decider = EscalationDecider(llm_client)
        
        self.reply_validator = ReplyValidator()
        self.escalation_validator = EscalationValidator()
        
        self.conversation_history = {}  # customer_id -> list of messages
    
    async def process_message(
        self,
        customer_message: str,
        customer_id: str,
        conversation_id: Optional[str] = None
    ) -> Dict:
        """
        Process a single customer message end-to-end.
        
        Returns:
            {
                'timestamp': str (ISO format),
                'message': str,
                'customer_id': str,
                'conversation_id': str,
                'classification': {
                    'intent': str,
                    'confidence': float,
                    'reasoning': str
                },
                'decision': {
                    'should_escalate': bool,
                    'reason': str,
                    'risk_score': float,
                    'signals': List[str]
                },
                'reply': {
                    'text': str,
                    'grounded_in': int  # examples from KB
                } | None,  # None if escalated
                'escalation_response': str | None,  # Only if escalated
                'validation': {
                    'reply_quality': Dict,
                    'escalation_decision': Dict
                }
            }
        """
        
        timestamp = datetime.utcnow().isoformat()
        conversation_id = conversation_id or customer_id
        
        # Get conversation history for this customer
        history = self.conversation_history.get(
            customer_id, 
            []
        )[-10:]  # Last 10 messages
        
        # Step 1: Classify intent
        classification = await self.classifier.classify(customer_message)
        
        # Step 2: Decide on escalation
        escalation_decision = await self.escalation_decider.should_escalate(
            message=customer_message,
            intent=classification['intent'],
            confidence=classification['confidence'],
            conversation_history=history
        )
        
        # Step 3: Generate response (if not escalated)
        reply = None
        escalation_response = None
        reply_validation = None
        
        if escalation_decision['should_escalate']:
            escalation_response = escalation_decision.get('suggested_response')
            escalation_validation = self.escalation_validator.validate_escalation_decision(
                escalation_decision
            )
        else:
            reply = await self.reply_generator.generate_reply(
                customer_message=customer_message,
                intent=classification['intent'],
                conversation_history=history
            )
            reply_validation = self.reply_validator.validate_reply(reply['reply'])
        
        # Step 4: Build result
        result = {
            'timestamp': timestamp,
            'message': customer_message,
            'customer_id': customer_id,
            'conversation_id': conversation_id,
            'classification': {
                'intent': classification['intent'],
                'confidence': classification['confidence'],
                'reasoning': classification['reasoning']
            },
            'decision': {
                'should_escalate': escalation_decision['should_escalate'],
                'reason': escalation_decision['reason'],
                'risk_score': escalation_decision['risk_score'],
                'signals': escalation_decision['signals']
            },
            'reply': reply,
            'escalation_response': escalation_response,
            'validation': {
                'reply_quality': reply_validation,
                'escalation_decision': escalation_validation if escalation_decision['should_escalate'] else None
            }
        }
        
        # Update conversation history
        if customer_id not in self.conversation_history:
            self.conversation_history[customer_id] = []
        self.conversation_history[customer_id].append({
            'text': customer_message,
            'is_customer': True,
            'timestamp': timestamp
        })
        
        return result
    
    async def process_batch(
        self,
        messages: List[Dict],  # [{customer_id, customer_message}, ...]
    ) -> List[Dict]:
        """Process multiple messages."""
        results = []
        for msg in messages:
            result = await self.process_message(
                customer_message=msg['customer_message'],
                customer_id=msg['customer_id'],
                conversation_id=msg.get('conversation_id')
            )
            results.append(result)
        return results
    
    def load_knowledge_base(self, knowledge_data: List[Dict]):
        """
        Load historical resolutions into reply generator.
        
        knowledge_data format:
        [
            {
                'intent': str,
                'customer_message': str,
                'brand_response': str,
                'outcome': 'resolved|escalated'
            },
            ...
        ]
        """
        # Group by intent
        by_intent = {}
        for example in knowledge_data:
            intent = example['intent']
            if intent not in by_intent:
                by_intent[intent] = []
            by_intent[intent].append({
                'customer_message': example['customer_message'],
                'brand_response': example['brand_response'],
                'outcome': example['outcome']
            })
        
        # Load into reply generator
        for intent, examples in by_intent.items():
            self.reply_generator.add_knowledge(intent, examples)
    
    def get_stats(self) -> Dict:
        """Get agent statistics."""
        return {
            'conversations': len(self.conversation_history),
            'total_messages': sum(
                len(msgs) for msgs in self.conversation_history.values()
            )
        }


async def run_agent_example():
    """Example usage of the support agent."""
    from llm_client import get_llm_client
    
    # Initialize with mock LLM for demo
    llm = get_llm_client("mock")
    agent = SupportAgent(llm)
    
    # Add some sample knowledge
    sample_knowledge = [
        {
            'intent': Intent.ORDER_STATUS.value,
            'customer_message': 'Where is my order?',
            'brand_response': 'Thank you for asking! Your order #12345 is on the way and will arrive by tomorrow. Track it here: [link]',
            'outcome': 'resolved'
        },
        {
            'intent': Intent.REFUND.value,
            'customer_message': 'Can I get a refund for my recent order?',
            'brand_response': 'We can help! We offer returns within 30 days. Your order is eligible. Please initiate a return here: [link]',
            'outcome': 'resolved'
        }
    ]
    agent.load_knowledge_base(sample_knowledge)
    
    # Process test messages
    test_messages = [
        {'customer_id': 'user_1', 'customer_message': 'Where is my order? I ordered it 2 weeks ago!'},
        {'customer_id': 'user_2', 'customer_message': 'I want a refund NOW! This product is terrible!!!'},
        {'customer_id': 'user_3', 'customer_message': 'How do I reset my password?'},
    ]
    
    print("Processing messages...")
    results = await agent.process_batch(test_messages)
    
    for result in results:
        print(f"\n{'='*60}")
        print(f"Message: {result['message']}")
        print(f"Intent: {result['classification']['intent']}")
        print(f"Escalate: {result['decision']['should_escalate']}")
        if result['reply']:
            print(f"Reply: {result['reply']['reply']}")
        else:
            print(f"Escalation Response: {result['escalation_response']}")


if __name__ == "__main__":
    asyncio.run(run_agent_example())
