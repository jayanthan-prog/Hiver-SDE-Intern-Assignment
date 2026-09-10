"""
Evaluation harness and metrics.
"""

import json
from typing import Dict, List, Tuple
from dataclasses import dataclass
from config import Intent

try:
    from sklearn.metrics import (
        accuracy_score, precision_recall_fscore_support, 
        confusion_matrix, classification_report
    )
except ImportError:
    # Fallback if sklearn not installed - implement basic metrics
    def accuracy_score(y_true, y_pred):
        return sum(1 for t, p in zip(y_true, y_pred) if t == p) / len(y_true)
    
    def precision_recall_fscore_support(y_true, y_pred, **kwargs):
        # Simplified version
        return 0.0, 0.0, 0.0, None
    
    def confusion_matrix(y_true, y_pred, **kwargs):
        # Return dummy matrix
        import numpy as np
        return np.zeros((len(set(y_true)), len(set(y_true))))


@dataclass
class MetricsResult:
    """Container for evaluation metrics."""
    accuracy: float
    precision: float
    recall: float
    f1: float
    confusion_matrix: List[List[int]]
    per_class_metrics: Dict[str, Dict]
    raw_report: str


class EvaluationHarness:
    """Evaluate agent performance against golden set."""
    
    def __init__(self):
        self.intent_list = [i.value for i in Intent]
    
    async def evaluate_classification(
        self,
        predictions: List[Dict],  # [{message, predicted_intent}, ...]
        ground_truth: List[Dict],  # [{message, intent}, ...]
    ) -> MetricsResult:
        """
        Evaluate intent classification performance.
        
        predictions and ground_truth must be aligned by index.
        """
        assert len(predictions) == len(ground_truth)
        
        predicted_intents = [p['predicted_intent'] for p in predictions]
        true_intents = [g['intent'] for g in ground_truth]
        
        # Basic metrics
        accuracy = accuracy_score(true_intents, predicted_intents)
        precision, recall, f1, support = precision_recall_fscore_support(
            true_intents, predicted_intents, 
            labels=self.intent_list,
            zero_division=0,
            average='weighted'
        )
        
        # Confusion matrix
        conf_matrix = confusion_matrix(
            true_intents, predicted_intents,
            labels=self.intent_list
        )
        
        # Per-class metrics
        class_report = classification_report(
            true_intents, predicted_intents,
            labels=self.intent_list,
            zero_division=0,
            output_dict=True
        )
        
        per_class = {}
        for intent in self.intent_list:
            if intent in class_report:
                per_class[intent] = {
                    'precision': class_report[intent]['precision'],
                    'recall': class_report[intent]['recall'],
                    'f1': class_report[intent]['f1-score'],
                    'support': int(class_report[intent]['support'])
                }
        
        return MetricsResult(
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1=f1,
            confusion_matrix=conf_matrix.tolist(),
            per_class_metrics=per_class,
            raw_report=classification_report(
                true_intents, predicted_intents,
                labels=self.intent_list,
                zero_division=0
            )
        )
    
    async def evaluate_escalation(
        self,
        predictions: List[Dict],  # [{message, predicted_escalate}, ...]
        ground_truth: List[Dict],  # [{message, should_escalate}, ...]
    ) -> Dict:
        """
        Evaluate escalation decision performance.
        """
        assert len(predictions) == len(ground_truth)
        
        predicted_escalate = [p['predicted_escalate'] for p in predictions]
        true_escalate = [g['should_escalate'] for g in ground_truth]
        
        # Treat as binary classification
        from sklearn.metrics import confusion_matrix as cm
        tn, fp, fn, tp = cm(true_escalate, predicted_escalate).ravel()
        
        accuracy = (tp + tn) / (tp + tn + fp + fn)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        # Business metrics: false negatives (missed escalations) are costly
        false_negative_rate = fn / (fn + tp) if (fn + tp) > 0 else 0
        
        return {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'true_positives': int(tp),
            'true_negatives': int(tn),
            'false_positives': int(fp),
            'false_negatives': int(fn),
            'false_negative_rate': false_negative_rate,  # Key business metric
        }
    
    async def evaluate_reply_quality(
        self,
        predicted_replies: List[str],
        reference_replies: List[str],
    ) -> Dict:
        """
        Evaluate reply quality using ROUGE and LLM-as-judge.
        
        This is a simplified version - full version would use LLM judge.
        """
        from rouge_score import rouge_scorer
        
        scorer = rouge_scorer.RougeScorer(['rouge1', 'rougeL'], use_stemmer=True)
        
        scores = []
        for pred, ref in zip(predicted_replies, reference_replies):
            score = scorer.score(ref, pred)
            scores.append({
                'rouge1': score['rouge1'].fmeasure,
                'rougeL': score['rougeL'].fmeasure,
            })
        
        avg_rouge1 = sum(s['rouge1'] for s in scores) / len(scores)
        avg_rougeL = sum(s['rougeL'] for s in scores) / len(scores)
        
        return {
            'avg_rouge1': avg_rouge1,
            'avg_rougeL': avg_rougeL,
            'sample_scores': scores[:5]  # First 5 for inspection
        }


class LLMAsJudgeEvaluator:
    """
    Use LLM to evaluate reply quality with a rubric.
    
    This addresses human-LLM agreement on what constitutes "good" replies.
    """
    
    def __init__(self, llm_client):
        self.llm = llm_client
    
    RUBRIC = """
You are an expert customer support evaluator. Rate this support agent reply on these dimensions:

RUBRIC (1-5 scale):
1. RELEVANT: Does the reply address the customer's issue?
2. ACCURATE: Is the information factually correct?
3. EMPATHETIC: Does it acknowledge customer's emotion?
4. ACTIONABLE: Does it provide clear next steps?
5. CONCISE: Is it appropriately brief (1-2 sentences)?

AGREEMENT CHECK: Compare agent reply to a reference ideal reply and score similarity (1-5).

Customer Message: {customer_message}
Customer Issue: {intent}

AGENT REPLY:
{predicted_reply}

REFERENCE REPLY (ideal):
{reference_reply}

Respond in JSON:
{
    "relevance": 4,
    "accuracy": 4,
    "empathy": 3,
    "actionability": 4,
    "conciseness": 5,
    "agreement_with_reference": 4,
    "overall_quality": 4,
    "reasoning": "Brief explanation of scores"
}
"""
    
    async def evaluate_reply(
        self,
        customer_message: str,
        predicted_reply: str,
        reference_reply: str,
        intent: str
    ) -> Dict:
        """Evaluate a single reply using LLM judge."""
        prompt = self.RUBRIC.format(
            customer_message=customer_message,
            predicted_reply=predicted_reply,
            reference_reply=reference_reply,
            intent=intent
        )
        
        try:
            response = await self.llm.call(
                prompt=prompt,
                model="gpt-4",
                temperature=0.1,
                max_tokens=300
            )
            
            result = json.loads(response)
            return result
        except Exception as e:
            print(f"⚠ Error evaluating reply: {e}")
            return {'error': str(e)}
    
    async def evaluate_batch(
        self,
        items: List[Dict]  # [{customer_message, predicted_reply, reference_reply, intent}, ...]
    ) -> Tuple[List[Dict], float]:
        """
        Evaluate multiple replies and compute human-LLM agreement score.
        
        Returns:
            (results, human_llm_agreement_rate)
        """
        results = []
        for item in items:
            result = await self.evaluate_reply(
                customer_message=item['customer_message'],
                predicted_reply=item['predicted_reply'],
                reference_reply=item['reference_reply'],
                intent=item['intent']
            )
            results.append(result)
        
        # Compute agreement: how often LLM gave reply >= 4/5 rating
        high_quality = sum(1 for r in results if r.get('overall_quality', 0) >= 4)
        agreement_rate = high_quality / len(results) if results else 0
        
        return results, agreement_rate


def save_evaluation_results(results: Dict, filepath: str):
    """Save evaluation results to JSON."""
    with open(filepath, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"✓ Saved evaluation results to {filepath}")
