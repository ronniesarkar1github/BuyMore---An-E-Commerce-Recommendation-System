from collections import Counter, defaultdict
from math import sqrt, log
from itertools import combinations
from datetime import datetime
import core.database as db_layer

from core.utils import normalize_text_value
from core.constants import (
    TOKEN_SPLIT_RE, CATEGORY_TERM_ALIASES, CONTENT_QUERY_SCORE_THRESHOLD,
    SEARCH_MIN_CONTENT_SCORE, COMPLEMENTARY_MIN_RESULTS,
    ASSOCIATION_MIN_SUPPORT, ASSOCIATION_MIN_CONFIDENCE,
    ASSOCIATION_MAX_RULES_PER_PRODUCT, SEARCH_RANK_WEIGHTS,
    TODAYS_DEALS_MIN_DISCOUNT, TODAYS_DEALS_MAX_DISCOUNT,
    TODAYS_DEALS_DEFAULT_LIMIT, INTERACTION_EVENT_PROFILE_WEIGHTS,
    INTERACTION_EVENT_POPULARITY_WEIGHTS, INTERACTION_EVENT_MATRIX_WEIGHTS,
    RECOMMENDER_SNAPSHOT_TTL_SECONDS
)

recommender_state = {
    "snapshot": None,
    "dirty": True
}

import os
from core.constants import (
    SENTIMENT_MODEL_PATH, SENTIMENT_TASK
)

sentiment_pipeline = None
sentiment_error = None

def get_sentiment_pipeline():
    global sentiment_pipeline, sentiment_error
    if sentiment_pipeline is not None:
        return sentiment_pipeline
    if sentiment_error is not None:
        return None
    if not os.path.exists(SENTIMENT_MODEL_PATH):
        sentiment_error = f"Model path not found: {SENTIMENT_MODEL_PATH}"
        return None
    try:
        from transformers import pipeline
        sentiment_pipeline = pipeline(SENTIMENT_TASK, model=SENTIMENT_MODEL_PATH)
        return sentiment_pipeline
    except Exception as e:
        sentiment_error = str(e)
        return None

def analyze_sentiment_text(text, rating=None):
    pipe = get_sentiment_pipeline()
    if pipe is None:
        return fallback_sentiment_from_rating(rating)
    try:
        result = pipe(text)
        if isinstance(result, list):
            result = result[0] if result else {}
        raw_label = (result.get("label") or result.get("sentiment") or "unknown")
        label = str(raw_label)
        label_lower = label.lower()
        if "pos" in label_lower:
            label = "positive"
        elif "neg" in label_lower:
            label = "negative"
        elif "neu" in label_lower:
            label = "neutral"
        elif label_lower.startswith("label_"):
            try:
                idx = int(label_lower.split("_", 1)[1])
                if idx == 0:
                    label = "negative"
                elif idx == 1:
                    label = "neutral"
                elif idx == 2:
                    label = "positive"
            except ValueError:
                pass
        else:
            digits = [c for c in label_lower if c.isdigit()]
            if digits:
                try:
                    score_num = int(digits[0])
                    if score_num <= 2:
                        label = "negative"
                    elif score_num == 3:
                        label = "neutral"
                    else:
                        label = "positive"
                except ValueError:
                    pass
        score = result.get("score")
        payload = {
            "label": label,
            "score": round(float(score), 4) if score is not None else None
        }
        return payload
    except Exception:
        return fallback_sentiment_from_rating(rating)

def fallback_sentiment_from_rating(rating):

    if rating is None:
        return None
    try:
        rating_val = int(rating)
    except (TypeError, ValueError):
        return None
    if rating_val <= 2:
        label = "negative"
    elif rating_val == 3:
        label = "neutral"
    else:
        label = "positive"
    return {"label": label, "score": None}

def tokenize_text(*parts):
    tokens = []
    for part in parts:
        if not part:
            continue
        split_tokens = TOKEN_SPLIT_RE.split(str(part).lower())
        tokens.extend(token for token in split_tokens if len(token) > 2)
    return set(tokens)

def get_product_catalog():
    if db_layer.products_collection is None:
        return []
    return list(db_layer.products_collection.find({}))


def get_product_map():
    return {product.get("name"): product for product in get_product_catalog() if product.get("name")}

def get_product_review_stats(product_names=None):
    if db_layer.reviews_collection is None:
        return {}
    match_stage = {}
    names = [str(name).strip() for name in (product_names or []) if str(name or "").strip()]
    if names:
        match_stage = {"product_name": {"$in": list(set(names))}}
    pipeline = []
    if match_stage:
        pipeline.append({"$match": match_stage})
    pipeline.append({
        "$group": {
            "_id": "$product_name",
            "avg_rating": {"$avg": "$rating"},
            "count": {"$sum": 1}
        }
    })
    try:
        return {
            item.get("_id"): {
                "rating": round(float(item.get("avg_rating") or 0), 1),
                "review_count": int(item.get("count") or 0)
            }
            for item in db_layer.reviews_collection.aggregate(pipeline)
            if item.get("_id")
        }
    except Exception:
        return {}

def apply_product_review_stats(product, review_stats=None):
    if not product:
        return None
    product_copy = dict(product)
    product_name = str(product_copy.get("name") or "").strip()
    stats = (review_stats or {}).get(product_name)
    if review_stats is None and product_name:
        stats = get_product_review_stats([product_name]).get(product_name)
    if stats:
        product_copy["rating"] = stats.get("rating", 0.0)
        product_copy["review_count"] = stats.get("review_count", 0)
    else:
        product_copy["rating"] = 0.0
        product_copy["review_count"] = 0
    return product_copy

def get_product_rating_value(product):
    if get_product_review_count(product) == 0:
        return 0.0
    try:
        return max(0.0, min(float((product or {}).get("rating") or 0), 5.0))
    except (TypeError, ValueError):
        return 0.0

def get_product_review_count(product):
    try:
        return max(0, int((product or {}).get("review_count") or 0))
    except (TypeError, ValueError):
        return 0

def get_product_quality_score(product):
    rating_norm = get_product_rating_value(product) / 5.0
    review_confidence = min(get_product_review_count(product), 50) / 50.0
    return round((rating_norm * 0.8) + (review_confidence * 0.2), 4)

def get_product_brand_value(product):
    return normalize_text_value((product or {}).get("brand"))

def get_category_content_terms(category):
    normalized = normalize_text_value(category).replace(" ", "")
    if not normalized:
        return set()
    terms = set(tokenize_text(normalized))
    if normalized in CATEGORY_TERM_ALIASES:
        terms.update(CATEGORY_TERM_ALIASES[normalized])
    if normalized == "homeappliances":
        terms.update({"home", "appliances", "appliance"})
    terms.add(normalized)
    return {term for term in terms if term}

def get_product_tags(product):
    tags = (product or {}).get("tags")
    normalized_tags = []

    if isinstance(tags, (list, tuple, set)):
        for tag in tags:
            normalized = normalize_text_value(tag)
            if normalized:
                normalized_tags.append(normalized)

    if normalized_tags:
        return list(dict.fromkeys(normalized_tags))

    derived = []
    derived.extend(sorted(tokenize_text((product or {}).get("name"), (product or {}).get("brand"))))
    derived.extend(sorted(get_category_content_terms((product or {}).get("category"))))
    derived.extend(sorted(tokenize_text((product or {}).get("description"))))

    unique_tags = []
    seen = set()
    for tag in derived:
        normalized = normalize_text_value(tag)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_tags.append(normalized)
        if len(unique_tags) >= 8:
            break
    return unique_tags

def format_category_label(category):
    value = normalize_text_value(category)
    if value == "homeappliances":
        return "home appliances"
    return value

def recompute_product_rating(product_name):
    if db_layer.reviews_collection is None or db_layer.products_collection is None:
        return
    agg = list(db_layer.reviews_collection.aggregate([
        {"$match": {"product_name": product_name}},
        {"$group": {"_id": "$product_name", "avg_rating": {"$avg": "$rating"}, "count": {"$sum": 1}}}
    ]))
    if agg:
        avg_rating = float(agg[0].get("avg_rating") or 0)
        review_count = int(agg[0].get("count") or 0)
        db_layer.products_collection.update_one(
            {"name": product_name},
            {"$set": {"rating": round(avg_rating, 1), "review_count": review_count}}
        )


def sort_products_by_rating(products, group_by_category=False):
    items = list(products or [])
    if group_by_category:
        items.sort(
            key=lambda product: (
                (product.get("category") or "").strip().lower(),
                -get_product_rating_value(product),
                -get_product_review_count(product),
                (product.get("name") or "").strip().lower()
            )
        )
        return items

    items.sort(
        key=lambda product: (
            -get_product_rating_value(product),
            -get_product_review_count(product),
            (product.get("name") or "").strip().lower()
        )
    )
    return items

def add_weighted_tokens(weights, parts, weight):

    for part in parts:
        if not part:
            continue
        for token in tokenize_text(part):
            weights[token] += weight

def get_price_bucket_label(price):
    try:
        price_value = float(price or 0)
    except (TypeError, ValueError):
        return None
    if price_value <= 0:
        return None
    if price_value <= 2500:
        return "budget"
    if price_value <= 8000:
        return "value"
    if price_value <= 20000:
        return "midrange"
    return "premium"

def get_rating_bucket_label(rating):
    try:
        rating_value = float(rating or 0)
    except (TypeError, ValueError):
        return None
    if rating_value >= 4.5:
        return "toprated"
    if rating_value >= 4.0:
        return "highrated"
    if rating_value >= 3.0:
        return "wellrated"
    if rating_value > 0:
        return "developing"
    return None

def get_product_content_weights(product):
    weights = Counter()
    if not product:
        return weights

    add_weighted_tokens(weights, [product.get("name")], 3.2)
    add_weighted_tokens(weights, [product.get("brand")], 2.4)
    add_weighted_tokens(weights, [product.get("description")], 1.5)
    add_weighted_tokens(weights, get_product_tags(product), 2.0)

    for term in get_category_content_terms(product.get("category")):
        weights[term] += 2.6

    price_bucket = get_price_bucket_label((product or {}).get("price"))
    if price_bucket:
        weights[price_bucket] += 0.9

    rating_bucket = get_rating_bucket_label(get_product_rating_value(product))
    if rating_bucket:
        weights[rating_bucket] += 0.7

    return weights

def build_query_content_weights(query_text):
    weights = Counter()
    query_value = normalize_text_value(query_text)
    if not query_value:
        return weights

    add_weighted_tokens(weights, [query_value], 3.0)
    compact_query = TOKEN_SPLIT_RE.sub("", query_value)

    for category, terms in CATEGORY_TERM_ALIASES.items():
        if category in compact_query or tokenize_text(query_value).intersection(terms):
            for term in terms:
                weights[term] += 2.2

    return weights

def get_top_content_overlap(source_weights, target_weights, limit=3):
    scored_terms = []
    for token, source_weight in source_weights.items():
        target_weight = float(target_weights.get(token, 0) or 0)
        if target_weight > 0:
            scored_terms.append((token, float(source_weight) * target_weight))
    scored_terms.sort(key=lambda item: item[1], reverse=True)
    return [token for token, _score in scored_terms[:limit]]

def get_normalized_counter_score(counter, key):
    if not counter or not key:
        return 0.0
    top_value = float(counter.most_common(1)[0][1] or 0)
    if top_value <= 0:
        return 0.0
    return min(float(counter.get(key, 0) or 0) / top_value, 1.0)

def get_keyword_preference_match(keyword_preferences, product):
    if not keyword_preferences:
        return 0.0
    product_weights = get_product_content_weights(product)
    top_value = float(keyword_preferences.most_common(1)[0][1] or 0)
    if top_value <= 0:
        return 0.0
    overlap_scores = []
    for token, product_weight in product_weights.items():
        preference_weight = float(keyword_preferences.get(token, 0) or 0)
        if preference_weight > 0:
            overlap_scores.append(min(preference_weight, top_value) * min(float(product_weight), 3.5))
    if not overlap_scores:
        return 0.0
    overlap_scores.sort(reverse=True)
    return min(sum(overlap_scores[:5]) / (top_value * 8.0), 1.4)

def get_price_preference_match(price_points, product):
    if not price_points:
        return 0.0
    try:
        candidate_price = float((product or {}).get("price") or 0)
    except (TypeError, ValueError):
        return 0.0
    if candidate_price <= 0:
        return 0.0
    avg_price = sum(float(point) for point in price_points) / max(len(price_points), 1)
    gap = abs(avg_price - candidate_price) / max(avg_price, candidate_price, 1.0)
    return max(0.0, 1.0 - gap)

def build_tfidf_vector(term_weights, idf_map, default_idf):
    vector = {}
    for token, weight in (term_weights or {}).items():
        try:
            tf_value = float(weight or 0)
        except (TypeError, ValueError):
            tf_value = 0.0
        if tf_value <= 0:
            continue
        vector[token] = (1.0 + log(1.0 + tf_value)) * float(idf_map.get(token, default_idf))
    return vector

def sparse_cosine_similarity(vec_a, vec_b):
    if not vec_a or not vec_b:
        return 0.0

    left = vec_a
    right = vec_b
    if len(left) > len(right):
        left, right = right, left

    dot = 0.0
    for token, value in left.items():
        dot += float(value) * float(right.get(token, 0.0))

    mag_left = sqrt(sum(float(value) * float(value) for value in vec_a.values()))
    mag_right = sqrt(sum(float(value) * float(value) for value in vec_b.values()))
    if mag_left == 0 or mag_right == 0:
        return 0.0
    return dot / (mag_left * mag_right)

def build_tfidf_model(catalog):
    product_documents = {}
    document_frequencies = Counter()

    for product in catalog or []:
        product_name = (product or {}).get("name")
        if not product_name:
            continue
        term_weights = get_product_content_weights(product)
        product_documents[product_name] = term_weights
        for token in term_weights.keys():
            document_frequencies[token] += 1

    total_docs = max(len(product_documents), 1)
    idf_map = {}
    for token, doc_freq in document_frequencies.items():
        idf_map[token] = 1.0 + log((1.0 + total_docs) / (1.0 + float(doc_freq)))
    default_idf = 1.0 + log(1.0 + total_docs)

    product_vectors = {}
    for product_name, term_weights in product_documents.items():
        product_vectors[product_name] = build_tfidf_vector(term_weights, idf_map, default_idf)

    return {
        "idf": idf_map,
        "default_idf": default_idf,
        "product_vectors": product_vectors
    }

def get_product_tfidf_vector(product, tfidf_model):
    product_name = (product or {}).get("name")
    if product_name and product_name in tfidf_model.get("product_vectors", {}):
        return tfidf_model["product_vectors"][product_name]
    return build_tfidf_vector(
        get_product_content_weights(product),
        tfidf_model.get("idf", {}),
        tfidf_model.get("default_idf", 1.0)
    )

def build_query_tfidf_vector(query_text, tfidf_model):
    return build_tfidf_vector(
        build_query_content_weights(query_text),
        tfidf_model.get("idf", {}),
        tfidf_model.get("default_idf", 1.0)
    )

def build_user_tfidf_profile_vector(activity_summary, product_map, tfidf_model):
    if not activity_summary or not activity_summary["name_weights"]:
        return None

    profile = defaultdict(float)
    total_weight = 0.0

    for product_name, weight in activity_summary["name_weights"].items():
        if product_name in activity_summary.get("negative_products", set()):
            continue
        product = product_map.get(product_name)
        if not product:
            continue
        product_vector = get_product_tfidf_vector(product, tfidf_model)
        if not product_vector:
            continue
        numeric_weight = float(weight or 0)
        if numeric_weight <= 0:
            continue
        for token, value in product_vector.items():
            profile[token] += float(value) * numeric_weight
        total_weight += numeric_weight

    if total_weight <= 0:
        return None
    return {token: (value / total_weight) for token, value in profile.items() if value}

def is_product_available(product):
    if not product:
        return False
    stock = product.get("stock")
    if stock is None:
        return True
    try:
        return int(stock) > 0
    except (TypeError, ValueError):
        return False

def normalize_interaction_event_type(event_type):
    normalized = normalize_text_value(event_type)
    if normalized in {"view", "views", "product_view", "impression"}:
        return "view"
    if normalized in {"click", "clicks", "product_click"}:
        return "click"
    if normalized in {"cart_add", "add_to_cart", "cart"}:
        return "cart_add"
    if normalized in {"purchase", "order", "ordered", "buy"}:
        return "purchase"
    return "click"

def get_user_activity_summary(user_id):
    summary = {
        "name_weights": Counter(),
        "category_preferences": Counter(),
        "brand_preferences": Counter(),
        "price_points": [],
        "keyword_preferences": Counter(),
        "positive_products": set(),
        "negative_products": set()
    }
    if not user_id:
        return summary

    product_map = get_product_map()

    def add_signal(product_name, weight, positive=None):
        if not product_name or weight <= 0:
            return
        product = product_map.get(product_name)
        if not product:
            return
        summary["name_weights"][product_name] += weight
        category = (product.get("category") or "").strip().lower()
        if category:
            summary["category_preferences"][category] += weight
        brand = get_product_brand_value(product)
        if brand:
            summary["brand_preferences"][brand] += weight
        try:
            price = float(product.get("price") or 0)
            if price > 0:
                summary["price_points"].append(price)
        except (TypeError, ValueError):
            pass
        for token, token_weight in get_product_content_weights(product).items():
            summary["keyword_preferences"][token] += weight * float(token_weight)
        if positive is True:
            summary["positive_products"].add(product_name)
        elif positive is False:
            summary["negative_products"].add(product_name)

    if db_layer.cart_collection is not None:
        cart = db_layer.cart_collection.find_one({"user_id": user_id}) or {}
        for item in cart.get("items", []):
            quantity = max(1, int((item or {}).get("quantity", 1) or 1))
            add_signal((item or {}).get("name"), 3 + min(quantity, 4), positive=True)

    if db_layer.wishlist_collection is not None:
        wishlist = db_layer.wishlist_collection.find_one({"user_id": user_id}) or {}
        for item in wishlist.get("items", []):
            add_signal((item or {}).get("name"), 2.5, positive=True)

    if db_layer.reviews_collection is not None:
        for review in db_layer.reviews_collection.find({"user_id": user_id}):
            product_name = review.get("product_name")
            try:
                rating = int(review.get("rating") or 0)
            except (TypeError, ValueError):
                rating = 0
            if rating >= 4:
                add_signal(product_name, 4.5 + max(rating - 4, 0), positive=True)
            elif rating == 3:
                add_signal(product_name, 1.5, positive=None)
            elif rating > 0:
                add_signal(product_name, 0.5, positive=False)

    if db_layer.orders_collection is not None:
        for order in db_layer.orders_collection.find({"user_id": user_id}):
            for item in order.get("items", []):
                product_name = (item or {}).get("name")
                try:
                    quantity = max(1, int((item or {}).get("quantity", 1) or 1))
                except (TypeError, ValueError):
                    quantity = 1
                add_signal(product_name, 5.0 + min(quantity, 4), positive=True)

    if db_layer.click_events_collection is not None:
        for event in db_layer.click_events_collection.find({"user_id": user_id}).sort("created_at", -1).limit(200):
            event_type = normalize_interaction_event_type(event.get("event_type"))
            base_weight = float(INTERACTION_EVENT_PROFILE_WEIGHTS.get(event_type, 0.75))
            try:
                quantity = max(1, int(event.get("quantity") or 1))
            except (TypeError, ValueError):
                quantity = 1
            quantity_multiplier = 1.0
            if event_type in {"cart_add", "purchase"}:
                quantity_multiplier = 1.0 + min(quantity, 5) * 0.35

            positive = True if event_type in {"cart_add", "purchase"} else None
            add_signal(
                event.get("product_name"),
                base_weight * quantity_multiplier,
                positive=positive
            )


    return summary

def get_popularity_scores():
    popularity = Counter()

    if db_layer.cart_collection is not None:
        for cart in db_layer.cart_collection.find({}):
            for item in cart.get("items", []):
                name = (item or {}).get("name")
                if name:
                    popularity[name] += max(1, int((item or {}).get("quantity", 1) or 1)) * 1.4

    if db_layer.wishlist_collection is not None:
        for wishlist in db_layer.wishlist_collection.find({}):
            for item in wishlist.get("items", []):
                name = (item or {}).get("name")
                if name:
                    popularity[name] += 1.2

    if db_layer.reviews_collection is not None:
        for review in db_layer.reviews_collection.find({}):
            name = review.get("product_name")
            if not name:
                continue
            try:
                rating = int(review.get("rating") or 0)
            except (TypeError, ValueError):
                rating = 0
            popularity[name] += max(rating, 1) * 0.8

    if db_layer.orders_collection is not None:
        for order in db_layer.orders_collection.find({}):
            for item in order.get("items", []):
                name = (item or {}).get("name")
                if not name:
                    continue
                try:
                    quantity = max(1, int((item or {}).get("quantity", 1) or 1))
                except (TypeError, ValueError):
                    quantity = 1
                popularity[name] += quantity * 3.5

    if db_layer.click_events_collection is not None:
        for event in db_layer.click_events_collection.find({}):
            name = event.get("product_name")
            if not name:
                continue
            event_type = normalize_interaction_event_type(event.get("event_type"))
            base_weight = float(INTERACTION_EVENT_POPULARITY_WEIGHTS.get(event_type, 0.35))
            try:
                quantity = max(1, int(event.get("quantity") or 1))
            except (TypeError, ValueError):
                quantity = 1
            quantity_multiplier = 1.0 + (min(quantity, 5) * 0.3) if event_type in {"cart_add", "purchase"} else 1.0
            popularity[name] += base_weight * quantity_multiplier


    return popularity

def build_user_interaction_matrix():
    interaction_matrix = defaultdict(Counter)

    if db_layer.cart_collection is not None:
        for cart in db_layer.cart_collection.find({}):
            user_id = cart.get("user_id")
            if not user_id:
                continue
            for item in cart.get("items", []):
                product_name = (item or {}).get("name")
                if not product_name:
                    continue
                try:
                    quantity = max(1, int((item or {}).get("quantity", 1) or 1))
                except (TypeError, ValueError):
                    quantity = 1
                interaction_matrix[user_id][product_name] += 2.5 + min(quantity, 4)

    if db_layer.wishlist_collection is not None:
        for wishlist in db_layer.wishlist_collection.find({}):
            user_id = wishlist.get("user_id")
            if not user_id:
                continue
            for item in wishlist.get("items", []):
                product_name = (item or {}).get("name")
                if product_name:
                    interaction_matrix[user_id][product_name] += 2.0

    if db_layer.reviews_collection is not None:
        for review in db_layer.reviews_collection.find({}):
            user_id = review.get("user_id")
            product_name = review.get("product_name")
            if not user_id or not product_name:
                continue
            try:
                rating = int(review.get("rating") or 0)
            except (TypeError, ValueError):
                rating = 0
            if rating >= 4:
                interaction_matrix[user_id][product_name] += 3.0 + ((rating - 3) * 1.2)
            elif rating == 3:
                interaction_matrix[user_id][product_name] += 1.0

    if db_layer.orders_collection is not None:
        for order in db_layer.orders_collection.find({}):
            user_id = order.get("user_id")
            if not user_id:
                continue
            for item in order.get("items", []):
                product_name = (item or {}).get("name")
                if not product_name:
                    continue
                try:
                    quantity = max(1, int((item or {}).get("quantity", 1) or 1))
                except (TypeError, ValueError):
                    quantity = 1
                interaction_matrix[user_id][product_name] += 4.5 + min(quantity, 5)

    if db_layer.click_events_collection is not None:
        for event in db_layer.click_events_collection.find({}):
            user_id = event.get("user_id")
            product_name = event.get("product_name")
            if user_id and product_name:
                event_type = normalize_interaction_event_type(event.get("event_type"))
                base_weight = float(INTERACTION_EVENT_MATRIX_WEIGHTS.get(event_type, 0.4))
                try:
                    quantity = max(1, int(event.get("quantity") or 1))
                except (TypeError, ValueError):
                    quantity = 1
                quantity_multiplier = 1.0 + (min(quantity, 6) * 0.25) if event_type in {"cart_add", "purchase"} else 1.0
                interaction_matrix[user_id][product_name] += base_weight * quantity_multiplier


    return interaction_matrix

def build_association_rule_model(min_support=None, min_confidence=None, max_rules_per_product=None):
    support_threshold = ASSOCIATION_MIN_SUPPORT if min_support is None else max(0.0, float(min_support))
    confidence_threshold = ASSOCIATION_MIN_CONFIDENCE if min_confidence is None else max(0.0, float(min_confidence))
    rule_cap = ASSOCIATION_MAX_RULES_PER_PRODUCT if max_rules_per_product is None else max(1, int(max_rules_per_product))

    if db_layer.orders_collection is None:
        return {
            "total_orders": 0,
            "item_counts": Counter(),
            "pair_counts": Counter(),
            "rules_by_antecedent": {},
            "rule_count": 0
        }


    item_counts = Counter()
    pair_counts = Counter()
    total_orders = 0

    for order in db_layer.orders_collection.find({}):
        basket = sorted({
            (item or {}).get("name")
            for item in order.get("items", [])
            if (item or {}).get("name")
        })

        if not basket:
            continue
        total_orders += 1
        item_counts.update(basket)
        for pair in combinations(basket, 2):
            pair_counts[pair] += 1

    rules_by_antecedent = defaultdict(list)
    if total_orders > 0:
        for (item_a, item_b), co_occurrence in pair_counts.items():
            support = float(co_occurrence) / float(total_orders)
            if support < support_threshold:
                continue

            for antecedent, consequent in ((item_a, item_b), (item_b, item_a)):
                antecedent_count = int(item_counts.get(antecedent, 0) or 0)
                consequent_count = int(item_counts.get(consequent, 0) or 0)
                if antecedent_count <= 0 or consequent_count <= 0:
                    continue

                confidence = float(co_occurrence) / float(antecedent_count)
                if confidence < confidence_threshold:
                    continue

                consequent_support = float(consequent_count) / float(total_orders)
                lift = confidence / consequent_support if consequent_support > 0 else 0.0
                score = (
                    (confidence * 3.0) +
                    (support * 2.0) +
                    (min(lift, 4.0) * 0.8)
                )

                rules_by_antecedent[antecedent].append({
                    "consequent": consequent,
                    "support": round(support, 6),
                    "confidence": round(confidence, 6),
                    "lift": round(lift, 6),
                    "co_occurrence": int(co_occurrence),
                    "score": round(score, 6)
                })

    compact_rules = {}
    rule_count = 0
    for antecedent, rules in rules_by_antecedent.items():
        ranked_rules = sorted(
            rules,
            key=lambda rule: (
                float(rule.get("score", 0) or 0),
                float(rule.get("confidence", 0) or 0),
                float(rule.get("lift", 0) or 0),
                float(rule.get("support", 0) or 0)
            ),
            reverse=True
        )[:rule_cap]
        compact_rules[antecedent] = ranked_rules
        rule_count += len(ranked_rules)

    return {
        "total_orders": total_orders,
        "item_counts": item_counts,
        "pair_counts": pair_counts,
        "rules_by_antecedent": compact_rules,
        "rule_count": rule_count
    }

def get_association_rule_map_for_product(product_name, association_model=None):
    if not product_name:
        return {}
    association_model = association_model or build_association_rule_model()
    rules = (association_model.get("rules_by_antecedent", {}) or {}).get(product_name, [])
    return {
        rule.get("consequent"): rule
        for rule in rules
        if rule.get("consequent")
    }

def serialize_product(product, review_stats=None):
    if not product:
        return None
    product_copy = apply_product_review_stats(product, review_stats)
    if not product_copy.get("tags"):
        product_copy["tags"] = get_product_tags(product_copy)
    if "_id" in product_copy:
        product_copy["_id"] = str(product_copy["_id"])
    return product_copy

def build_recommender_snapshot():
    catalog = get_product_catalog()
    product_map = {product.get("name"): product for product in catalog if product.get("name")}
    user_interaction_matrix = build_user_interaction_matrix()
    association_model = build_association_rule_model()
    snapshot = {
        "trained_at": datetime.utcnow(),
        "product_count": len(catalog),
        "catalog": catalog,
        "product_map": product_map,
        "popularity": get_popularity_scores(),
        "tfidf_model": build_tfidf_model(catalog),
        "user_interaction_matrix": user_interaction_matrix,
        "association_model": association_model
    }
    return snapshot

def get_recommender_snapshot(force=False):
    snapshot = recommender_state.get("snapshot")
    is_stale = False
    if snapshot and snapshot.get("trained_at"):
        age_seconds = (datetime.utcnow() - snapshot["trained_at"]).total_seconds()
        is_stale = age_seconds >= RECOMMENDER_SNAPSHOT_TTL_SECONDS

    if force or snapshot is None or recommender_state.get("dirty") or is_stale:
        snapshot = build_recommender_snapshot()
        recommender_state["snapshot"] = snapshot
        recommender_state["dirty"] = False

    return snapshot

def mark_recommender_dirty():
    recommender_state["dirty"] = True

def build_item_collaborative_score_map(base_product_name, user_interaction_matrix=None):
    if not base_product_name:
        return Counter()

    user_interaction_matrix = user_interaction_matrix or build_user_interaction_matrix()
    collaborative_scores = Counter()

    for interactions in user_interaction_matrix.values():
        base_weight = float(interactions.get(base_product_name, 0) or 0)
        if base_weight <= 0:
            continue
        for product_name, weight in interactions.items():
            numeric_weight = float(weight or 0)
            if product_name == base_product_name or numeric_weight <= 0:
                continue
            collaborative_scores[product_name] += sqrt(base_weight * numeric_weight)

    return collaborative_scores

def build_frequently_bought_together_recommendations_for_product(
    base_product_name,
    catalog,
    popularity,
    association_model=None,
    limit=6,
    exclude_names=None,
    user_interaction_matrix=None
):
    exclude_names = exclude_names or set()
    if not base_product_name:
        return []

    product_map = {product.get("name"): product for product in (catalog or []) if product.get("name")}
    association_rules = get_association_rule_map_for_product(
        base_product_name,
        association_model=association_model
    )
    use_collaborative_fallback = not association_rules
    collaborative_fallback_scores = Counter()
    if use_collaborative_fallback:
        collaborative_fallback_scores = build_item_collaborative_score_map(
            base_product_name,
            user_interaction_matrix=user_interaction_matrix
        )
        if not collaborative_fallback_scores:
            return []

    ranked = []
    candidate_source = (
        association_rules.items()
        if association_rules
        else collaborative_fallback_scores.most_common(limit * 4)
    )

    for candidate_name, rule in candidate_source:
        if not candidate_name or candidate_name in exclude_names:
            continue

        candidate = product_map.get(candidate_name)
        if not candidate or not is_product_available(candidate):
            continue

        confidence = 0.0
        support = 0.0
        lift = 0.0
        collaborative_strength = 0.0
        if use_collaborative_fallback:
            collaborative_strength = min(float(rule or 0), 12.0) / 12.0
        else:
            confidence = float((rule or {}).get("confidence", 0) or 0)
            support = float((rule or {}).get("support", 0) or 0)
            lift = float((rule or {}).get("lift", 0) or 0)
        quality_score = get_product_quality_score(candidate)
        popularity_boost = min(float(popularity.get(candidate_name, 0)), 25.0) / 25.0

        final_score = (
            (confidence * 4.2) +
            (support * 3.0) +
            (min(lift, 4.0) * 1.25) +
            (collaborative_strength * 1.7) +
            (quality_score * 1.8) +
            (popularity_boost * 0.8)
        )
        confidence_pct = int(round(confidence * 100))

        ranked.append({
            "product": serialize_product(candidate),
            "score": round(final_score, 4),
            "reason": (
                (
                    f"frequently bought together ({confidence_pct}% confidence)"
                    + (" with strong category affinity" if lift >= 1.4 else "")
                )
                if not use_collaborative_fallback
                else "complementary fallback from collaborative co-engagement while purchase rules warm up"
            )
        })

    ranked.sort(
        key=lambda item: (
            item.get("score", 0),
            get_product_quality_score(item.get("product")),
            get_product_rating_value(item.get("product")),
            float(popularity.get((item.get("product") or {}).get("name"), 0))
        ),
        reverse=True
    )
    return ranked[:limit]

def build_frequently_bought_together_recommendations_for_user(
    user_id,
    catalog,
    popularity,
    association_model=None,
    limit=6,
    exclude_names=None,
    user_interaction_matrix=None
):
    exclude_names = exclude_names or set()
    if not user_id:
        return []

    user_interaction_matrix = user_interaction_matrix or build_user_interaction_matrix()
    user_vector = user_interaction_matrix.get(user_id) or Counter()
    if not user_vector:
        return []

    anchor_products = [
        name for name, weight in user_vector.most_common(8)
        if name and float(weight or 0) > 0 and name not in exclude_names
    ]
    if not anchor_products:
        return []

    association_model = association_model or build_association_rule_model()
    rules_by_antecedent = association_model.get("rules_by_antecedent", {}) or {}
    product_map = {product.get("name"): product for product in (catalog or []) if product.get("name")}
    candidate_scores = defaultdict(lambda: {
        "score": 0.0,
        "best_anchor": None,
        "best_confidence": 0.0
    })

    for anchor_name in anchor_products:
        anchor_weight = float(user_vector.get(anchor_name, 0) or 0)
        if anchor_weight <= 0:
            continue
        for rule in rules_by_antecedent.get(anchor_name, []):
            candidate_name = rule.get("consequent")
            if (
                not candidate_name or
                candidate_name in exclude_names or
                candidate_name in anchor_products
            ):
                continue

            confidence = float(rule.get("confidence", 0) or 0)
            support = float(rule.get("support", 0) or 0)
            lift = float(rule.get("lift", 0) or 0)
            score = (
                (anchor_weight * 0.2) +
                (confidence * 4.0) +
                (support * 2.8) +
                (min(lift, 4.0) * 1.0)
            )

            candidate_scores[candidate_name]["score"] += score
            if confidence > candidate_scores[candidate_name]["best_confidence"]:
                candidate_scores[candidate_name]["best_confidence"] = confidence
                candidate_scores[candidate_name]["best_anchor"] = anchor_name

    if not candidate_scores:
        fallback_entries = []
        for anchor_name in anchor_products[:2]:
            fallback_entries.extend(
                build_frequently_bought_together_recommendations_for_product(
                    base_product_name=anchor_name,
                    catalog=catalog,
                    popularity=popularity,
                    association_model=association_model,
                    limit=limit,
                    exclude_names=set(exclude_names).union(anchor_products),
                    user_interaction_matrix=user_interaction_matrix
                )
            )
        deduped = []
        seen = set()
        for entry in fallback_entries:
            name = ((entry or {}).get("product") or {}).get("name")
            if not name or name in seen:
                continue
            seen.add(name)
            deduped.append(entry)
            if len(deduped) >= limit:
                break
        if deduped:
            return deduped

    ranked = []
    for candidate_name, payload in candidate_scores.items():
        product = product_map.get(candidate_name)
        if not product or not is_product_available(product):
            continue

        quality_score = get_product_quality_score(product)
        popularity_boost = min(float(popularity.get(candidate_name, 0)), 25.0) / 25.0
        final_score = (
            float(payload.get("score", 0) or 0) +
            (quality_score * 1.6) +
            (popularity_boost * 0.7)
        )
        anchor_name = payload.get("best_anchor")

        ranked.append({
            "product": serialize_product(product),
            "score": round(final_score, 4),
            "reason": (
                f"often bought with products from your activity like {anchor_name}"
                if anchor_name
                else "frequently bought with items in your shopping history"
            )
        })

    ranked.sort(
        key=lambda item: (
            item.get("score", 0),
            get_product_quality_score(item.get("product")),
            get_product_rating_value(item.get("product")),
            float(popularity.get((item.get("product") or {}).get("name"), 0))
        ),
        reverse=True
    )
    return ranked[:limit]

def build_collaborative_recommendations_for_user(user_id, catalog, popularity, limit=6, exclude_names=None, user_interaction_matrix=None):
    exclude_names = exclude_names or set()
    if not user_id:
        return []

    user_interaction_matrix = user_interaction_matrix or build_user_interaction_matrix()
    target_vector = user_interaction_matrix.get(user_id)
    if not target_vector:
        return []

    similar_users = []
    for other_user_id, other_vector in user_interaction_matrix.items():
        if other_user_id == user_id:
            continue
        similarity = sparse_cosine_similarity(target_vector, other_vector)
        if similarity > 0.05:
            similar_users.append((other_user_id, similarity))

    if not similar_users:
        return []

    product_map = {product.get("name"): product for product in catalog if product.get("name")}
    candidate_scores = Counter()
    strongest_support = {}

    for other_user_id, similarity in similar_users:
        for product_name, weight in user_interaction_matrix.get(other_user_id, {}).items():
            numeric_weight = float(weight or 0)
            if product_name in exclude_names or numeric_weight <= 0:
                continue
            candidate_scores[product_name] += similarity * numeric_weight
            strongest_support[product_name] = max(float(strongest_support.get(product_name, 0.0)), similarity)

    ranked = []
    for product_name, score in candidate_scores.items():
        product = product_map.get(product_name)
        if not product or not is_product_available(product):
            continue

        final_score = (
            float(score) +
            (get_product_quality_score(product) * 1.2) +
            (min(float(popularity.get(product_name, 0)), 20) / 20.0)
        )
        reason = "liked by users with similar shopping activity"
        if float(strongest_support.get(product_name, 0.0)) >= 0.35:
            reason = "popular with shoppers whose carts and reviews look similar to yours"

        ranked.append({
            "product": serialize_product(product),
            "score": round(final_score, 4),
            "reason": reason
        })

    ranked.sort(
        key=lambda item: (
            item["score"],
            get_product_quality_score(item["product"]),
            get_product_rating_value(item["product"])
        ),
        reverse=True
    )
    return ranked[:limit]

def merge_recommendation_groups(recommendation_groups, limit):
    merged = {}

    for group in recommendation_groups:
        weight = float(group.get("weight", 1.0))
        entries = group.get("entries") or []
        group_size = max(len(entries), 1)

        for index, entry in enumerate(entries):
            product = entry.get("product") or {}
            product_name = product.get("name")
            if not product_name:
                continue

            rank_bonus = max(group_size - index, 1) / group_size
            weighted_score = (float(entry.get("score", 0) or 0) * weight) + rank_bonus

            if product_name not in merged:
                merged[product_name] = {
                    "product": product,
                    "score": 0.0,
                    "reasons": []
                }

            merged[product_name]["score"] += weighted_score
            reason = entry.get("reason")
            if reason and reason not in merged[product_name]["reasons"]:
                merged[product_name]["reasons"].append(reason)

    merged_entries = []
    for payload in merged.values():
        reasons = payload.pop("reasons", [])
        payload["score"] = round(float(payload.get("score", 0) or 0), 4)
        if len(reasons) >= 2:
            payload["reason"] = reasons[0] + "; " + reasons[1]
        elif reasons:
            payload["reason"] = reasons[0]
        merged_entries.append(payload)

    merged_entries.sort(
        key=lambda item: (
            item["score"],
            get_product_quality_score(item["product"]),
            get_product_rating_value(item["product"])
        ),
        reverse=True
    )
    return merged_entries[:limit]

def get_trending_products(limit=6, exclude_names=None):
    exclude_names = exclude_names or set()
    popularity = get_popularity_scores()
    products = []
    for product in get_product_catalog():
        if product.get("name") in exclude_names:
            continue
        if not is_product_available(product):
            continue
        products.append(product)

    products.sort(
        key=lambda item: (
            float(popularity.get(item.get("name"), 0)),
            get_product_quality_score(item),
            get_product_rating_value(item),
            get_product_review_count(item)
        ),
        reverse=True
    )
    return products[:limit]

def get_today_deal_seed():
    return int(datetime.utcnow().strftime("%Y%m%d"))

def get_today_discount_percent(product_name, seed=None):
    seed = seed if seed is not None else get_today_deal_seed()
    low = max(5, int(TODAYS_DEALS_MIN_DISCOUNT))
    high = max(low, int(TODAYS_DEALS_MAX_DISCOUNT))
    spread = (high - low) + 1
    name_score = sum(ord(ch) for ch in str(product_name or ""))
    return low + ((name_score + int(seed)) % spread)

def get_today_deal_price(product_name, base_price, seed=None):
    try:
        base_value = float(base_price or 0)
    except (TypeError, ValueError):
        return 0.0
    if base_value <= 0:
        return 0.0
    discount_percent = get_today_discount_percent(product_name, seed=seed)
    return round(max(base_value * (1.0 - (discount_percent / 100.0)), 1.0), 2)

def resolve_product_line_price(product, requested_price=None):
    try:
        base_price = float((product or {}).get("price") or 0)
    except (TypeError, ValueError):
        base_price = 0.0
    if base_price <= 0:
        return 0.0

    try:
        candidate_price = float(requested_price) if requested_price is not None else None
    except (TypeError, ValueError):
        candidate_price = None

    deal_price = get_today_deal_price((product or {}).get("name"), base_price)
    if candidate_price is not None:
        # Only honor client-provided price when it exactly matches today's computed deal price.
        if abs(candidate_price - deal_price) <= 0.01:
            return round(deal_price, 2)

    return round(base_price, 2)


def build_todays_deals(limit=None, category=None, user_id=None, snapshot=None):
    snapshot = snapshot or get_recommender_snapshot()
    catalog = list(snapshot.get("catalog", []))
    if not catalog:
        return []

    popularity = snapshot.get("popularity", Counter())
    normalized_category = normalize_text_value(category)
    if normalized_category == "all":
        normalized_category = ""

    resolved_limit = TODAYS_DEALS_DEFAULT_LIMIT if limit is None else max(1, int(limit))
    seed = get_today_deal_seed()
    activity_summary = get_user_activity_summary(user_id) if user_id else None
    category_preferences = (
        activity_summary.get("category_preferences", Counter())
        if activity_summary else Counter()
    )

    def collect_deals(category_filter):
        deals = []
        seen_names = set()
        for product in catalog:
            if not is_product_available(product):
                continue
            
            product_name = (product or {}).get("name")
            if not product_name or product_name in seen_names:
                continue
                
            category_name = normalize_text_value((product or {}).get("category"))
            if category_filter and category_name != category_filter:
                continue

            try:
                original_price = float((product or {}).get("price") or 0)
            except (TypeError, ValueError):
                original_price = 0
            if original_price <= 0:
                continue

            discount_percent = get_today_discount_percent(product_name, seed=seed)
            deal_price = get_today_deal_price(product_name, original_price, seed=seed)
            savings = round(max(original_price - deal_price, 0.0), 2)
            if savings <= 0:
                continue

            seen_names.add(product_name)
            
            category_boost = get_normalized_counter_score(category_preferences, category_name)
            rating_value = get_product_rating_value(product)
            quality_score = get_product_quality_score(product)
            popularity_score = min(float(popularity.get(product_name, 0)), 30.0) / 30.0

            deal_score = (
                (discount_percent * 0.44) +
                (rating_value * 0.85) +
                (quality_score * 4.2) +
                (popularity_score * 3.5) +
                (category_boost * 2.8)
            )

            reason = "popular pick in today's deals"
            if category_boost >= 0.6 and category_name:
                reason = f"deal in your preferred {format_category_label(category_name)} category"
            elif discount_percent >= (TODAYS_DEALS_MAX_DISCOUNT - 2):
                reason = "high discount deal for today"
            elif rating_value >= 4.5:
                reason = "top-rated product with today's offer"

            serialized = serialize_product(product)
            serialized["original_price"] = round(original_price, 2)
            serialized["deal_price"] = deal_price
            serialized["savings"] = savings
            serialized["discount_percent"] = int(discount_percent)

            deals.append({
                "product": serialized,
                "score": round(deal_score, 4),
                "reason": reason
            })


        deals.sort(
            key=lambda item: (
                float(item.get("score", 0) or 0),
                get_product_quality_score((item.get("product") or {})),
                get_product_rating_value((item.get("product") or {})),
                float(popularity.get((item.get("product") or {}).get("name"), 0))
            ),
            reverse=True
        )
        return deals[:resolved_limit]

    deals = collect_deals(normalized_category)
    if deals or not normalized_category:
        return deals
    return collect_deals("")

def score_product_similarity(base_product, candidate_product):
    score = 0.0
    reasons = []

    base_category = (base_product.get("category") or "").strip().lower()
    candidate_category = (candidate_product.get("category") or "").strip().lower()
    if base_category and base_category == candidate_category:
        score += 3.0
        reasons.append(f"same category: {candidate_category}")

    try:
        base_price = float(base_product.get("price") or 0)
        candidate_price = float(candidate_product.get("price") or 0)
        if base_price and candidate_price:
            price_gap = abs(base_price - candidate_price) / max(base_price, candidate_price)
            if price_gap <= 0.15:
                score += 2.0
                reasons.append("similar price range")
            elif price_gap <= 0.35:
                score += 1.0
    except (TypeError, ValueError):
        pass

    overlap_terms = get_top_content_overlap(
        get_product_content_weights(base_product),
        get_product_content_weights(candidate_product),
        limit=3
    )
    if overlap_terms:
        score += min(len(overlap_terms), 3) * 0.85
        reasons.append("shared features: " + ", ".join(overlap_terms[:2]))

    rating_match = get_rating_match_score(
        get_product_rating_value(base_product),
        get_product_rating_value(candidate_product)
    )
    if rating_match > 0.7:
        reasons.append("similar customer rating")

    score += rating_match * 2.2
    score += get_product_quality_score(candidate_product) * 1.2

    return score, reasons

def get_rating_match_score(reference_rating, candidate_rating):
    if reference_rating is None:
        return 0.0
    try:
        reference_rating = float(reference_rating)
        candidate_rating = float(candidate_rating)
    except (TypeError, ValueError):
        return 0.0
    gap = abs(reference_rating - candidate_rating)
    return max(0.0, 1.0 - (gap / 4.0))

def build_recommender_spaces(catalog):
    categories = sorted({
        (product.get("category") or "").strip().lower()
        for product in catalog
        if (product.get("category") or "").strip()
    })
    brands = sorted({
        get_product_brand_value(product)
        for product in catalog
        if get_product_brand_value(product)
    })
    token_scores = Counter()
    for product in catalog:
        token_scores.update(get_product_content_weights(product))
    tokens = [token for token, _count in token_scores.most_common(48)]

    prices = [float(product.get("price") or 0) for product in catalog if float(product.get("price") or 0) > 0]
    ratings = [float(product.get("rating") or 0) for product in catalog if float(product.get("rating") or 0) >= 0]
    review_counts = [int(product.get("review_count") or 0) for product in catalog if int(product.get("review_count") or 0) >= 0]

    return {
        "categories": categories,
        "brands": brands,
        "tokens": tokens,
        "max_price": max(prices) if prices else 1.0,
        "max_rating": max(ratings) if ratings else 5.0,
        "max_reviews": max(review_counts) if review_counts else 1.0
    }

def build_product_feature_vector(product, spaces):
    category = (product.get("category") or "").strip().lower()
    brand = get_product_brand_value(product)
    product_tokens = get_product_content_weights(product)

    vector = []

    for item_category in spaces["categories"]:
        vector.append(3.0 if item_category == category else 0.0)

    for item_brand in spaces["brands"]:
        vector.append(2.2 if item_brand == brand else 0.0)

    for token in spaces["tokens"]:
        vector.append(float(product_tokens.get(token, 0.0)))

    try:
        vector.append(float(product.get("price") or 0) / max(spaces["max_price"], 1.0))
    except (TypeError, ValueError):
        vector.append(0.0)

    try:
        vector.append(float(product.get("rating") or 0) / max(spaces["max_rating"], 1.0))
    except (TypeError, ValueError):
        vector.append(0.0)

    try:
        vector.append(int(product.get("review_count") or 0) / max(spaces["max_reviews"], 1.0))
    except (TypeError, ValueError):
        vector.append(0.0)

    return vector

def cosine_similarity(vec_a, vec_b):
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = sqrt(sum(a * a for a in vec_a))
    mag_b = sqrt(sum(b * b for b in vec_b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)

def score_product_against_query(query_text, product, tfidf_model=None):
    if not query_text:
        return 0.0, []

    tfidf_model = tfidf_model or build_tfidf_model([product] if product else [])
    query_vector = build_query_tfidf_vector(query_text, tfidf_model)
    product_vector = get_product_tfidf_vector(product, tfidf_model)
    query_weights = build_query_content_weights(query_text)
    product_weights = get_product_content_weights(product)
    similarity = sparse_cosine_similarity(query_vector, product_vector)
    overlap_terms = get_top_content_overlap(query_weights, product_weights, limit=4)
    query_tokens = tokenize_text(query_text)

    query_value = normalize_text_value(query_text)
    name_text = normalize_text_value((product or {}).get("name"))
    brand_text = normalize_text_value((product or {}).get("brand"))
    description_text = normalize_text_value((product or {}).get("description"))
    name_overlap = query_tokens.intersection(tokenize_text((product or {}).get("name")))
    description_overlap = query_tokens.intersection(tokenize_text((product or {}).get("description")))
    category_overlap = query_tokens.intersection(get_category_content_terms((product or {}).get("category")))

    exact_name_match = bool(query_value and query_value in name_text)
    brand_match = bool(query_value and query_value in brand_text)
    description_match = bool(query_value and query_value in description_text)

    score = (
        (similarity * 4.0) +
        (len(name_overlap) * 1.2) +
        (len(description_overlap) * 0.65) +
        (len(category_overlap) * 0.55) +
        (len(overlap_terms) * 0.3) +
        (1.4 if exact_name_match else 0.0) +
        (0.9 if brand_match else 0.0) +
        (0.5 if description_match else 0.0) +
        (get_product_quality_score(product) * 0.8)
    )

    match_reasons = []
    if exact_name_match:
        match_reasons.append("name")
    if brand_match:
        match_reasons.append("brand")
    if name_overlap:
        match_reasons.extend(sorted(name_overlap)[:2])
    if overlap_terms:
        match_reasons.extend(overlap_terms[:2])

    return score, match_reasons

def rank_products_by_content_query(query_text, products, tfidf_model=None, include_scores=False, min_score=None):
    if not query_text:
        return list(products or []) if not include_scores else [
            {"product": product, "score": 0.0, "reasons": []}
            for product in (products or [])
        ]

    catalog = list(products or [])
    if not catalog:
        return []

    tfidf_model = tfidf_model or build_tfidf_model(catalog)
    threshold = CONTENT_QUERY_SCORE_THRESHOLD if min_score is None else float(min_score)
    ranked = []

    for product in catalog:
        score, reasons = score_product_against_query(query_text, product, tfidf_model=tfidf_model)
        if score < threshold and not reasons:
            continue
        ranked.append({
            "product": product,
            "score": round(score, 4),
            "reasons": reasons
        })

    ranked.sort(
        key=lambda item: (
            item["score"],
            get_product_quality_score(item["product"]),
            get_product_rating_value(item["product"]),
            get_product_review_count(item["product"])
        ),
        reverse=True
    )
    if include_scores:
        return ranked
    return [entry["product"] for entry in ranked]

def build_search_score_map(products, relevance_scores, popularity):
    products = list(products or [])
    max_relevance = max(
        [float(relevance_scores.get((product or {}).get("name"), 0) or 0) for product in products] + [0.0]
    )
    max_popularity = max(
        [float(popularity.get((product or {}).get("name"), 0) or 0) for product in products] + [0.0]
    )
    max_reviews = max([get_product_review_count(product) for product in products] + [0])
    review_denominator = log(1.0 + float(max_reviews)) if max_reviews > 0 else 0.0

    scores = {}
    for product in products:
        product_name = (product or {}).get("name")
        if not product_name:
            continue

        relevance_raw = float(relevance_scores.get(product_name, 0) or 0)
        popularity_raw = float(popularity.get(product_name, 0) or 0)
        rating_value = get_product_rating_value(product)
        review_count = get_product_review_count(product)

        relevance_norm = relevance_raw / max(max_relevance, 0.0001)
        popularity_norm = popularity_raw / max(max_popularity, 0.0001)
        rating_norm = rating_value / 5.0
        reviews_norm = (log(1.0 + float(review_count)) / review_denominator) if review_denominator > 0 else 0.0

        hybrid_score = (
            (relevance_norm * SEARCH_RANK_WEIGHTS["relevance"]) +
            (popularity_norm * SEARCH_RANK_WEIGHTS["popularity"]) +
            (rating_norm * SEARCH_RANK_WEIGHTS["rating"]) +
            (reviews_norm * SEARCH_RANK_WEIGHTS["reviews"])
        )

        scores[product_name] = {
            "hybrid": round(hybrid_score, 6),
            "relevance": round(relevance_raw, 6),
            "relevance_norm": round(relevance_norm, 6),
            "popularity": round(popularity_raw, 6),
            "popularity_norm": round(popularity_norm, 6),
            "rating": round(rating_value, 6),
            "rating_norm": round(rating_norm, 6),
            "reviews": int(review_count),
            "reviews_norm": round(reviews_norm, 6)
        }

    return scores

def build_content_based_recommendations_for_query(query_text, catalog, popularity, limit=6, exclude_names=None, tfidf_model=None):
    exclude_names = exclude_names or set()
    tfidf_model = tfidf_model or build_tfidf_model(catalog)
    ranked_entries = rank_products_by_content_query(
        query_text,
        catalog,
        tfidf_model=tfidf_model,
        include_scores=True,
        min_score=SEARCH_MIN_CONTENT_SCORE
    )
    recommendations = []

    for entry in ranked_entries:
        product = entry.get("product") or {}
        product_name = product.get("name")
        if not product_name or product_name in exclude_names:
            continue
        if not is_product_available(product):
            continue

        score = float(entry.get("score", 0) or 0)
        overlap_terms = list(entry.get("reasons") or [])
        score += min(float(popularity.get(product_name, 0)), 20) * 0.03
        recommendations.append({
            "product": serialize_product(product),
            "score": round(score, 4),
            "reason": (
                "content match for your search: " + ", ".join(overlap_terms[:2])
                if overlap_terms
                else "content match for your search"
            )
        })
        if len(recommendations) >= limit:
            break

    return recommendations[:limit]

def build_content_based_recommendations_for_user(activity_summary, catalog, product_map, popularity, limit=6, exclude_names=None, tfidf_model=None):
    exclude_names = exclude_names or set()
    if not activity_summary or not activity_summary["name_weights"]:
        return []

    tfidf_model = tfidf_model or build_tfidf_model(catalog)
    profile_vector = build_user_tfidf_profile_vector(activity_summary, product_map, tfidf_model)
    if profile_vector is None:
        return []

    ranked = []

    for candidate in catalog:
        candidate_name = candidate.get("name")
        if not candidate_name or candidate_name in exclude_names:
            continue
        if not is_product_available(candidate):
            continue

        candidate_vector = get_product_tfidf_vector(candidate, tfidf_model)
        content_similarity = sparse_cosine_similarity(profile_vector, candidate_vector)
        category_match = get_normalized_counter_score(
            activity_summary.get("category_preferences"),
            normalize_text_value(candidate.get("category"))
        )
        brand_match = get_normalized_counter_score(
            activity_summary.get("brand_preferences"),
            get_product_brand_value(candidate)
        )
        keyword_match = get_keyword_preference_match(
            activity_summary.get("keyword_preferences"),
            candidate
        )
        price_match = get_price_preference_match(
            activity_summary.get("price_points"),
            candidate
        )
        quality_score = get_product_quality_score(candidate)
        popularity_boost = min(float(popularity.get(candidate_name, 0)), 20) / 20.0
        negative_penalty = 0.8 if candidate_name in activity_summary.get("negative_products", set()) else 0.0

        final_score = (
            (content_similarity * 4.2) +
            (category_match * 1.8) +
            (brand_match * 1.4) +
            (keyword_match * 1.7) +
            (price_match * 0.9) +
            (quality_score * 1.2) +
            (popularity_boost * 0.5) -
            negative_penalty
        )

        overlap_terms = get_top_content_overlap(
            activity_summary.get("keyword_preferences", Counter()),
            get_product_content_weights(candidate),
            limit=2
        )
        candidate_category = format_category_label(candidate.get("category"))
        reason = "based on your content preferences"
        if category_match >= 0.6 and candidate_category:
            reason = f"content match for your {candidate_category} interest"
        elif brand_match >= 0.6:
            reason = "matches brands you engage with often"
        elif overlap_terms:
            reason = "shared product traits: " + ", ".join(overlap_terms)

        ranked.append({
            "product": serialize_product(candidate),
            "score": round(final_score, 4),
            "reason": reason
        })

    ranked.sort(
        key=lambda item: (
            item["score"],
            get_product_quality_score(item["product"]),
            get_product_rating_value(item["product"]),
            float(popularity.get(item["product"].get("name"), 0))
        ),
        reverse=True
    )
    return ranked[:limit]

def build_ml_recommendations_for_product(
    base_product,
    catalog,
    popularity,
    limit=6,
    exclude_names=None,
    user_interaction_matrix=None,
    tfidf_model=None,
    association_model=None
):
    exclude_names = exclude_names or set()
    base_category = (base_product.get("category") or "").strip().lower()
    spaces = build_recommender_spaces(catalog + [base_product])
    base_vector = build_product_feature_vector(base_product, spaces)
    tfidf_model = tfidf_model or build_tfidf_model(catalog + [base_product])
    base_tfidf_vector = get_product_tfidf_vector(base_product, tfidf_model)
    collaborative_scores = build_item_collaborative_score_map(
        base_product.get("name"),
        user_interaction_matrix=user_interaction_matrix
    )
    association_rule_map = get_association_rule_map_for_product(
        base_product.get("name"),
        association_model=association_model
    )
    ranked = []

    for candidate in catalog:
        candidate_name = candidate.get("name")
        if not candidate_name or candidate_name in exclude_names or candidate_name == base_product.get("name"):
            continue
        if not is_product_available(candidate):
            continue

        candidate_category = (candidate.get("category") or "").strip().lower()
        same_category = candidate_category == base_category
        candidate_vector = build_product_feature_vector(candidate, spaces)
        dense_similarity = cosine_similarity(base_vector, candidate_vector)
        tfidf_similarity = sparse_cosine_similarity(
            base_tfidf_vector,
            get_product_tfidf_vector(candidate, tfidf_model)
        )
        similarity_score, reasons = score_product_similarity(base_product, candidate)
        popularity_boost = min(float(popularity.get(candidate_name, 0)), 20) / 20.0
        quality_score = get_product_quality_score(candidate)
        collaborative_boost = min(float(collaborative_scores.get(candidate_name, 0) or 0), 10.0) / 10.0
        association_rule = association_rule_map.get(candidate_name) or {}
        association_confidence = float(association_rule.get("confidence", 0) or 0)
        association_lift = float(association_rule.get("lift", 0) or 0)
        association_support = float(association_rule.get("support", 0) or 0)
        association_boost = (
            (association_confidence * 2.8) +
            (association_support * 6.0) +
            (min(association_lift, 4.0) * 0.9)
        )
        category_bonus = 1.5 if same_category else 0.0
        complementary_boost = 1.8 * collaborative_boost if not same_category else 0.0
        rating_match = get_rating_match_score(
            get_product_rating_value(base_product),
            get_product_rating_value(candidate)
        )
        final_score = (
            (tfidf_similarity * 4.4) +
            (dense_similarity * 1.2) +
            (similarity_score * 1.1) +
            category_bonus +
            (rating_match * 2.2) +
            (quality_score * 2.6) +
            (collaborative_boost * 1.6) +
            association_boost +
            complementary_boost +
            (popularity_boost * 0.8)
        )

        reason = f"similar to {base_product.get('name')}"
        if association_confidence >= 0.12 and not same_category:
            reason = "frequently bought together with this product"
        elif not same_category and collaborative_boost >= 0.25:
            reason = "complementary product shoppers often buy or view together"
        elif same_category and tfidf_similarity >= 0.45:
            reason = "similar item in the same category using TF-IDF similarity"
        elif collaborative_boost >= 0.35:
            reason = "often explored together by similar shoppers"
        elif rating_match >= 0.85:
            reason = "close rating match with strong customer feedback"
        elif quality_score >= 0.82:
            reason = "highly rated pick with consistent reviews"
        elif reasons:
            reason = ", ".join(reasons[:2])

        ranked.append({
            "product": serialize_product(candidate),
            "score": round(final_score, 4),
            "reason": reason
        })

    ranked.sort(
        key=lambda item: (
            item["score"],
            get_product_rating_value(item["product"]),
            get_product_review_count(item["product"]),
            float(popularity.get(item["product"].get("name"), 0))
        ),
        reverse=True
    )

    same_category_ranked = [
        entry for entry in ranked
        if normalize_text_value((entry.get("product") or {}).get("category")) == base_category
    ]
    complementary_ranked = [
        entry for entry in ranked
        if normalize_text_value((entry.get("product") or {}).get("category")) != base_category
    ]

    blended = []
    blended.extend(same_category_ranked[:max(1, limit - COMPLEMENTARY_MIN_RESULTS)])
    blended.extend(complementary_ranked[:COMPLEMENTARY_MIN_RESULTS])

    used_names = {entry.get("product", {}).get("name") for entry in blended if entry.get("product")}
    for entry in ranked:
        product_name = (entry.get("product") or {}).get("name")
        if not product_name or product_name in used_names:
            continue
        blended.append(entry)
        used_names.add(product_name)
        if len(blended) >= limit:
            break

    return blended[:limit]

def get_recommendation_seed_categories(product_name=None, user_id=None):
    categories = []

    if product_name:
        product = get_product_map().get(product_name)
        category = (product or {}).get("category")
        if category:
            categories.append(category.strip().lower())

    if user_id:
        activity_summary = get_user_activity_summary(user_id)
        if activity_summary["category_preferences"]:
            for category, _weight in activity_summary["category_preferences"].most_common():
                category = (category or "").strip().lower()
                if category and category not in categories:
                    categories.append(category)

    return categories

def diversify_recommendations(ranked_entries, limit):
    diversified = []
    category_counts = Counter()

    for entry in ranked_entries:
        product = entry.get("product") or {}
        category = (product.get("category") or "").strip().lower()
        if category_counts.get(category, 0) >= 2 and len(diversified) + 1 < limit:
            continue
        diversified.append(entry)
        if category:
            category_counts[category] += 1
        if len(diversified) >= limit:
            return diversified

    for entry in ranked_entries:
        if entry in diversified:
            continue
        diversified.append(entry)
        if len(diversified) >= limit:
            break

    return diversified[:limit]

def get_activity_target_rating(activity_summary, product_map):
    if not activity_summary or not product_map:
        return None

    preferred_names = [
        name for name in activity_summary.get("positive_products", set())
        if name in product_map
    ]
    if not preferred_names:
        preferred_names = [
            name for name, _weight in activity_summary.get("name_weights", {}).most_common()
            if name not in activity_summary.get("negative_products", set()) and name in product_map
        ]

    weighted_total = 0.0
    total_weight = 0.0
    for name in preferred_names:
        rating = get_product_rating_value(product_map.get(name))
        if rating <= 0:
            continue
        weight = float(activity_summary["name_weights"].get(name, 1.0))
        weighted_total += rating * weight
        total_weight += weight

    if total_weight <= 0:
        return None
    return round(weighted_total / total_weight, 2)

def build_recommendation_results(limit=6, product_name=None, user_id=None, snapshot=None):
    snapshot = snapshot or get_recommender_snapshot()
    product_map = snapshot.get("product_map", {})
    catalog = list(snapshot.get("catalog", []))
    if not catalog:
        return []

    exclude_names = set()
    popularity = snapshot.get("popularity", Counter())
    tfidf_model = snapshot.get("tfidf_model")
    user_interaction_matrix = snapshot.get("user_interaction_matrix")
    association_model = snapshot.get("association_model")
    seed_categories = get_recommendation_seed_categories(product_name=product_name, user_id=user_id)
    ranked = []

    if product_name:
        exclude_names.add(product_name)
        base_product = product_map.get(product_name)
        if base_product:
            similar_ranked = build_ml_recommendations_for_product(
                base_product,
                catalog,
                popularity,
                limit=limit,
                exclude_names=exclude_names,
                user_interaction_matrix=user_interaction_matrix,
                tfidf_model=tfidf_model,
                association_model=association_model
            )
            fbt_ranked = build_frequently_bought_together_recommendations_for_product(
                base_product_name=base_product.get("name"),
                catalog=catalog,
                popularity=popularity,
                association_model=association_model,
                limit=limit,
                exclude_names=exclude_names,
                user_interaction_matrix=user_interaction_matrix
            )
            ranked = merge_recommendation_groups([
                {"entries": similar_ranked, "weight": 1.0},
                {"entries": fbt_ranked, "weight": 1.05}
            ], limit)
            return ranked[:limit]

    activity_summary = None
    target_rating = None
    if user_id:
        activity_summary = get_user_activity_summary(user_id)
        exclude_names.update(activity_summary["name_weights"].keys())
        target_rating = get_activity_target_rating(activity_summary, product_map)
        content_ranked = build_content_based_recommendations_for_user(
            activity_summary,
            catalog,
            product_map,
            popularity,
            limit=limit,
            exclude_names=exclude_names,
            tfidf_model=tfidf_model
        )
        collaborative_ranked = build_collaborative_recommendations_for_user(
            user_id,
            catalog,
            popularity,
            limit=limit,
            exclude_names=exclude_names,
            user_interaction_matrix=user_interaction_matrix
        )
        frequent_bought_ranked = build_frequently_bought_together_recommendations_for_user(
            user_id,
            catalog,
            popularity,
            association_model=association_model,
            limit=limit,
            exclude_names=exclude_names,
            user_interaction_matrix=user_interaction_matrix
        )
        ranked = merge_recommendation_groups([
            {"entries": content_ranked, "weight": 1.0},
            {"entries": collaborative_ranked, "weight": 0.95},
            {"entries": frequent_bought_ranked, "weight": 0.9}
        ], limit)

    if not seed_categories:
        if ranked:
            return diversify_recommendations(ranked, limit)
        trending = get_trending_products(limit=limit, exclude_names=exclude_names)
        return [
            {
                "product": serialize_product(product),
                "score": round(
                    float(popularity.get(product.get("name"), 0)) +
                    (get_product_quality_score(product) * 5),
                    3
                ),
                "reason": "trending with shoppers right now"
            }
            for product in trending
        ]

    for category_index, seed_category in enumerate(seed_categories):
        category_matches = []
        for candidate in catalog:
            candidate_name = candidate.get("name")
            candidate_category = (candidate.get("category") or "").strip().lower()
            if not candidate_name or candidate_name in exclude_names:
                continue
            if not is_product_available(candidate):
                continue
            if candidate_category != seed_category:
                continue

            if candidate_name in {item["product"]["name"] for item in ranked if item.get("product")}:
                continue
            candidate_rating = get_product_rating_value(candidate)
            rating_match = get_rating_match_score(target_rating, candidate_rating)
            quality_score = get_product_quality_score(candidate)
            negative_penalty = 0.0
            if activity_summary and target_rating is not None and candidate_rating + 0.35 < target_rating:
                negative_penalty = min(target_rating - candidate_rating, 2.5) * 0.8

            category_matches.append({
                "product": serialize_product(candidate),
                "score": round(
                    max(0, 10 - category_index) +
                    min(float(popularity.get(candidate_name, 0)), 20) * 0.2 +
                    (candidate_rating * 0.75) +
                    (quality_score * 2.4) +
                    (rating_match * 2.8) -
                    negative_penalty,
                    3
                ),
                "reason": (
                    f"matches your preferred {target_rating:.1f}+ rated {seed_category} picks"
                    if target_rating is not None and rating_match >= 0.8
                    else (
                        f"same category: {seed_category}"
                        if category_index == 0
                        else f"matches your interest in {seed_category}"
                    )
                )
            })

        category_matches.sort(
            key=lambda item: (
                item["score"],
                get_product_quality_score(item["product"]),
                float(popularity.get(item["product"].get("name"), 0))
            ),
            reverse=True
        )

        for entry in category_matches:
            if entry["product"]["name"] in {item["product"]["name"] for item in ranked}:
                continue
            ranked.append(entry)
            if len(ranked) >= limit:
                break
        if len(ranked) >= limit:
            break

    if len(ranked) < limit:
        existing_names = {entry["product"]["name"] for entry in ranked if entry.get("product")}
        existing_names.update(exclude_names)
        for product in get_trending_products(limit=limit * 2, exclude_names=existing_names):
            ranked.append({
                "product": serialize_product(product),
                "score": round(
                    float(popularity.get(product.get("name"), 0)) +
                    (get_product_quality_score(product) * 5),
                    3
                ),
                "reason": "trending with shoppers right now"
            })
            if len(ranked) >= limit:
                break

    return diversify_recommendations(ranked, limit)

def build_support_chat_context(message=None, session_id=None, user_id=None):
    """
    Constructs a comprehensive context for the chatbot, including catalog data,
    user-specific cart/wishlist items, and general recommendations.
    """
    try:
        snapshot = get_recommender_snapshot()
        
        # 1. Catalog View (Larger sample for matching)
        raw_catalog = snapshot.get("catalog", [])
        products = [serialize_product(p) for p in raw_catalog[:50]] if raw_catalog else []
            
        # 2. Recommendations & Deals
        recommendations = build_recommendation_results(limit=6, user_id=user_id, snapshot=snapshot)
        todays_deals = build_todays_deals(limit=4, snapshot=snapshot)
        
        # 3. User-Specific State (Cart, Wishlist & Orders)
        cart_items = []
        wishlist_items = []
        user_orders = []
        
        if user_id:
            if db_layer.cart_collection is not None:
                cart = db_layer.cart_collection.find_one({"user_id": user_id})
                if cart:
                    cart_items = list(cart.get("items", []))
            
            if db_layer.wishlist_collection is not None:
                wishlist = db_layer.wishlist_collection.find_one({"user_id": user_id})
                if wishlist:
                    wishlist_items = list(wishlist.get("items", []))

            # Fetch recent orders for order tracking
            if db_layer.orders_collection is not None:
                try:
                    raw_orders = list(db_layer.orders_collection.find({"user_id": user_id}).sort("created_at", -1).limit(20))
                    for order in raw_orders:
                        user_orders.append({
                            "_id": str(order["_id"]),
                            "items": order.get("items", []),
                            "total": order.get("total", 0),
                            "status": order.get("status", "placed"),
                            "shipping": order.get("shipping", {}),
                            "payment": order.get("payment", ""),
                            "created_at": order.get("created_at"),
                        })
                except Exception as oe:
                    print(f"Error fetching orders for chat context: {oe}")

        return {
            "products": products,
            "recommendations": recommendations,
            "todays_deals": todays_deals,
            "cart_items": cart_items,
            "wishlist_items": wishlist_items,
            "user_orders": user_orders,
            "user": {"user_id": user_id} if user_id else None,
            "catalog_size": len(raw_catalog),
            "trained_at": snapshot.get("trained_at").isoformat() if snapshot.get("trained_at") else None
        }
    except Exception as e:
        print(f"Error building chat context: {e}")
        return {
            "products": [],
            "recommendations": [],
            "todays_deals": [],
            "cart_items": [],
            "wishlist_items": [],
            "user_orders": [],
            "user": None,
            "error": str(e)
        }
