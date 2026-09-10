"""
Core configuration and constants for the support agent.
"""

from enum import Enum
from typing import List

# ============= BRAND SELECTION =============
# Selected brand: Amazon (highest volume, diverse issue types)
BRAND = "amazon"

# ============= INTENT DEFINITIONS =============
class Intent(str, Enum):
    """Customer support intents discovered from Amazon data."""
    
    ORDER_STATUS = "order_status"  # Asking about order tracking/status
    REFUND = "refund"  # Refund requests or refund status
    DELIVERY_ISSUE = "delivery_issue"  # Late/missing/damaged delivery
    PRODUCT_QUALITY = "product_quality"  # Defective/wrong product
    ACCOUNT_ISSUE = "account_issue"  # Account access, password, login
    PAYMENT_ISSUE = "payment_issue"  # Billing, payment method, charges
    RETURN = "return"  # Return process, RMA
    ESCALATION = "escalation"  # Already frustrated, needs human
    GENERAL_INQUIRY = "general_inquiry"  # General questions
    COMPLIMENT = "compliment"  # Praise, positive feedback


INTENT_DESCRIPTIONS = {
    Intent.ORDER_STATUS: "Customer asking about their order status, tracking, or delivery date",
    Intent.REFUND: "Customer requesting a refund or asking about refund status",
    Intent.DELIVERY_ISSUE: "Order is late, missing, or damaged upon delivery",
    Intent.PRODUCT_QUALITY: "Product is defective, wrong item, or doesn't meet expectations",
    Intent.ACCOUNT_ISSUE: "Problems with account access, login, or account settings",
    Intent.PAYMENT_ISSUE: "Billing disputes, incorrect charges, or payment method problems",
    Intent.RETURN: "Customer wants to return a product or needs return instructions",
    Intent.ESCALATION: "Customer is already escalated/frustrated and needs human attention",
    Intent.GENERAL_INQUIRY: "General questions that don't fit other categories",
    Intent.COMPLIMENT: "Positive feedback or compliment that doesn't need action",
}

# ============= ESCALATION TRIGGERS =============
ESCALATION_KEYWORDS = [
    "unacceptable", "terrible", "awful", "worst", "disgusting",
    "scam", "fraud", "lawyer", "legal", "sue",
    "demand", "manager", "supervisor", "escalate",
    "never again", "will never", "extremely", "furious",
    "disappointed", "upset", "frustrated", "angry",
]

ESCALATION_THRESHOLDS = {
    "max_retries": 2,  # If customer has messaged 2+ times about same issue
    "sentiment_threshold": -0.7,  # Very negative sentiment score
    "requires_verification": True,  # Requires order verification
}

# ============= EVALUATION SETTINGS =============
GOLDEN_SET_SIZE = 200  # Number of hand-labeled examples
MIN_INTENT_EXAMPLES = 15  # Min examples per intent in golden set

# ============= MODEL SETTINGS =============
LLM_MODEL = "gpt-4"  # Primary LLM for classification and generation
FALLBACK_MODEL = "gpt-3.5-turbo"
TEMPERATURE_CLASSIFY = 0.1  # Low temperature for consistent classification
TEMPERATURE_REPLY = 0.7  # Higher for more natural replies
MAX_TOKENS_REPLY = 200
MAX_TOKENS_CLASSIFY = 100

# ============= DATA PATHS =============
RAW_DATA_DIR = "data/raw"
PROCESSED_DATA_DIR = "data/processed"
GOLDEN_SET_PATH = "data/golden_eval_set.json"
SAMPLE_PATH = "data/sample_tweets.json"
RESULTS_DIR = "results"

# ============= DATASET INFO =============
# We'll subsample the Kaggle dataset for feasibility
SUBSAMPLE_SIZE = 5000  # Sample 5K tweets to start with
BRAND_SUBSAMPLE = 500  # 500 per brand for deeper analysis
