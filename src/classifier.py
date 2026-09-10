"""
Intent classification module using LLM.
"""

import json
from typing import Dict, List, Tuple, Optional
from functools import lru_cache
from config import (
    Intent, INTENT_DESCRIPTIONS, LLM_MODEL, TEMPERATURE_CLASSIFY, 
    MAX_TOKENS_CLASSIFY, ESCALATION_KEYWORDS
)
from llm_client import LLMClient


class IntentClassifier:
    """Classify customer messages into predefined intents."""
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self.intents = [i.value for i in Intent]
        self.intent_descriptions = INTENT_DESCRIPTIONS
        
    def _build_prompt(self, message: str) -> str:
        """Build classification prompt with intent descriptions."""
        intents_text = "\n".join([
            f"- {intent}: {self.intent_descriptions[Intent(intent)]}"
            for intent in self.intents
        ])
        
        prompt = f"""You are an expert customer support analyst. Classify the following customer message into ONE of these intents:

{intents_text}

CUSTOMER MESSAGE:
"{message}"

Respond in JSON format ONLY with no markdown:
{{"intent": "intent_name", "confidence": 0.95, "reasoning": "brief reason"}}

Valid intents: {', '.join(self.intents)}
"""
        return prompt
    
    async def classify(self, message: str) -> Dict:
        """
        Classify a single message.
        
        Returns:
            {
                'intent': str,
                'confidence': float (0-1),
                'reasoning': str,
                'raw_response': str
            }
        """
        prompt = self._build_prompt(message)
        
        response = await self.llm.call(
            prompt=prompt,
            model=LLM_MODEL,
            temperature=TEMPERATURE_CLASSIFY,
            max_tokens=MAX_TOKENS_CLASSIFY,
        )
        
        try:
            # Extract JSON from response
            result = json.loads(response)
            
            # Validate intent exists
            if result.get('intent') not in self.intents:
                result['intent'] = self.intents[0]  # Fallback
                
            return {
                'intent': result.get('intent', Intent.GENERAL_INQUIRY.value),
                'confidence': float(result.get('confidence', 0.5)),
                'reasoning': result.get('reasoning', ''),
                'raw_response': response
            }
        except json.JSONDecodeError:
            print(f"⚠ Failed to parse response: {response}")
            return {
                'intent': Intent.GENERAL_INQUIRY.value,
                'confidence': 0.3,
                'reasoning': 'Parse error',
                'raw_response': response
            }
    
    async def classify_batch(self, messages: List[str]) -> List[Dict]:
        """Classify multiple messages."""
        results = []
        for msg in messages:
            result = await self.classify(msg)
            results.append(result)
        return results
    
    @staticmethod
    def detect_escalation_signals(message: str) -> Tuple[bool, List[str]]:
        """
        Detect escalation signals in message text.
        
        Returns:
            (should_escalate: bool, signals: List[str])
        """
        message_lower = message.lower()
        signals = []
        
        for keyword in ESCALATION_KEYWORDS:
            if keyword in message_lower:
                signals.append(keyword)
        
        return len(signals) > 0, signals


class IntentExplainer:
    """Explain classification decisions for debugging."""
    
    @staticmethod
    def explain_classification(message: str, result: Dict[str, any]) -> str:
        """Generate human-readable explanation."""
        explanation = f"""
Classification Result
---
Intent: {result['intent'].upper()}
Confidence: {result['confidence']:.1%}
Reasoning: {result['reasoning']}

Message: "{message}"
"""
        return explanation.strip()
