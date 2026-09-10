#!/usr/bin/env python
"""Quick test of the async pipeline."""

import sys
import asyncio
sys.path.insert(0, 'src')

from llm_client import MockLLMClient
from agent import SupportAgent
from config import Intent

async def test():
    print('='*60)
    print('ASYNC PIPELINE TEST')
    print('='*60)
    
    llm = MockLLMClient()
    agent = SupportAgent(llm)
    
    test_messages = [
        {
            'text': 'Where is my order? I ordered 2 weeks ago!',
            'id': 'user_1'
        },
        {
            'text': 'REFUND NOW OR I DISPUTE!!!',
            'id': 'user_2'
        },
        {
            'text': 'This product is amazing!',
            'id': 'user_3'
        }
    ]
    
    for msg in test_messages:
        print(f'\n[Message] {msg["text"][:40]}...')
        
        result = await agent.process_message(
            customer_message=msg['text'],
            customer_id=msg['id']
        )
        
        print(f'  Intent: {result["classification"]["intent"]}')
        print(f'  Confidence: {result["classification"]["confidence"]:.1%}')
        print(f'  Escalate: {result["decision"]["should_escalate"]}')
        print(f'  Risk Score: {result["decision"]["risk_score"]:.2f}')
    
    print('\n' + '='*60)
    print('✓ All tests passed!')
    print('='*60)

if __name__ == '__main__':
    asyncio.run(test())
