"""
Data loading and processing utilities.
"""

import json
import os
from typing import List, Dict, Any, Tuple
import pandas as pd
from pathlib import Path

from config import BRAND, RAW_DATA_DIR, PROCESSED_DATA_DIR


def ensure_dirs_exist():
    """Create necessary directories if they don't exist."""
    Path(RAW_DATA_DIR).mkdir(parents=True, exist_ok=True)
    Path(PROCESSED_DATA_DIR).mkdir(parents=True, exist_ok=True)


def download_kaggle_dataset():
    """
    Download Twitter customer support dataset from Kaggle.
    Requires kaggle API to be configured (~/.kaggle/kaggle.json)
    """
    try:
        import kaggle
        print(f"Downloading customer support dataset from Kaggle...")
        kaggle.api.dataset_download_files(
            'thoughtvector/customer-support-on-twitter',
            path=RAW_DATA_DIR,
            unzip=True
        )
        print(f"✓ Dataset downloaded to {RAW_DATA_DIR}")
    except Exception as e:
        print(f"⚠ Could not download via Kaggle API: {e}")
        print(f"Manual download: https://www.kaggle.com/thoughtvector/customer-support-on-twitter")
        return False
    return True


def load_twitter_data(csv_path: str) -> pd.DataFrame:
    """Load Twitter customer support CSV."""
    try:
        df = pd.read_csv(csv_path)
        print(f"✓ Loaded {len(df)} tweets from {csv_path}")
        return df
    except Exception as e:
        print(f"✗ Error loading data: {e}")
        return pd.DataFrame()


def filter_by_brand(df: pd.DataFrame, brand: str) -> pd.DataFrame:
    """Filter tweets for a specific brand."""
    # Assuming 'author_id' or 'brand' column exists
    if 'author_id' in df.columns:
        brand_df = df[df['author_id'].str.contains(brand, case=False, na=False)]
    elif 'inbound' in df.columns:
        # Some datasets have inbound (customer) vs outbound (brand) tweets
        brand_df = df[df['inbound'] == False]
    else:
        # Filter by text content mentioning the brand
        brand_df = df[df['text'].str.contains(brand, case=False, na=False)]
    
    return brand_df


def subsample_data(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """Randomly subsample data."""
    if len(df) > n:
        return df.sample(n=n, random_state=42)
    return df


def clean_tweet_text(text: str) -> str:
    """Basic text cleaning."""
    if not isinstance(text, str):
        return ""
    
    # Remove URLs
    text = ' '.join(word for word in text.split() if not word.startswith('http'))
    # Remove extra whitespace
    text = ' '.join(text.split())
    return text.strip()


def extract_threads(df: pd.DataFrame) -> List[List[Dict[str, Any]]]:
    """
    Extract conversation threads from tweets.
    Groups tweets by conversation ID if available.
    """
    threads = []
    
    if 'conversation_id' in df.columns:
        grouped = df.groupby('conversation_id')
        for conv_id, group in grouped:
            thread = []
            for _, row in group.sort_values('created_at').iterrows():
                thread.append({
                    'author': row.get('author_id', 'unknown'),
                    'text': clean_tweet_text(row.get('text', '')),
                    'timestamp': row.get('created_at', ''),
                    'is_inbound': row.get('inbound', True),
                })
            threads.append(thread)
    else:
        # If no conversation structure, treat each tweet as single-message "thread"
        for _, row in df.iterrows():
            threads.append([{
                'author': row.get('author_id', 'unknown'),
                'text': clean_tweet_text(row.get('text', '')),
                'timestamp': row.get('created_at', ''),
                'is_inbound': row.get('inbound', True),
            }])
    
    return threads


def save_processed_data(data: Any, filename: str):
    """Save processed data to JSON."""
    output_path = os.path.join(PROCESSED_DATA_DIR, filename)
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    print(f"✓ Saved to {output_path}")


def load_processed_data(filename: str) -> Any:
    """Load processed data from JSON."""
    filepath = os.path.join(PROCESSED_DATA_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return None


def prepare_sample_dataset(csv_path: str, brand: str, n_samples: int = 500) -> List[Dict]:
    """
    Main pipeline: load, filter, and prepare a sample dataset.
    
    Returns list of customer messages with minimal preprocessing.
    """
    df = load_twitter_data(csv_path)
    if df.empty:
        return []
    
    # Filter for brand
    brand_df = filter_by_brand(df, brand)
    print(f"✓ Found {len(brand_df)} tweets mentioning {brand}")
    
    # Subsample
    sample_df = subsample_data(brand_df, n_samples)
    print(f"✓ Subsampled to {len(sample_df)} tweets")
    
    # Extract customer messages (inbound = True or from customers)
    customer_messages = []
    for _, row in sample_df.iterrows():
        if row.get('inbound', True):  # Customer message
            customer_messages.append({
                'text': clean_tweet_text(row.get('text', '')),
                'author_id': row.get('author_id', ''),
                'timestamp': row.get('created_at', ''),
                'tweet_id': row.get('tweet_id', ''),
            })
    
    print(f"✓ Extracted {len(customer_messages)} customer messages")
    return customer_messages
