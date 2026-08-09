import re
import os
from dotenv import load_dotenv

load_dotenv(override=True)

TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PASSWORD_SPECIAL_RE = re.compile(r"[!@#$%^&*()_\-+=\[\]{}|\\:;\"'<>,.?/`~]")

CATEGORY_TERM_ALIASES = {
    "electronics": {"electronics", "electronic", "tech", "device", "devices"},
    "fashion": {"fashion", "style", "apparel", "clothing", "outfit"},
    "furniture": {"furniture", "decor", "sofa", "table", "chair"},
    "gadgets": {"gadgets", "gadget", "portable", "accessory", "accessories"},
    "homeappliances": {"homeappliances", "appliances", "appliance", "kitchen", "refrigerator", "washer"}
}

CONTENT_QUERY_SCORE_THRESHOLD = 0.22
SEARCH_MIN_CONTENT_SCORE = 0.05
COMPLEMENTARY_MIN_RESULTS = 2
ASSOCIATION_MIN_SUPPORT = float(os.getenv("ASSOCIATION_MIN_SUPPORT", "0.01"))
ASSOCIATION_MIN_CONFIDENCE = float(os.getenv("ASSOCIATION_MIN_CONFIDENCE", "0.08"))
ASSOCIATION_MAX_RULES_PER_PRODUCT = int(os.getenv("ASSOCIATION_MAX_RULES_PER_PRODUCT", "12"))

SEARCH_RANK_WEIGHTS = {
    "relevance": 0.56,
    "popularity": 0.2,
    "rating": 0.16,
    "reviews": 0.08
}

TODAYS_DEALS_MIN_DISCOUNT = int(os.getenv("TODAYS_DEALS_MIN_DISCOUNT", "10"))
TODAYS_DEALS_MAX_DISCOUNT = int(os.getenv("TODAYS_DEALS_MAX_DISCOUNT", "35"))
TODAYS_DEALS_DEFAULT_LIMIT = int(os.getenv("TODAYS_DEALS_DEFAULT_LIMIT", "8"))

INTERACTION_EVENT_TYPES = {"view", "click", "cart_add", "purchase"}
INTERACTION_EVENT_PROFILE_WEIGHTS = {
    "view": 0.45,
    "click": 0.75,
    "cart_add": 2.1,
    "purchase": 4.5
}
INTERACTION_EVENT_POPULARITY_WEIGHTS = {
    "view": 0.12,
    "click": 0.35,
    "cart_add": 1.4,
    "purchase": 3.2
}
INTERACTION_EVENT_MATRIX_WEIGHTS = {
    "view": 0.2,
    "click": 0.4,
    "cart_add": 2.5,
    "purchase": 4.2
}

RECOMMENDER_SNAPSHOT_TTL_SECONDS = int(os.getenv("RECOMMENDER_SNAPSHOT_TTL_SECONDS", "300"))

# Sentiment Analysis Configuration
SENTIMENT_TASK = "sentiment-analysis"
SENTIMENT_MODEL_PATH = "./bert_sentiment_model"
