#!/usr/bin/env python3
"""
Run the Hiver AI Support Agent pipeline and display beautiful results.
"""
import sys
import json
import asyncio
from pathlib import Path
from typing import Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from llm_client import MockLLMClient, get_llm_client
from agent import SupportAgent
from baselines import TrivialBaseline, RuleBasedBaseline
from config import Intent, BRAND


class TerminalUI:
    """Beautiful terminal UI renderer."""
    
    @staticmethod
    def header(title: str, level: int = 1) -> str:
        if level == 1:
            return f"\n{'='*70}\n{title.center(70)}\n{'='*70}\n"
        elif level == 2:
            return f"\n{'-'*70}\n{title}\n{'-'*70}\n"
        else:
            return f"\n→ {title}\n"
    
    @staticmethod
    def metric(name: str, value: Any, unit: str = "", good_min: float = None) -> str:
        val_str = str(value)
        if isinstance(value, float):
            if 0 <= value <= 1:
                val_str = f"{value:.1%}"
            else:
                val_str = f"{value:.2f}"
        
        # Color coding for performance
        marker = "✓"
        if good_min is not None and isinstance(value, (int, float)):
            if value >= good_min:
                marker = "✓"  # Good
            else:
                marker = "○"  # Fair
        
        return f"  {marker} {name:.<40} {val_str} {unit}".ljust(70)
    
    @staticmethod
    def benchmark_table(data: Dict[str, Dict[str, float]]) -> str:
        lines = []
        lines.append("┌─" + "─"*18 + "─┬─" + "─"*12 + "─┬─" + "─"*15 + "─┬─" + "─"*12 + "─┐")
        header = f"│ {'System':<18} │ {'Strategy':<12} │ {'Accuracy':<15} │ {'vs Baseline':<12} │"
        lines.append(header)
        lines.append("├─" + "─"*18 + "─┼─" + "─"*12 + "─┼─" + "─"*15 + "─┼─" + "─"*12 + "─┤")
        
        for system, metrics in data.items():
            acc = metrics.get("accuracy", 0)
            baseline_delta = metrics.get("vs_baseline", "")
            strategy = metrics.get("strategy", "")
            line = f"│ {system:<18} │ {strategy:<12} │ {acc:>13.1%} │ {baseline_delta:>12} │"
            lines.append(line)
        
        lines.append("└─" + "─"*18 + "─┴─" + "─"*12 + "─┴─" + "─"*15 + "─┴─" + "─"*12 + "─┘")
        return "\n".join(lines)
    
    @staticmethod
    def sample_results(results: list, count: int = 5) -> str:
        lines = []
        for result in results[:count]:
            customer = result.get("customer_message", "")[:40]
            intent = result.get("predicted_intent", "")
            ground_truth = result.get("ground_truth_intent", "")
            match = "✓" if intent == ground_truth else "✗"
            confidence = result.get("confidence", 0)
            
            lines.append(f"  {match} Intent: {intent:<20} (confidence: {confidence:.0%}) - {ground_truth}")
            lines.append(f"     Message: \"{customer}...\"")
        
        return "\n".join(lines)


async def run_pipeline() -> Dict[str, Any]:
    """Run the complete pipeline and return results."""
    
    results = {
        "golden_set": {},
        "baselines": {},
        "main_agent": {},
        "sample_results": [],
        "per_intent_accuracy": {},
    }
    
    # Load golden set
    print("\n⏳ Loading golden evaluation set...", end=" ", flush=True)
    with open("data/golden_eval_set.json") as f:
        data = json.load(f)
    examples = data["examples"]
    results["golden_set"] = {
        "size": len(examples),
        "intents": len(set(e["ground_truth"]["intent"] for e in examples)),
        "with_escalation": sum(1 for e in examples if e.get("ground_truth", {}).get("should_escalate", False)),
    }
    print(f"✓ {len(examples)} examples loaded")
    
    # Initialize systems
    print("⏳ Initializing systems...", end=" ", flush=True)
    llm = MockLLMClient()
    agent = SupportAgent(llm)
    trivial = TrivialBaseline()
    rule_based = RuleBasedBaseline()
    print("✓ Done")
    
    # Evaluate systems
    print("\n⏳ Evaluating systems on golden set (this may take a minute)...")
    
    trivial_correct = 0
    rule_correct = 0
    agent_correct = 0
    agent_escalation_correct = 0
    sample_results = []
    per_intent_counts = {}
    per_intent_correct = {}
    
    for i, example in enumerate(examples):
        if (i + 1) % 50 == 0:
            print(f"   Progress: {i+1}/{len(examples)} examples...", flush=True)
        
        message = example["customer_message"]
        ground_truth = example.get("ground_truth", {})
        ground_intent = ground_truth.get("intent", "general_inquiry")
        ground_escalate = ground_truth.get("should_escalate", False)
        
        # Initialize per-intent tracking
        if ground_intent not in per_intent_counts:
            per_intent_counts[ground_intent] = 0
            per_intent_correct[ground_intent] = 0
        per_intent_counts[ground_intent] += 1
        
        # Trivial baseline
        trivial_pred = trivial.classify(message)
        if trivial_pred == ground_intent:
            trivial_correct += 1
        
        # Rule-based baseline
        rule_pred = rule_based.classify(message)
        if rule_pred == ground_intent:
            rule_correct += 1
        
        # Main agent
        try:
            agent_result = await agent.process_message(
                customer_message=message,
                customer_id=f"test_{i}",
                conversation_id=f"conv_{i}"
            )
            agent_pred = agent_result.get("classification", {}).get("intent", "general_inquiry")
            agent_escalate = agent_result.get("decision", {}).get("should_escalate", False)
            confidence = agent_result.get("classification", {}).get("confidence", 0.0)
            
            if agent_pred == ground_intent:
                agent_correct += 1
                per_intent_correct[ground_intent] += 1
            
            if agent_escalate == ground_escalate:
                agent_escalation_correct += 1
            
            # Store sample results (first 10)
            if len(sample_results) < 10:
                sample_results.append({
                    "customer_message": message,
                    "predicted_intent": agent_pred,
                    "ground_truth_intent": ground_intent,
                    "confidence": confidence,
                    "escalate_predicted": agent_escalate,
                    "escalate_ground": ground_escalate,
                })
        except Exception as e:
            print(f"   Error processing: {str(e)[:50]}")
    
    # Calculate metrics
    total = len(examples)
    trivial_acc = trivial_correct / total if total > 0 else 0
    rule_acc = rule_correct / total if total > 0 else 0
    agent_acc = agent_correct / total if total > 0 else 0
    agent_escalation_acc = agent_escalation_correct / total if total > 0 else 0
    
    results["baselines"] = {
        "trivial": {
            "strategy": "Always 'general_inquiry'",
            "accuracy": trivial_acc,
            "correct": trivial_correct,
            "total": total,
        },
        "rule_based": {
            "strategy": "Keyword matching",
            "accuracy": rule_acc,
            "correct": rule_correct,
            "total": total,
        },
    }
    
    results["main_agent"] = {
        "strategy": "LLM-based classification",
        "accuracy": agent_acc,
        "escalation_accuracy": agent_escalation_acc,
        "correct": agent_correct,
        "escalation_correct": agent_escalation_correct,
        "total": total,
        "vs_trivial": f"+{(agent_acc - trivial_acc):.1%}",
        "vs_rule": f"+{(agent_acc - rule_acc):.1%}",
    }
    
    results["per_intent_accuracy"] = {
        intent: per_intent_correct[intent] / per_intent_counts[intent] if per_intent_counts[intent] > 0 else 0
        for intent in per_intent_counts
    }
    
    results["sample_results"] = sample_results
    
    return results


def display_results(results: Dict[str, Any]):
    """Display results in beautiful UI format."""
    
    ui = TerminalUI()
    
    # Title
    print(ui.header("🎯 HIVER AI SUPPORT AGENT - EVALUATION RESULTS", 1))
    
    # Golden Set Info
    print(ui.header("📊 Golden Evaluation Set", 2))
    gs = results["golden_set"]
    print(ui.metric("Total Examples", gs["size"]))
    print(ui.metric("Intent Classes", gs["intents"]))
    print(ui.metric("Escalation Cases", gs["with_escalation"]))
    
    # Baselines
    print(ui.header("📈 Baseline Systems", 2))
    trivial = results["baselines"]["trivial"]
    rule = results["baselines"]["rule_based"]
    print(ui.metric("1. Trivial (always same intent)", f"{trivial['accuracy']:.1%}", good_min=0))
    print(ui.metric("   • Strategy", trivial["strategy"]))
    print()
    print(ui.metric("2. Rule-Based (keyword matching)", f"{rule['accuracy']:.1%}", good_min=0.5))
    print(ui.metric("   • Strategy", rule["strategy"]))
    
    # Main Agent Performance
    print(ui.header("🚀 Main AI Agent", 2))
    agent = results["main_agent"]
    print(ui.metric("Classification Accuracy", f"{agent['accuracy']:.1%}", good_min=0.75))
    print(ui.metric("Escalation Accuracy", f"{agent['escalation_accuracy']:.1%}", good_min=0.80))
    print(ui.metric("vs. Trivial Baseline", agent["vs_trivial"], good_min=0))
    print(ui.metric("vs. Rule-Based Baseline", agent["vs_rule"], good_min=0))
    
    # Comparison Table
    print(ui.header("📊 Performance Comparison", 2))
    comparison_data = {
        "Trivial": {
            "strategy": "Always same",
            "accuracy": trivial["accuracy"],
            "vs_baseline": "-",
        },
        "Rule-Based": {
            "strategy": "Keywords",
            "accuracy": rule["accuracy"],
            "vs_baseline": "-",
        },
        "AI Agent": {
            "strategy": "LLM + signals",
            "accuracy": agent["accuracy"],
            "vs_baseline": agent["vs_rule"],
        },
    }
    print(ui.benchmark_table(comparison_data))
    
    # Per-Intent Performance
    print(ui.header("🎯 Accuracy by Intent Class", 2))
    per_intent = results["per_intent_accuracy"]
    sorted_intents = sorted(per_intent.items(), key=lambda x: x[1], reverse=True)
    for intent, accuracy in sorted_intents:
        emoji = "🟢" if accuracy >= 0.85 else "🟡" if accuracy >= 0.70 else "🔴"
        print(f"  {emoji} {intent:<25} {accuracy:>6.1%}")
    
    # Sample Classifications
    print(ui.header("📝 Sample Classifications (First 10)", 2))
    print(ui.sample_results(results["sample_results"], count=10))
    
    # Summary
    print(ui.header("✨ Summary", 2))
    print(f"""
  📌 Key Finding:
     The AI Agent achieves {agent['accuracy']:.1%} accuracy,
     {agent['vs_rule']} improvement over rule-based baseline.
  
  📌 Escalation Handling:
     Correctly identifies escalation cases {agent['escalation_accuracy']:.1%} of the time.
  
  📌 Best Performing Intents:
     {sorted_intents[0][0]:<25} {sorted_intents[0][1]:.1%}
     {sorted_intents[1][0]:<25} {sorted_intents[1][1]:.1%}
     {sorted_intents[2][0]:<25} {sorted_intents[2][1]:.1%}
  
  📌 System: {BRAND.title()} Support Agent
     Evaluated on: {gs['size']} examples
     Framework: AsyncIO, LLM-based, pluggable providers
""")
    
    # Technical Details
    print(ui.header("🔧 Technical Details", 2))
    print(f"""
  Architecture: 3-Stage Pipeline
    1. Intent Classification (LLM + low temperature)
    2. Escalation Assessment (Rule + sentiment signals)
    3. Reply Generation (Knowledge-grounded or escalate)
  
  LLM Provider: Mock (no API calls needed)
  Can switch to: OpenAI or Anthropic with API keys
  
  Features:
    ✓ Async/await for scalability
    ✓ Conversation history tracking
    ✓ Confidence scoring
    ✓ Multi-signal escalation detection
    ✓ Knowledge base integration
""")
    
    print(ui.header("", 1))
    print("✅ Evaluation Complete! Check results/evaluation_results.json for full metrics.\n")


def main():
    """Main entry point."""
    try:
        print("\n" + "="*70)
        print("Starting Hiver AI Support Agent Evaluation...".center(70))
        print("="*70)
        
        # Run async pipeline
        results = asyncio.run(run_pipeline())
        
        # Display results
        display_results(results)
        
        # Save results
        results_file = Path(__file__).parent / "results" / "evaluation_results.json"
        results_file.parent.mkdir(parents=True, exist_ok=True)
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"✓ Results saved to: {results_file}")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
