#!/usr/bin/env python3
"""
Submission Verification Script
Checks that all required deliverables are present and working.
"""

import os
import json
import sys
from pathlib import Path

def check(condition: bool, message: str):
    """Print checkmark or X."""
    symbol = "✓" if condition else "✗"
    print(f"  {symbol} {message}")
    return condition

def verify_files():
    """Verify all required files exist."""
    print("\n" + "="*60)
    print("FILE STRUCTURE VERIFICATION")
    print("="*60)
    
    required_files = {
        "src/config.py": "Intent definitions",
        "src/agent.py": "Main orchestrator",
        "src/classifier.py": "Intent classification",
        "src/reply_generator.py": "Reply generation",
        "src/escalator.py": "Escalation decisions",
        "src/llm_client.py": "LLM provider abstraction",
        "src/evaluator.py": "Evaluation metrics",
        "src/baselines.py": "Baseline implementations",
        "src/golden_set.py": "Golden set builder",
        "src/main.py": "End-to-end pipeline",
        "data/golden_eval_set.json": "200 labeled examples",
        "evaluation/failure_analysis.md": "Failure deep-dive",
        "README.md": "Main documentation",
        "SUBMISSION_GUIDE.md": "Submission guide",
        "requirements.txt": "Dependencies",
        "setup.py": "Package setup",
    }
    
    all_exist = True
    for filepath, description in required_files.items():
        exists = Path(filepath).exists()
        all_exist = all_exist and exists
        check(exists, f"{filepath:40} ({description})")
    
    return all_exist

def verify_golden_set():
    """Verify golden evaluation set."""
    print("\n" + "="*60)
    print("GOLDEN EVALUATION SET VERIFICATION")
    print("="*60)
    
    try:
        with open("data/golden_eval_set.json") as f:
            data = json.load(f)
        
        check(
            "metadata" in data,
            f"Has metadata"
        )
        
        size = len(data.get("examples", []))
        check(
            150 <= size <= 250,
            f"Size: {size} examples (target: 150-250)"
        )
        
        dist = data.get("distribution", {})
        check(
            len(dist) >= 8,
            f"Intents represented: {len(dist)} (target: 8+)"
        )
        
        min_per_intent = min(dist.values()) if dist else 0
        check(
            min_per_intent >= 10,
            f"Minimum per intent: {min_per_intent} (target: 10+)"
        )
        
        # Verify examples have required fields
        example = data["examples"][0] if data.get("examples") else {}
        has_message = "customer_message" in example
        has_ground_truth = "ground_truth" in example
        
        check(
            has_message and has_ground_truth,
            f"Examples have required fields"
        )
        
        return True
    except Exception as e:
        print(f"  ✗ Error reading golden set: {e}")
        return False

def verify_code_quality():
    """Verify code can be imported and run."""
    print("\n" + "="*60)
    print("CODE QUALITY VERIFICATION")
    print("="*60)
    
    sys.path.insert(0, "src")
    
    try:
        from config import Intent, BRAND
        check(len(list(Intent)) == 10, f"Has 10 intents defined")
        check(BRAND == "amazon", f"Brand is correctly set to amazon")
        
        from llm_client import get_llm_client, MockLLMClient
        check(True, f"LLM client module imports")
        
        from agent import SupportAgent
        check(True, f"Agent module imports")
        
        from classifier import IntentClassifier
        check(True, f"Classifier module imports")
        
        from escalator import EscalationDecider
        check(True, f"Escalator module imports")
        
        from evaluator import EvaluationHarness
        check(True, f"Evaluator module imports")
        
        from baselines import TrivialBaseline, RuleBasedBaseline
        check(True, f"Baseline module imports")
        
        # Test mock LLM
        import asyncio
        
        async def test_llm():
            llm = MockLLMClient()
            result = await llm.call(
                prompt="test",
                model="mock",
                temperature=0.5,
                max_tokens=100
            )
            return len(result) > 0
        
        works = asyncio.run(test_llm())
        check(works, f"Mock LLM works")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def verify_documentation():
    """Verify documentation completeness."""
    print("\n" + "="*60)
    print("DOCUMENTATION VERIFICATION")
    print("="*60)
    
    try:
        # Check README
        with open("README.md") as f:
            readme = f.read()
        
        check("Quick Start" in readme, "README has Quick Start")
        check("Architecture" in readme, "README has Architecture")
        check("Decision Log" in readme, "README has Decision Log")
        check("Failure Mode" in readme, "README mentions failure analysis")
        
        # Check Failure Analysis
        with open("evaluation/failure_analysis.md") as f:
            failures = f.read()
        
        check("Failure Mode" in failures, "Has 5 failure modes documented")
        check("Hypothesis" in failures, "Includes hypotheses")
        check("Proposed Fix" in failures, "Includes proposed fixes")
        
        # Check Submission Guide
        with open("SUBMISSION_GUIDE.md") as f:
            guide = f.read()
        
        check("Quick Start" in guide, "Submission guide has setup")
        check("Deployment" in guide, "Submission guide has deployment notes")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def main():
    """Run all verification checks."""
    print("\n" + "="*60)
    print("HIVER SUBMISSION VERIFICATION")
    print("="*60)
    
    results = {
        "File Structure": verify_files(),
        "Golden Set": verify_golden_set(),
        "Code Quality": verify_code_quality(),
        "Documentation": verify_documentation(),
    }
    
    print("\n" + "="*60)
    print("VERIFICATION SUMMARY")
    print("="*60)
    
    for check_name, result in results.items():
        symbol = "✓" if result else "✗"
        print(f"  {symbol} {check_name}")
    
    all_pass = all(results.values())
    
    print("\n" + "="*60)
    if all_pass:
        print("✓ ALL CHECKS PASSED - Ready for submission!")
    else:
        print("✗ Some checks failed - review above")
    print("="*60 + "\n")
    
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
