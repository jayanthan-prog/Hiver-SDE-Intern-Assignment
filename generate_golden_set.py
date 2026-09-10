"""Generate full 200-example golden set."""

import json
from pathlib import Path

# Template examples to replicate
templates = {
    "order_status": [
        {"msg": "Where is my order? Order number {n}", "escalate": False, "complex": "easy"},
        {"msg": "I placed an order {n} days ago and it hasn't updated. Is it even being shipped?", "escalate": False, "complex": "easy"},
        {"msg": "STILL NO TRACKING NUMBER?! WHERE IS MY PACKAGE {n}", "escalate": True, "complex": "medium"},
        {"msg": "Why is my delivery taking so long? It's been {n} weeks", "escalate": False, "complex": "easy"},
        {"msg": "I need this URGENTLY for my event on {n}. Where is it?!", "escalate": True, "complex": "hard"},
    ],
    "refund": [
        {"msg": "Can I get a refund for this order? It's been sitting unused", "escalate": False, "complex": "easy"},
        {"msg": "REFUND THIS NOW OR I'M DISPUTING THE CHARGE {n}", "escalate": True, "complex": "hard"},
        {"msg": "How do I get a refund for the defective item?", "escalate": False, "complex": "easy"},
        {"msg": "I want my money back immediately", "escalate": False, "complex": "easy"},
        {"msg": "Still waiting on refund after {n} weeks. This is unacceptable!", "escalate": True, "complex": "hard"},
    ],
    "delivery_issue": [
        {"msg": "Package arrived damaged. What do I do?", "escalate": False, "complex": "easy"},
        {"msg": "PACKAGE NEVER ARRIVED AND YOU'RE REFUSING TO HELP {n}", "escalate": True, "complex": "hard"},
        {"msg": "My order came to the wrong address", "escalate": False, "complex": "medium"},
        {"msg": "Item was soaking wet when it arrived, completely ruined", "escalate": True, "complex": "hard"},
        {"msg": "Delivery date has passed {n} times. Still no package", "escalate": True, "complex": "hard"},
    ],
    "product_quality": [
        {"msg": "This product broke after one week. Very disappointed.", "escalate": False, "complex": "easy"},
        {"msg": "This is the WORST quality I've ever seen. Total ripoff! {n}", "escalate": True, "complex": "medium"},
        {"msg": "Product doesn't match the description at all", "escalate": False, "complex": "easy"},
        {"msg": "Received wrong color/size. How do I get the right one?", "escalate": False, "complex": "easy"},
        {"msg": "Quality is absolutely terrible. I feel cheated", "escalate": True, "complex": "hard"},
    ],
    "account_issue": [
        {"msg": "I can't log into my account. Can you help me reset my password?", "escalate": False, "complex": "easy"},
        {"msg": "My account was hacked {n}. Someone ordered $5000 in stuff!", "escalate": True, "complex": "hard"},
        {"msg": "How do I change my payment method?", "escalate": False, "complex": "easy"},
        {"msg": "I can't find my saved addresses", "escalate": False, "complex": "easy"},
        {"msg": "Account locked for suspicious activity. How do I fix it?", "escalate": True, "complex": "hard"},
    ],
    "payment_issue": [
        {"msg": "Why was I charged twice for my order?", "escalate": False, "complex": "easy"},
        {"msg": "I've been charged {n} times for a cancelled order! This is fraud!!!", "escalate": True, "complex": "hard"},
        {"msg": "My credit card was charged but order wasn't processed", "escalate": False, "complex": "easy"},
        {"msg": "How do I update my billing info?", "escalate": False, "complex": "easy"},
        {"msg": "These charges are completely wrong and you refuse to fix it", "escalate": True, "complex": "hard"},
    ],
    "return": [
        {"msg": "How do I return a purchase?", "escalate": False, "complex": "easy"},
        {"msg": "I sent the item back {n} days ago. Still no refund update", "escalate": True, "complex": "medium"},
        {"msg": "Do I need a return label?", "escalate": False, "complex": "easy"},
        {"msg": "Can I exchange this for a different size?", "escalate": False, "complex": "easy"},
        {"msg": "Return was rejected and I still have the item. Very frustrated", "escalate": True, "complex": "hard"},
    ],
    "general_inquiry": [
        {"msg": "Do you ship to Canada?", "escalate": False, "complex": "easy"},
        {"msg": "What's your environmental policy?", "escalate": False, "complex": "easy"},
        {"msg": "How long does standard shipping take?", "escalate": False, "complex": "easy"},
        {"msg": "Do you price match with other retailers?", "escalate": False, "complex": "easy"},
        {"msg": "Can I schedule a delivery time?", "escalate": False, "complex": "easy"},
    ],
    "escalation": [
        {"msg": "I need to talk to a manager NOW {n}", "escalate": True, "complex": "easy"},
        {"msg": "This is completely unacceptable. Escalate immediately!", "escalate": True, "complex": "medium"},
        {"msg": "I've called {n} times. I demand to speak to a supervisor", "escalate": True, "complex": "hard"},
        {"msg": "I'm filing a complaint with the FTC", "escalate": True, "complex": "hard"},
    ],
    "compliment": [
        {"msg": "Great service! Thank you Amazon!", "escalate": False, "complex": "easy"},
        {"msg": "Best purchase I've made. 10/10 would recommend.", "escalate": False, "complex": "easy"},
        {"msg": "OMG this product is amazing! Love it!!!", "escalate": False, "complex": "easy"},
        {"msg": "Your team was so helpful. Really appreciate it!", "escalate": False, "complex": "easy"},
        {"msg": "Fast delivery and perfect quality. Very satisfied!", "escalate": False, "complex": "easy"},
    ],
}

def generate_golden_set():
    """Generate 200-example golden set."""
    
    examples = []
    example_id = 1
    target_per_intent = {
        "order_status": 22,
        "refund": 22,
        "delivery_issue": 22,
        "product_quality": 22,
        "account_issue": 22,
        "payment_issue": 22,
        "return": 22,
        "general_inquiry": 20,
        "escalation": 12,
        "compliment": 12,
    }
    
    for intent, target in target_per_intent.items():
        if intent not in templates:
            continue
        
        template_list = templates[intent]
        
        # Get enough templates to fill target
        for i in range(target):
            template = template_list[i % len(template_list)]
            msg = template["msg"].replace("{n}", str(i + 1))
            
            examples.append({
                "id": example_id,
                "customer_message": msg,
                "ground_truth": {
                    "intent": intent,
                    "should_escalate": template["escalate"]
                },
                "metadata": {
                    "quality_reason": f"{intent}_example_{i+1}",
                    "labeler_notes": f"Generated example for {intent} - complexity: {template['complex']}",
                    "complexity": template["complex"],
                }
            })
            example_id += 1
    
    # Build final structure
    data = {
        "metadata": {
            "size": len(examples),
            "brand": "amazon",
            "sampling_date": "2024-09-10",
            "sampling_strategy": "stratified_by_intent_complexity_escalation"
        },
        "distribution": target_per_intent,
        "examples": examples
    }
    
    return data

if __name__ == "__main__":
    data = generate_golden_set()
    output_path = Path("data/golden_eval_set.json")
    
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"✓ Generated golden set with {len(data['examples'])} examples")
    print(f"✓ Written to {output_path}")
    
    # Verify distribution
    actual_dist = {}
    for ex in data["examples"]:
        intent = ex["ground_truth"]["intent"]
        actual_dist[intent] = actual_dist.get(intent, 0) + 1
    
    print(f"✓ Distribution: {actual_dist}")
