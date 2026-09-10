"""
Escalation decision engine - determine if message should be auto-handled or escalated.
"""

import json
from typing import Dict, Tuple, Optional, List
from config import (
    Intent, ESCALATION_KEYWORDS, ESCALATION_THRESHOLDS,
    LLM_MODEL, TEMPERATURE_CLASSIFY, MAX_TOKENS_CLASSIFY
)
from llm_client import LLMClient
from classifier import IntentClassifier


class EscalationDecider:
    """Decide whether to handle automatically or escalate to human."""
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self.classifier = IntentClassifier(llm_client)
        
    async def should_escalate(
        self,
        message: str,
        intent: str,
        confidence: float,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Determine if message should be escalated.
        
        Returns:
            {
                'should_escalate': bool,
                'reason': str,
                'risk_score': float (0-1),  # How risky to auto-handle
                'suggested_response': str,  # If escalating
                'signals': List[str]
            }
        """
        signals = []
        risk_score = 0.0
        
        # 1. Check rule-based escalation signals
        has_escalation_keywords, keywords = IntentClassifier.detect_escalation_signals(message)
        if has_escalation_keywords:
            signals.extend(keywords)
            risk_score += 0.3
        
        # 2. Check if intent requires escalation
        if intent in [Intent.ESCALATION.value]:
            signals.append("explicit_escalation_intent")
            risk_score += 0.4
        
        # 3. Check if we have low confidence
        if confidence < 0.6:
            signals.append(f"low_confidence_{confidence:.2f}")
            risk_score += 0.2
        
        # 4. Check conversation history for repeated issues
        if conversation_history and len(conversation_history) >= ESCALATION_THRESHOLDS["max_retries"]:
            signals.append("repeated_contact")
            risk_score += 0.3
        
        # 5. Use LLM for nuanced sentiment analysis
        sentiment_risk = await self._assess_sentiment_risk(message)
        if sentiment_risk > ESCALATION_THRESHOLDS["sentiment_threshold"]:
            signals.append(f"negative_sentiment_{sentiment_risk:.2f}")
            risk_score += 0.2
        
        # 6. Check if intent typically needs human verification
        if self._intent_requires_verification(intent):
            signals.append("requires_order_verification")
            risk_score += 0.15
        
        # Decision threshold
        should_escalate = risk_score >= 0.5
        
        reason = self._generate_reason(should_escalate, signals, risk_score)
        suggested_response = await self._generate_escalation_response(
            message, intent, signals
        ) if should_escalate else None
        
        return {
            'should_escalate': should_escalate,
            'reason': reason,
            'risk_score': min(1.0, risk_score),
            'suggested_response': suggested_response,
            'signals': signals
        }
    
    async def _assess_sentiment_risk(self, message: str) -> float:
        """Use LLM to assess message sentiment (-1 to 1, with -1 being most negative)."""
        prompt = f"""Analyze the sentiment of this customer message on a scale from -1 (very angry/negative) to 1 (very happy/positive).

Message: "{message}"

Respond in JSON format:
{{"sentiment_score": -0.5, "reasoning": "brief reason"}}

Only return the JSON, no markdown.
"""
        try:
            response = await self.llm.call(
                prompt=prompt,
                model=LLM_MODEL,
                temperature=TEMPERATURE_CLASSIFY,
                max_tokens=MAX_TOKENS_CLASSIFY,
            )
            result = json.loads(response)
            return float(result.get('sentiment_score', 0))
        except:
            return 0.0  # Neutral if parse fails
    
    async def _generate_escalation_response(
        self,
        message: str,
        intent: str,
        signals: List[str]
    ) -> str:
        """Generate a holding/escalation response."""
        prompt = f"""Generate a brief, empathetic holding response that:
1. Acknowledges the customer's frustration
2. Explains we're escalating to a specialist
3. Sets expectations for follow-up time (1-2 hours)
4. Maintains the customer's trust

Customer message: "{message}"
Issue: {intent}
Concerns: {', '.join(signals[:3])}

Respond with ONLY the message text, no preamble.
Keep it under 100 words.
"""
        try:
            response = await self.llm.call(
                prompt=prompt,
                model=LLM_MODEL,
                temperature=0.7,
                max_tokens=150,
            )
            return response.strip()
        except:
            return "Thank you for your message. We're escalating this to our specialist team who will follow up with you within 2 hours."
    
    @staticmethod
    def _intent_requires_verification(intent: str) -> bool:
        """Check if intent typically requires human verification."""
        verification_intents = [
            Intent.REFUND.value,
            Intent.RETURN.value,
            Intent.PAYMENT_ISSUE.value,
            Intent.ACCOUNT_ISSUE.value,
        ]
        return intent in verification_intents
    
    @staticmethod
    def _generate_reason(should_escalate: bool, signals: List[str], risk_score: float) -> str:
        """Generate human-readable reason for escalation decision."""
        if not should_escalate:
            return "Low risk - can be auto-handled with generated reply."
        
        reasons = []
        if len(signals) > 0:
            reasons.append(f"Detected concerns: {', '.join(signals[:3])}")
        reasons.append(f"Risk level: {risk_score:.1%}")
        
        return "; ".join(reasons)


class EscalationValidator:
    """Validate escalation decisions."""
    
    @staticmethod
    def validate_escalation_decision(decision: Dict) -> Dict:
        """
        Validate escalation decision quality.
        
        Returns:
            {
                'is_valid': bool,
                'issues': List[str],
                'score': float (0-1)
            }
        """
        issues = []
        score = 1.0
        
        if not isinstance(decision.get('should_escalate'), bool):
            issues.append("Missing or invalid should_escalate")
            score -= 0.3
        
        if not decision.get('reason'):
            issues.append("Missing reason")
            score -= 0.2
        
        if not isinstance(decision.get('risk_score'), (int, float)):
            issues.append("Missing or invalid risk_score")
            score -= 0.2
        
        risk = decision.get('risk_score', 0)
        if decision['should_escalate'] and risk < 0.5:
            issues.append("Risk score doesn't match escalation decision")
            score -= 0.2
        
        if decision['should_escalate'] and not decision.get('suggested_response'):
            issues.append("Escalation without suggested response")
            score -= 0.1
        
        return {
            'is_valid': score >= 0.7,
            'issues': issues,
            'score': max(0, score)
        }
