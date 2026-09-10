"""
Baseline implementations for comparison.
"""

from typing import List, Dict
from config import Intent


class TrivialBaseline:
    """
    Trivial baseline: classify everything as general_inquiry, never escalate.
    
    Expected performance: ~20% accuracy (only hits general_inquiry correct)
    This establishes the floor for "not intelligent."
    """
    
    def classify(self, message: str) -> Dict:
        """Always return general_inquiry."""
        return {
            'intent': Intent.GENERAL_INQUIRY.value,
            'confidence': 0.1,
            'reasoning': 'Trivial baseline - no intent understanding'
        }
    
    def decide_escalation(self, message: str) -> Dict:
        """Never escalate."""
        return {
            'should_escalate': False,
            'reason': 'Trivial baseline - all messages auto-handled',
            'risk_score': 0.0,
            'signals': []
        }
    
    def generate_reply(self, message: str, intent: str) -> str:
        """Generic reply regardless of message."""
        return "Thank you for contacting us. We appreciate your feedback."


class RuleBasedBaseline:
    """
    Simple baseline: rule-based classification using keywords and heuristics.
    
    Expected performance: ~60-70% overall
    - Keyword matching for common intents
    - Escalation if angry/frustrated language detected
    - Generic replies
    
    This shows what domain knowledge + simple rules achieve.
    """
    
    # Intent keyword mappings
    INTENT_KEYWORDS = {
        Intent.ORDER_STATUS.value: ['order', 'status', 'tracking', 'when', 'where', 'deliver'],
        Intent.REFUND.value: ['refund', 'money back', 'return money', 'refund status'],
        Intent.DELIVERY_ISSUE.value: ['late', 'damaged', 'missing', 'broken', 'arrived', 'delivery'],
        Intent.PRODUCT_QUALITY.value: ['quality', 'broken', 'defect', 'wrong', 'bad', 'poor'],
        Intent.ACCOUNT_ISSUE.value: ['account', 'login', 'password', 'reset', 'access', 'hack'],
        Intent.PAYMENT_ISSUE.value: ['charge', 'payment', 'billing', 'card', 'money', 'fee'],
        Intent.RETURN.value: ['return', 'send back', 'return process'],
        Intent.GENERAL_INQUIRY.value: ['how', 'where', 'what', 'do you', 'shipping', 'policy'],
        Intent.COMPLIMENT.value: ['thank', 'great', 'excellent', 'love', 'best', 'awesome'],
    }
    
    ESCALATION_KEYWORDS = [
        'unacceptable', 'terrible', 'awful', 'worst', 'disgusting',
        'scam', 'fraud', 'lawyer', 'sue', 'demand',
        'never', 'furious', 'angry', 'upset', 'frustrated'
    ]
    
    @classmethod
    def classify(cls, message: str) -> Dict:
        """Keyword-based intent classification."""
        message_lower = message.lower()
        
        scores = {}
        for intent, keywords in cls.INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in message_lower)
            scores[intent] = score
        
        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]
        confidence = min(0.95, 0.5 + (best_score * 0.1))
        
        return {
            'intent': best_intent,
            'confidence': confidence,
            'reasoning': f'Matched {best_score} keywords'
        }
    
    @classmethod
    def decide_escalation(cls, message: str) -> Dict:
        """Rule-based escalation detection."""
        message_lower = message.lower()
        
        signals = []
        risk = 0.0
        
        # Check for anger/frustration keywords
        anger_count = sum(1 for kw in cls.ESCALATION_KEYWORDS if kw in message_lower)
        if anger_count > 0:
            signals.append(f"anger_{anger_count}")
            risk += 0.4
        
        # Check for repeated contact (!!!, ???)
        if '!!!' in message or '???' in message:
            signals.append("repeated_punctuation")
            risk += 0.2
        
        # Check for ALL CAPS
        if message.isupper() and len(message) > 10:
            signals.append("all_caps")
            risk += 0.2
        
        should_escalate = risk >= 0.5
        
        return {
            'should_escalate': should_escalate,
            'reason': f'Risk score: {risk:.2f}',
            'risk_score': risk,
            'signals': signals
        }
    
    @classmethod
    def generate_reply(cls, message: str, intent: str) -> str:
        """Generate generic but relevant reply."""
        replies = {
            Intent.ORDER_STATUS.value: 'Thank you for your patience. Please provide your order number and we\'ll check the status for you.',
            Intent.REFUND.value: 'We can help with refunds. Our standard return window is 30 days. Please let us know the order number.',
            Intent.DELIVERY_ISSUE.value: 'We\'re sorry for the delivery issue. Please provide your order number so we can investigate.',
            Intent.PRODUCT_QUALITY.value: 'We apologize for the quality issue. We\'ll make this right - please provide order details.',
            Intent.ACCOUNT_ISSUE.value: 'For account issues, please use our password reset tool or contact support with your account email.',
            Intent.PAYMENT_ISSUE.value: 'Let\'s resolve this payment issue. Please provide your order number for investigation.',
            Intent.RETURN.value: 'To return an item, please visit our returns center with your order number.',
            Intent.GENERAL_INQUIRY.value: 'Thank you for your question. That\'s a great question!',
            Intent.COMPLIMENT.value: 'Thank you so much for the kind words! We appreciate your business.',
        }
        return replies.get(intent, 'Thank you for contacting us.')


class BaselineEvaluator:
    """Helper to evaluate baselines."""
    
    @staticmethod
    async def evaluate_baseline(
        baseline,
        test_messages: List[Dict],  # [{message, intent, should_escalate}, ...]
        harness  # EvaluationHarness instance
    ) -> Dict:
        """
        Evaluate a baseline on classification and escalation.
        
        Returns evaluation metrics.
        """
        predictions_classify = []
        predictions_escalate = []
        ground_truth = []
        
        for item in test_messages:
            message = item['customer_message']
            
            # Classify
            pred = baseline.classify(message)
            predictions_classify.append({
                'message': message,
                'predicted_intent': pred['intent']
            })
            
            # Escalate
            esc = baseline.decide_escalation(message)
            predictions_escalate.append({
                'message': message,
                'predicted_escalate': esc['should_escalate']
            })
            
            ground_truth.append({
                'intent': item['intent'],
                'should_escalate': item.get('should_escalate', False)
            })
        
        # Evaluate
        classify_metrics = await harness.evaluate_classification(
            predictions_classify,
            [{'intent': g['intent']} for g in ground_truth]
        )
        
        escalate_metrics = await harness.evaluate_escalation(
            predictions_escalate,
            ground_truth
        )
        
        return {
            'classification': {
                'accuracy': classify_metrics.accuracy,
                'precision': classify_metrics.precision,
                'recall': classify_metrics.recall,
                'f1': classify_metrics.f1,
                'per_class': classify_metrics.per_class_metrics
            },
            'escalation': escalate_metrics
        }
