"""
Main pipeline orchestration and end-to-end runner.
"""

import asyncio
import json
from pathlib import Path
from typing import List, Dict, Optional
import argparse

from config import (
    BRAND, GOLDEN_SET_PATH, RAW_DATA_DIR, RESULTS_DIR
)
from llm_client import get_llm_client
from agent import SupportAgent
from golden_set import GoldenSetBuilder, create_sample_golden_set
from evaluator import EvaluationHarness, LLMAsJudgeEvaluator
from baselines import TrivialBaseline, RuleBasedBaseline, BaselineEvaluator
from data_loader import prepare_sample_dataset


def create_result_dir():
    """Create results directory if needed."""
    Path(RESULTS_DIR).mkdir(parents=True, exist_ok=True)


async def generate_golden_set(force_recreate: bool = False):
    """
    Generate or load the golden evaluation set.
    """
    if Path(GOLDEN_SET_PATH).exists() and not force_recreate:
        print(f"✓ Loading existing golden set from {GOLDEN_SET_PATH}")
        builder = GoldenSetBuilder.load(GOLDEN_SET_PATH)
    else:
        print("Creating golden evaluation set...")
        builder = GoldenSetBuilder()
        
        examples = create_sample_golden_set()
        builder.add_batch(examples)
        
        # Verify balance
        if not builder.is_balanced():
            print("⚠ Warning: Golden set is not balanced across intents")
            print(f"  Distribution: {builder.get_distribution()}")
        
        builder.save(GOLDEN_SET_PATH)
    
    return builder


async def run_baselines(
    golden_set: GoldenSetBuilder,
    harness: EvaluationHarness
) -> Dict:
    """
    Run baseline implementations for comparison.
    """
    print("\n" + "="*60)
    print("EVALUATING BASELINES")
    print("="*60)
    
    test_data = golden_set.examples
    
    # Trivial Baseline
    print("\n[1/2] Trivial Baseline (always general_inquiry, never escalate)...")
    trivial_results = await BaselineEvaluator.evaluate_baseline(
        TrivialBaseline(),
        test_data,
        harness
    )
    
    print(f"  Classification Accuracy: {trivial_results['classification']['accuracy']:.1%}")
    print(f"  Escalation F1: {trivial_results['escalation']['f1']:.1%}")
    
    # Rule-based Baseline
    print("\n[2/2] Rule-based Baseline (keyword + heuristics)...")
    rulebased_results = await BaselineEvaluator.evaluate_baseline(
        RuleBasedBaseline(),
        test_data,
        harness
    )
    
    print(f"  Classification Accuracy: {rulebased_results['classification']['accuracy']:.1%}")
    print(f"  Escalation F1: {rulebased_results['escalation']['f1']:.1%}")
    
    return {
        'trivial': trivial_results,
        'rulebased': rulebased_results
    }


async def run_agent_evaluation(
    agent: SupportAgent,
    golden_set: GoldenSetBuilder,
    harness: EvaluationHarness,
    llm_judge: LLMAsJudgeEvaluator
) -> Dict:
    """
    Evaluate the main support agent end-to-end.
    """
    print("\n" + "="*60)
    print("EVALUATING MAIN AGENT")
    print("="*60)
    
    test_data = golden_set.examples
    
    # Process all test messages
    print(f"\nProcessing {len(test_data)} golden set examples...")
    
    agent_results = []
    for i, example in enumerate(test_data):
        if (i + 1) % 50 == 0:
            print(f"  Processed {i+1}/{len(test_data)}")
        
        result = await agent.process_message(
            customer_message=example['customer_message'],
            customer_id=f"test_user_{i}",
        )
        agent_results.append(result)
    
    # Extract predictions
    predictions_classify = [
        {
            'message': r['message'],
            'predicted_intent': r['classification']['intent']
        }
        for r in agent_results
    ]
    
    predictions_escalate = [
        {
            'message': r['message'],
            'predicted_escalate': r['decision']['should_escalate']
        }
        for r in agent_results
    ]
    
    ground_truth = [
        {
            'intent': ex['ground_truth']['intent'],
            'should_escalate': ex['ground_truth']['should_escalate']
        }
        for ex in test_data
    ]
    
    # Evaluate classification
    print("\nEvaluating classification...")
    classify_metrics = await harness.evaluate_classification(
        predictions_classify,
        [{'intent': g['intent']} for g in ground_truth]
    )
    
    print(f"  Accuracy: {classify_metrics.accuracy:.1%}")
    print(f"  Precision: {classify_metrics.precision:.1%}")
    print(f"  Recall: {classify_metrics.recall:.1%}")
    print(f"  F1: {classify_metrics.f1:.1%}")
    
    # Evaluate escalation
    print("\nEvaluating escalation decisions...")
    escalate_metrics = await harness.evaluate_escalation(
        predictions_escalate,
        ground_truth
    )
    
    print(f"  Accuracy: {escalate_metrics['accuracy']:.1%}")
    print(f"  Precision: {escalate_metrics['precision']:.1%}")
    print(f"  Recall: {escalate_metrics['recall']:.1%}")
    print(f"  F1: {escalate_metrics['f1']:.1%}")
    print(f"  False Negative Rate: {escalate_metrics['false_negative_rate']:.1%}")
    print(f"    ↳ (Missed escalations - critical metric!)")
    
    return {
        'classification': {
            'accuracy': classify_metrics.accuracy,
            'precision': classify_metrics.precision,
            'recall': classify_metrics.recall,
            'f1': classify_metrics.f1,
            'per_class': classify_metrics.per_class_metrics,
            'confusion_matrix': classify_metrics.confusion_matrix
        },
        'escalation': escalate_metrics,
        'raw_results': agent_results
    }


async def main(args):
    """Main pipeline."""
    
    create_result_dir()
    
    print("="*60)
    print(f"HIVER - AI SUPPORT AGENT PIPELINE")
    print(f"Brand: {BRAND.upper()}")
    print("="*60)
    
    # Step 1: Generate/load golden set
    print("\n[STEP 1] Golden Evaluation Set")
    golden_set = await generate_golden_set(force_recreate=args.recreate_golden)
    print(f"  ✓ {len(golden_set.examples)} examples")
    print(f"  ✓ Distribution: {golden_set.get_distribution()}")
    
    # Step 2: Initialize LLM and agent
    print("\n[STEP 2] Initializing Agent")
    llm_provider = args.llm or "mock"
    print(f"  Using LLM: {llm_provider}")
    
    try:
        llm = get_llm_client(llm_provider)
        agent = SupportAgent(llm)
        print("  ✓ Agent initialized")
    except Exception as e:
        print(f"  ✗ Error initializing agent: {e}")
        return
    
    # Step 3: Load knowledge base (if available)
    if args.knowledge_file:
        print(f"\n[STEP 3] Loading Knowledge Base from {args.knowledge_file}")
        try:
            with open(args.knowledge_file) as f:
                knowledge = json.load(f)
            agent.load_knowledge_base(knowledge)
            print(f"  ✓ Loaded {len(knowledge)} knowledge examples")
        except Exception as e:
            print(f"  ✗ Error loading knowledge: {e}")
    
    # Step 4: Evaluate baselines
    print("\n[STEP 4] Evaluating Baselines")
    harness = EvaluationHarness()
    baseline_results = await run_baselines(golden_set, harness)
    
    # Step 5: Evaluate main agent
    print("\n[STEP 5] Evaluating Main Agent")
    llm_judge = LLMAsJudgeEvaluator(llm)
    agent_results = await run_agent_evaluation(agent, golden_set, harness, llm_judge)
    
    # Step 6: Save results
    print("\n[STEP 6] Saving Results")
    
    final_results = {
        'metadata': {
            'brand': BRAND,
            'llm_provider': llm_provider,
            'golden_set_size': len(golden_set.examples),
            'golden_set_distribution': golden_set.get_distribution(),
        },
        'baselines': baseline_results,
        'agent': agent_results,
        'agent_stats': agent.get_stats()
    }
    
    results_path = f"{RESULTS_DIR}/evaluation_results.json"
    with open(results_path, 'w') as f:
        # Save without raw_results to keep JSON size manageable
        summary = final_results.copy()
        if 'agent' in summary and 'raw_results' in summary['agent']:
            summary['agent'].pop('raw_results')
        json.dump(summary, f, indent=2, default=str)
    
    print(f"  ✓ Results saved to {results_path}")
    
    # Print summary
    print("\n" + "="*60)
    print("RESULTS SUMMARY")
    print("="*60)
    
    print("\nTrivial Baseline:")
    print(f"  Classification Accuracy: {baseline_results['trivial']['classification']['accuracy']:.1%}")
    
    print("\nRule-based Baseline:")
    print(f"  Classification Accuracy: {baseline_results['rulebased']['classification']['accuracy']:.1%}")
    
    print("\nMain Agent (LLM-powered):")
    print(f"  Classification Accuracy: {agent_results['classification']['accuracy']:.1%}")
    print(f"  Escalation F1: {agent_results['escalation']['f1']:.1%}")
    print(f"  Improvement over Rule-based: {(agent_results['classification']['accuracy'] - baseline_results['rulebased']['classification']['accuracy']):.1%}")


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Run Hiver support agent end-to-end pipeline"
    )
    parser.add_argument(
        "--llm",
        choices=["openai", "anthropic", "mock"],
        default="mock",
        help="LLM provider to use"
    )
    parser.add_argument(
        "--recreate-golden",
        action="store_true",
        help="Force recreation of golden evaluation set"
    )
    parser.add_argument(
        "--knowledge-file",
        type=str,
        help="Path to knowledge base JSON file"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(main(args))
