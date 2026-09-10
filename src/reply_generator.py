"""
Reply generation module using LLM and historical context.
"""

import json
from typing import Dict, List, Optional
from config import LLM_MODEL, TEMPERATURE_REPLY, MAX_TOKENS_REPLY, Intent
from llm_client import LLMClient


class ReplyGenerator:
    """Generate contextual replies based on resolved similar issues."""
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self.knowledge_base = {}  # intent -> list of resolution examples
        
    def add_knowledge(self, intent: str, resolution_examples: List[Dict]):
        """
        Add historical resolutions for an intent.
        
        resolution_examples format:
        [
            {
                'customer_message': str,
                'brand_response': str,
                'outcome': 'resolved|escalated'
            },
            ...
        ]
        """
        self.knowledge_base[intent] = resolution_examples
    
    def _build_context_prompt(
        self, 
        customer_message: str, 
        intent: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> str:
        """Build prompt with historical context."""
        
        context = ""
        
        # Add similar resolved cases if available
        if intent in self.knowledge_base and self.knowledge_base[intent]:
            examples = self.knowledge_base[intent][:3]  # Use top 3 examples
            context += "SIMILAR RESOLVED CASES:\n"
            for i, ex in enumerate(examples, 1):
                context += f"""
Case {i}:
Customer: {ex['customer_message']}
Brand Response: {ex['brand_response']}
Outcome: {ex['outcome']}
"""
        
        # Add conversation history if available
        if conversation_history:
            context += "\nCONVERSATION HISTORY:\n"
            for msg in conversation_history[-5:]:  # Last 5 messages
                role = "Customer" if msg.get('is_customer') else "Brand"
                context += f"{role}: {msg['text']}\n"
        
        prompt = f"""You are a helpful Amazon customer support agent. Generate a single, concise reply to resolve the customer's issue.

{context}

CUSTOMER'S CURRENT MESSAGE:
"{customer_message}"

ISSUE CATEGORY: {intent}

Generate a helpful, professional response that:
1. Acknowledges the customer's issue
2. Takes responsibility where appropriate
3. Offers a specific solution or next steps
4. Is concise (1-2 sentences max)
5. Ends with a specific action the customer should take or expect

Reply only with the response text, no preamble.
"""
        return prompt
    
    async def generate_reply(
        self,
        customer_message: str,
        intent: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Generate a reply to a customer message.
        
        Returns:
            {
                'reply': str,
                'intent': str,
                'grounded_in': int (number of similar cases used),
                'confidence': float
            }
        """
        prompt = self._build_context_prompt(
            customer_message, 
            intent, 
            conversation_history
        )
        
        response = await self.llm.call(
            prompt=prompt,
            model=LLM_MODEL,
            temperature=TEMPERATURE_REPLY,
            max_tokens=MAX_TOKENS_REPLY,
        )
        
        # Count how many knowledge base examples were used
        grounded_in = len(self.knowledge_base.get(intent, []))
        
        return {
            'reply': response.strip(),
            'intent': intent,
            'grounded_in': grounded_in,
            'confidence': min(0.95, 0.7 + (grounded_in / 10))  # Confidence based on available examples
        }
    
    async def generate_batch_replies(
        self,
        messages: List[str],
        intents: List[str],
    ) -> List[Dict]:
        """Generate replies for multiple messages."""
        results = []
        for msg, intent in zip(messages, intents):
            result = await self.generate_reply(msg, intent)
            results.append(result)
        return results


class ReplyValidator:
    """Validate generated replies for quality."""
    
    @staticmethod
    def validate_reply(reply: str) -> Dict:
        """
        Validate reply quality.
        
        Returns:
            {
                'is_valid': bool,
                'issues': List[str],
                'score': float (0-1)
            }
        """
        issues = []
        score = 1.0
        
        if not reply or len(reply.strip()) == 0:
            issues.append("Empty reply")
            score -= 0.5
        
        if len(reply) > 500:
            issues.append("Reply too long (>500 chars)")
            score -= 0.3
        
        if len(reply) < 10:
            issues.append("Reply too short (<10 chars)")
            score -= 0.3
        
        # Check for generic non-answers
        generic_phrases = ["i don't know", "not sure", "unclear", "can't help"]
        if any(phrase in reply.lower() for phrase in generic_phrases):
            issues.append("Reply seems unhelpful")
            score -= 0.2
        
        # Check for placeholders that weren't filled
        if "{" in reply or "[REDACTED]" in reply:
            issues.append("Unfilled placeholders")
            score -= 0.3
        
        return {
            'is_valid': score >= 0.5,
            'issues': issues,
            'score': max(0, score)
        }
