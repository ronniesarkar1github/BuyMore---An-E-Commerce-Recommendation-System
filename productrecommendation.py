# ============================================================
# SMART ECOMMERCE PRODUCT RECOMMENDATION SYSTEM
# ============================================================
# FEATURES
# ============================================================
# ✅ TF-IDF Recommendation
# ✅ Product Name Priority
# ✅ Category Priority
# ✅ Brand Matching
# ✅ Fuzzy Matching
# ✅ Synonym Matching
# ✅ Better Ecommerce Accuracy
# ✅ Recommendation Graph
# ✅ Lower RAM Usage
# ============================================================

import pandas as pd
import numpy as np
import re
import os
import threading
from datetime import datetime

from difflib import get_close_matches

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Import database connection (lazy init)
from core.database import init_db

# ============================================================
# LAZY / CACHED MODEL STATE
# ============================================================

_MODEL_LOCK = threading.Lock()
_MODEL_STATE = {
    "loaded": False,
    "loaded_at": None,
    "train_data": None,
    "name_col": None,
    "category_col": None,
    "brand_col": None,
    "desc_col": None,
    "tfidf": None,
    "tfidf_matrix": None,
    "cosine_sim": None,
}

def _debug_enabled():
    return (os.getenv("RECOMMENDER_DEBUG", "").strip().lower() in {"1", "true", "yes"})

def _log(msg: str):
    if _debug_enabled():
        print(msg)

def _load_products_dataframe(limit: int = 15000) -> pd.DataFrame:
    init_db()
    from core.database import products_collection

    if products_collection is None:
        return pd.DataFrame([])

    products_list = list(products_collection.find({}))
    df = pd.DataFrame(products_list)
    if df.empty:
        return df
    if limit and limit > 0:
        df = df.head(int(limit))
    return df

def _detect_columns(df: pd.DataFrame):
    columns = df.columns.tolist()

    def find_column(possible_names):
        for col in columns:
            for name in possible_names:
                if name.lower() in str(col).lower():
                    return col
        return None

    name_col = find_column(["product name", "product_name", "name", "title"])
    category_col = find_column(["category", "categories"])
    brand_col = find_column(["brand", "brands"])
    desc_col = find_column(["description", "desc", "details"])

    # Fall back to conventional names if detection failed
    if name_col is None and "name" in df.columns:
        name_col = "name"
    if category_col is None and "category" in df.columns:
        category_col = "category"
    if brand_col is None and "brand" in df.columns:
        brand_col = "brand"
    if desc_col is None and "description" in df.columns:
        desc_col = "description"

    return name_col, category_col, brand_col, desc_col

def _prepare_model(force_reload: bool = False) -> bool:
    """
    Loads products from MongoDB and builds TF-IDF + cosine similarity.
    Returns True if model is ready, else False.
    """
    with _MODEL_LOCK:
        cache_ttl = int(os.getenv("RECOMMENDER_CACHE_TTL_SECONDS", "0") or "0")
        if _MODEL_STATE["loaded"] and not force_reload:
            loaded_at = _MODEL_STATE.get("loaded_at")
            if cache_ttl > 0 and isinstance(loaded_at, datetime):
                age_seconds = (datetime.utcnow() - loaded_at).total_seconds()
                if age_seconds >= cache_ttl:
                    force_reload = True
            if not force_reload:
                return True

        limit = int(os.getenv("RECOMMENDER_MAX_PRODUCTS", "15000") or "15000")
        _log(f"[recommender] Loading products from MongoDB (limit={limit})...")

        df = _load_products_dataframe(limit=limit)
        if df.empty:
            _MODEL_STATE.update({
                "loaded": False,
                "train_data": pd.DataFrame([]),
                "name_col": None,
                "category_col": None,
                "brand_col": None,
                "desc_col": None,
                "tfidf": None,
                "tfidf_matrix": None,
                "cosine_sim": None,
            })
            return False

        name_col, category_col, brand_col, desc_col = _detect_columns(df)
        if name_col is None:
            _MODEL_STATE.update({
                "loaded": False,
                "train_data": pd.DataFrame([]),
                "name_col": None,
                "category_col": None,
                "brand_col": None,
                "desc_col": None,
                "tfidf": None,
                "tfidf_matrix": None,
                "cosine_sim": None,
            })
            return False

        # Ensure columns exist (missing ones become empty strings)
        for col in [name_col, category_col, brand_col, desc_col]:
            if col is None:
                continue
            df[col] = df[col].fillna("").astype(str)

        # Fill absent optional columns with empty strings
        if category_col is None:
            df["__category__"] = ""
            category_col = "__category__"
        if brand_col is None:
            df["__brand__"] = ""
            brand_col = "__brand__"
        if desc_col is None:
            df["__description__"] = ""
            desc_col = "__description__"

        df = df[df[name_col].astype(str).str.strip() != ""].copy()
        df = df.drop_duplicates(subset=[name_col]).reset_index(drop=True)

        df["CleanName"] = df[name_col].apply(clean_text)
        df["CleanCategory"] = df[category_col].apply(clean_text)
        df["CleanBrand"] = df[brand_col].apply(clean_text)
        df["CleanDescription"] = df[desc_col].apply(clean_text)

        df["Tags"] = (
            df["CleanName"] + " " +
            df["CleanName"] + " " +
            df["CleanName"] + " " +
            df["CleanCategory"] + " " +
            df["CleanCategory"] + " " +
            df["CleanBrand"] + " " +
            df["CleanDescription"]
        )

        tfidf = TfidfVectorizer(
            stop_words="english",
            max_features=4000,
            ngram_range=(1, 2)
        )
        tfidf_matrix = tfidf.fit_transform(df["Tags"])
        cosine_sim = cosine_similarity(tfidf_matrix)

        _MODEL_STATE.update({
            "loaded": True,
            "loaded_at": datetime.utcnow(),
            "train_data": df,
            "name_col": name_col,
            "category_col": category_col,
            "brand_col": brand_col,
            "desc_col": desc_col,
            "tfidf": tfidf,
            "tfidf_matrix": tfidf_matrix,
            "cosine_sim": cosine_sim,
        })
        _log(f"[recommender] Model ready with {len(df)} products.")
        return True

# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text):

    text = str(text).lower()

    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()

# ============================================================
# SYNONYM DICTIONARY
# ============================================================

synonym_map = {

    "shoe": ["shoes", "sneaker", "footwear", "running"],
    "shoes": ["shoe", "sneaker", "footwear"],
    "glove": ["gloves", "winter", "hand"],
    "gloves": ["glove", "winter", "hand"],
    "car": ["automotive", "vehicle", "auto"],
    "rice": ["food", "grain", "basmati"],
    "tv": ["television", "smarttv"],
    "phone": ["mobile", "smartphone"],
    "laptop": ["notebook", "computer"],
    "chair": ["office", "furniture", "seat"],
    "table": ["desk", "furniture"],
    "bed": ["bedroom", "mattress"],
    "watch": ["smartwatch", "wearable"],
    "headphone": ["earbuds", "audio"],
    "sandal": ["footwear", "slipper", "shoe"]
}

# ============================================================
# NOTE
# ============================================================
# Model training/data load is performed lazily via _prepare_model()

# ============================================================
# SMART PRODUCT MATCHING
# ============================================================

def find_best_match(user_input):

    user_input = clean_text(user_input)

    user_words = user_input.split()

    # ========================================================
    # ADD SYNONYMS
    # ========================================================

    expanded_words = list(user_words)

    for word in user_words:

        if word in synonym_map:
            expanded_words.extend(synonym_map[word])

    expanded_words = list(set(expanded_words))

    exact_matches = []

    partial_matches = []

    fuzzy_candidates = []

    train_data = _MODEL_STATE.get("train_data")
    if train_data is None or train_data.empty:
        return None

    for idx, row in train_data.iterrows():

        product_name = row.get("CleanName", "")
        category_name = row.get("CleanCategory", "")

        combined_text = product_name + " " + category_name

        product_words = combined_text.split()

        # ====================================================
        # EXACT MATCH
        # ====================================================

        if user_input == product_name:
            exact_matches.append(idx)

        # ====================================================
        # WORD MATCH
        # ====================================================

        elif any(word in product_words for word in expanded_words):
            partial_matches.append(idx)

        # ====================================================
        # FUZZY MATCH
        # ====================================================

        else:

            fuzzy = get_close_matches(
                user_input,
                product_words,
                n=1,
                cutoff=0.80
            )

            if fuzzy:
                fuzzy_candidates.append(idx)

    if exact_matches:
        return exact_matches[0]

    if partial_matches:
        return partial_matches[0]

    if fuzzy_candidates:
        return fuzzy_candidates[0]

    return None

# ============================================================
# RECOMMEND PRODUCTS
# ============================================================

def recommend_products(user_input, top_n=5):

    # Optional CLI helper; ensure model is loaded.
    if not _prepare_model():
        print("Recommendation model is not available (no products loaded).")
        return

    # matplotlib is only needed for the CLI graph.
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        plt = None

    selected_index = find_best_match(user_input)

    if selected_index is None:

        print("\nNo product found.\n")
        return

    train_data = _MODEL_STATE["train_data"]
    name_col = _MODEL_STATE["name_col"]
    cosine_sim = _MODEL_STATE["cosine_sim"]

    selected_product = train_data.iloc[selected_index]

    selected_name = selected_product[name_col]

    selected_category = selected_product["CleanCategory"]

    selected_brand = selected_product["CleanBrand"]

    print("\n================================================")
    print("\nSELECTED PRODUCT:")
    print(selected_name)

    # ========================================================
    # GET SIMILARITY SCORES
    # ========================================================

    similarity_scores = list(
        enumerate(cosine_sim[selected_index])
    )

    boosted_scores = []

    for idx, score in similarity_scores:

        category_bonus = 0

        current_category = train_data.iloc[idx]["CleanCategory"]

        current_brand = train_data.iloc[idx]["CleanBrand"]

        # ====================================================
        # CATEGORY BOOST
        # ====================================================

        if current_category == selected_category:
            category_bonus += 0.35

        # ====================================================
        # BRAND BOOST
        # ====================================================

        if current_brand == selected_brand:
            category_bonus += 0.15

        final_score = score + category_bonus

        boosted_scores.append((idx, final_score))

    # ========================================================
    # SORT
    # ========================================================

    boosted_scores = sorted(
        boosted_scores,
        key=lambda x: x[1],
        reverse=True
    )

    # remove same product
    boosted_scores = [
        item for item in boosted_scores
        if item[0] != selected_index
    ]

    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================

    final_recommendations = []

    used_names = set()

    for idx, score in boosted_scores:

        pname = train_data.iloc[idx][name_col]

        if pname in used_names:
            continue

        used_names.add(pname)

        final_recommendations.append((idx, score))

        if len(final_recommendations) >= top_n:
            break

    # ========================================================
    # PRINT RESULTS
    # ========================================================

    print("\n================================================")
    print("\nRECOMMENDED PRODUCTS")
    print("================================================\n")

    graph_names = []

    graph_scores = []

    for idx, score in final_recommendations:

        pname = train_data.iloc[idx][name_col]

        print("Product :", pname)

        print("Hybrid Score :", round(score, 4))

        print("-" * 60)

        short_name = pname[:40]

        graph_names.append(short_name)

        graph_scores.append(score)

    # ========================================================
    # GRAPH
    # ========================================================

    if plt is None:
        return

    plt.figure(figsize=(14, 7))

    bars = plt.barh(graph_names, graph_scores)

    plt.xlabel("Recommendation Score")

    plt.ylabel("Products")

    plt.title(
        f"Recommended Products For: {selected_name[:50]}"
    )

    plt.gca().invert_yaxis()

    for bar in bars:

        width = bar.get_width()

        plt.text(
            width + 0.01,
            bar.get_y() + bar.get_height()/2,
            f"{width:.2f}",
            va='center'
        )

    plt.tight_layout()

    plt.show()

# ============================================================
# API FUNCTION FOR RECOMMENDATIONS
# ============================================================

def get_recommendations_for_product(product_name, top_n=5):
    """
    Get recommendations for a given product name.
    Returns a list of recommended products with scores.
    """
    if not _prepare_model():
        return []

    selected_index = find_best_match(product_name)

    if selected_index is None:
        return []

    train_data = _MODEL_STATE["train_data"]
    name_col = _MODEL_STATE["name_col"]
    cosine_sim = _MODEL_STATE["cosine_sim"]

    selected_product = train_data.iloc[selected_index]
    selected_name = selected_product[name_col]

    def _extract_display_tags(row) -> list:
        tokens = []
        for key in ["CleanCategory", "CleanBrand", "CleanName"]:
            value = row.get(key, "")
            if not isinstance(value, str):
                value = str(value or "")
            tokens.extend(value.split())

        stop = {
            "and", "or", "the", "a", "an", "for", "with", "to", "in", "on", "of",
            "by", "from", "new", "latest", "best", "quality", "original"
        }
        cleaned = []
        seen = set()
        for t in tokens:
            t = clean_text(t)
            if not t or t in stop:
                continue
            if t in seen:
                continue
            seen.add(t)
            cleaned.append(t)

        # Prefer fewer, more meaningful tags
        return cleaned[:12]

    selected_tags = set(_extract_display_tags(selected_product))

    # Get similarity scores
    similarity_scores = list(
        enumerate(cosine_sim[selected_index])
    )

    boosted_scores = []

    for idx, score in similarity_scores:

        category_bonus = 0

        current_category = train_data.iloc[idx].get("CleanCategory", "")
        current_brand = train_data.iloc[idx].get("CleanBrand", "")

        # Category boost
        if current_category == selected_product["CleanCategory"]:
            category_bonus += 0.35

        # Brand boost
        if current_brand == selected_product["CleanBrand"]:
            category_bonus += 0.15

        final_score = score + category_bonus

        boosted_scores.append((idx, final_score))

    # Sort
    boosted_scores = sorted(
        boosted_scores,
        key=lambda x: x[1],
        reverse=True
    )

    # Remove same product
    boosted_scores = [
        item for item in boosted_scores
        if item[0] != selected_index
    ]

    # Remove duplicates
    final_recommendations = []

    used_names = set()

    for idx, score in boosted_scores:

        pname = train_data.iloc[idx][name_col]

        if pname in used_names:
            continue

        used_names.add(pname)

        # Get the full product data
        product_data = train_data.iloc[idx].to_dict()
        matched = []
        try:
            candidate_tags = set(_extract_display_tags(train_data.iloc[idx]))
            matched = sorted(selected_tags.intersection(candidate_tags))
        except Exception:
            matched = []

        final_recommendations.append({
            "product": product_data,
            "score": round(score, 4),
            "reason": f"Similar to {selected_name}",
            "matched_tags": matched[:5],
        })

        if len(final_recommendations) >= top_n:
            break

    return final_recommendations

def reload_recommendation_model() -> bool:
    """
    Force reloading products from MongoDB and rebuilding the model.
    Useful after bulk updates to the products collection.
    """
    return _prepare_model(force_reload=True)

def ensure_recommendation_model_loaded() -> bool:
    """
    Ensures the recommendation model is loaded (no force reload).
    Intended to be called during app startup so the first user request
    doesn't pay the model build cost.
    """
    return _prepare_model(force_reload=False)

# ============================================================
# INITIALIZE MODEL ON IMPORT
# ============================================================

# This will run when the module is imported
if __name__ == "__main__":
    # Test the system
    while True:
        print("\n================================================")
        user_input = input("\nEnter Product Name (or type exit): ")

        if user_input.lower() == "exit":
            print("\nExiting Recommendation System...\n")
            break

        recommend_products(user_input)
