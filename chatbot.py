import re
import pickle
import os
from collections import defaultdict


WORD_RE = re.compile(r"[a-z0-9]+")

CATEGORY_ALIASES = {
    "electronics": {"electronics", "electronic", "tv", "laptop", "headphone", "headphones", "earbuds", "watch", "smartwatch", "gadget", "gadgets"},
    "fashion": {"fashion", "shoe", "shoes", "sneaker", "sneakers", "jacket", "wallet", "clothes", "clothing", "wear"},
    "furniture": {"furniture", "chair", "table", "lamp", "sofa", "dining", "desk"},
    "homeappliances": {"homeappliances", "home", "appliance", "appliances", "air purifier", "kitchen", "living room"}
}

INTENT_LABELS_MAP = {
    "hello": "greeting",
    "goodbye": "farewell",
    "payment": "payment",
    "shipping and delivery": "delivery",
    "return policy": "return",
    "order tracking": "order",
    "my shopping cart": "cart",
    "wishlist": "wishlist",
    "product recommendation": "recommend",
    "product reviews": "review",
    "account help": "account",
    "support hours": "support_hours",
    "discounts and deals": "offer",
    "speak to agent": "escalation",
    "contact": "contact",
    "stock": "stock"
}


CANDIDATE_LABELS = list(INTENT_LABELS_MAP.keys())


_classifier_pipeline = None

def get_classifier():
    global _classifier_pipeline
    if _classifier_pipeline is not None:
        return _classifier_pipeline
        
    try:
        model_path = os.path.join(os.getcwd(), 'intent_engine.pkl')
        if os.path.exists(model_path):
            with open(model_path, 'rb') as f:
                _classifier_pipeline = pickle.load(f)
            print(f"[ChatBot] Loaded local intent engine from {model_path}")
        else:
            print("[ChatBot] WARNING: intent_engine.pkl not found. Using fallback matching.")
            _classifier_pipeline = "fallback"
    except Exception as e:
        print(f"[ChatBot] FAILED to load local intent engine: {e}")
        _classifier_pipeline = "fallback"
    return _classifier_pipeline



def _normalize_text(text):
    return " ".join(WORD_RE.findall((text or "").lower()))


def _tokenize(text):
    return set(WORD_RE.findall((text or "").lower()))


def _format_currency(value):
    try:
        return f"INR {int(float(value)):,}"
    except (TypeError, ValueError):
        return "INR 0"


def _truncate_list(items, limit=3):
    safe_items = [item for item in (items or []) if item]
    if len(safe_items) <= limit:
        return safe_items
    return safe_items[:limit]


def _find_category(message):
    lowered = (message or "").lower()
    for category, aliases in CATEGORY_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            return category
    return None


def _extract_budget(message):
    match = re.search(r"(?:under|below|less than|max(?:imum)?|budget)\s*(?:inr|rs\.?|rupees)?\s*(\d{3,6})", (message or "").lower())
    if match:
        return int(match.group(1))
    return None


def _find_product_matches(message, products):
    normalized_message = _normalize_text(message)
    message_tokens = _tokenize(message)
    scored = []

    for product in products or []:
        name = str(product.get("name") or "").strip()
        if not name:
            continue
        normalized_name = _normalize_text(name)
        product_tokens = _tokenize(name)
        score = 0

        if normalized_name and normalized_name in normalized_message:
            score += 10

        overlap = len(message_tokens.intersection(product_tokens))
        score += overlap * 2

        category = str(product.get("category") or "").strip().lower()
        if category and category in normalized_message:
            score += 1

        if score > 0:
            scored.append((score, product))

    scored.sort(key=lambda item: (item[0], float(item[1].get("rating") or 0)), reverse=True)

    unique = []
    seen = set()
    for _, product in scored:
        name = product.get("name")
        if name in seen:
            continue
        seen.add(name)
        unique.append(product)

    return unique[:4]


def _has_explicit_product_mention(message, product):
    normalized_message = _normalize_text(message)
    normalized_name = _normalize_text((product or {}).get("name") or "")
    if not normalized_name:
        return False
    return normalized_name in normalized_message


def _build_product_summary(product):
    if not product:
        return ""
    name = product.get("name") or "Product"
    category = str(product.get("category") or "general").replace("homeappliances", "home appliances")
    rating = float(product.get("rating") or 0)
    review_count = int(product.get("review_count") or 0)
    rating_text = f"{rating:.1f}/5"
    if review_count > 0:
        rating_text += f" from {review_count} review"
        if review_count != 1:
            rating_text += "s"
    return f"{name} is in {category} at {_format_currency(product.get('price'))} with a rating of {rating_text}."


def _extract_order_id(message):
    # Regex to find patterns like #B8B68662 or ORD-789
    # We look for the 8-digit hex ID shown in 'My Account'
    patterns = [r"#([A-Fa-f0-9]{8})", r"#?(\d{6})", r"ORD-(\d{3,})"]
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return match.group(0)
    return None



def _is_abusive(message):
    # Basic keyword-based safety filter for production-grade bots
    bad_words = {"stupid", "idiot", "dumb", "hate", "worthless", "garbage", "trash"}
    normalized = set(re.findall(r"[a-z]+", message.lower()))
    return not normalized.isdisjoint(bad_words)


def _get_intent_scores(message):
    normalized = _normalize_text(message)
    if not normalized:
        return {}
    
    classifier = get_classifier()
    scores = {}
    
    if classifier == "fallback" or classifier is None:
        # Fallback to simple matching if ML model fails to load
        tokens = set(normalized.split())
        for keyword in CANDIDATE_LABELS:
            score = 0
            for word in keyword.split():
                if word in tokens:
                    score += 1
            if score > 0:
                intent_key = INTENT_LABELS_MAP[keyword]
                scores[intent_key] = max(scores.get(intent_key, 0), score)
        return scores

    # ML Inference
    try:
        print(f"[ChatBot] Analyzing message: '{message[:50]}...'")
        
        # sklearn predict_proba returns a probability distribution
        probs = classifier.predict_proba([message])[0]
        classes = classifier.classes_
        
        # Sort classes by probability descending
        sorted_indices = probs.argsort()[::-1]
        best_class = classes[sorted_indices[0]]
        best_score = probs[sorted_indices[0]]
        
        print(f"[ChatBot] Top Intent: {best_class} (Score: {best_score:.4f})")

        for idx in sorted_indices:
            intent_key = classes[idx]
            score = probs[idx]
            
            # Application-specific logic: Boost 'cart' intent if the user specifically mentions 'cart'
            final_score = score
            if intent_key == "cart" and "cart" in normalized:
                final_score += 0.2
                print(f"[ChatBot] Boosting 'cart' intent due to keyword match. New Score: {final_score:.4f}")

            if final_score >= 0.4:
                scores[intent_key] = int(final_score * 10) + 1
                
    except Exception as e:
        print(f"[ChatBot] Local inference error: {e}")

        
    return scores



def build_support_response(user, context=None):
    context = context or {}
    message = (user or "").strip()
    normalized = _normalize_text(message)
    products = list(context.get("products") or [])
    recommendations = list(context.get("recommendations") or [])
    cart_items = list(context.get("cart_items") or [])
    wishlist_items = list(context.get("wishlist_items") or [])
    is_logged_in = bool(context.get("user"))
    user_name = ((context.get("user") or {}).get("name") or "there").strip()
    category = _find_category(message)
    product_matches = _find_product_matches(message, products)
    budget = _extract_budget(message)
    intent_scores = _get_intent_scores(message)
    history = list(context.get("history") or [])

    # Dialogue Management / Coreference Resolution
    # If the user says "it", "this", or "that" and we have no strong product match, 
    # we look at the bot's past responses for a product we were just discussing.
    coref_triggers = {"it", "this", "that", "them", "those", "one"}
    if not product_matches and any(word in normalized.split() for word in coref_triggers):
        for turn in reversed(history):
            if turn.get("role") == "bot":
                historical_matches = _find_product_matches(turn.get("text", ""), products)
                if historical_matches:
                    product_matches = historical_matches
                    break

    response = {
        "intent": "fallback",
        "reply": "",
        "suggestions": [],
        "products": [],
        "matched_products": [product.get("name") for product in product_matches[:3] if product.get("name")],
        "category": category
    }

    if not normalized:
        response["reply"] = "Welcome! I'm BuyMore, your intelligent shopping coach. How can I help you find exactly what you're looking for today?"
        response["suggestions"] = ["Show trending products", "Track my order", "How do returns work?"]
        return response

    # 1. Safety Filter (Abusive Language Protection)
    if _is_abusive(message):
        response["intent"] = "safety_trigger"
        response["reply"] = "I aim to be a helpful and polite assistant. Please rephrase your request so I can assist you better."
        response["suggestions"] = ["How do returns work?", "Show trending products", "Payment options"]
        return response


    # 2. Sentiment-Based Escalation Trigger
    sentiment = (context.get("sentiment") or {}).get("label", "").lower()
    sentiment_prefix = ""
    if "neg" in sentiment:
        sentiment_prefix = "I hear you, and I'm here to help make this right. "
        response["suggestions"].insert(0, "Speak to a human agent")

    if intent_scores.get("greeting") and len(normalized.split()) <= 4:
        response["intent"] = "greeting"
        response["reply"] = (
            f"{sentiment_prefix}Hi {user_name}! I'm BuyMore, your personal shopping assistant. I can help you find products, track orders, or handle returns. What's on your mind?"
            if is_logged_in else
            f"{sentiment_prefix}Hi there! I'm BuyMore, your personal shopping assistant. I can help you find products, track orders, or handle returns. How can I help you today?"
        )
        response["suggestions"] += ["Show trending products", "Recommend something for me", "What is in my cart?"]
        return response

    if intent_scores.get("farewell") and len(normalized.split()) <= 6:
        response["intent"] = "farewell"
        response["reply"] = f"{sentiment_prefix}It was a pleasure helping you! Feel free to reach out if you need more shopping advice or order help. Have a great day!"
        response["suggestions"] += ["Show trending products", "Payment options", "Support hours"]
        return response

    order_id_raw = _extract_order_id(message)
    if intent_scores.get("order") or order_id_raw:
        response["intent"] = "order"
        if order_id_raw:
            # Clean up the ID
            clean_id = order_id_raw.replace("#", "").strip().upper()
            
            # Look up order from context
            user_orders = list(context.get("user_orders") or [])
            matched_order = None
            
            for order in user_orders:
                if not order: continue
                # Match by _id string
                o_id_str = str(order.get("_id", "")).upper()
                if clean_id in o_id_str or o_id_str.endswith(clean_id):
                    matched_order = order
                    break
            
            if matched_order:
                # Safely extract details
                status = str(matched_order.get("status", "pending")).capitalize()
                items = matched_order.get("items", [])
                
                # Format items list
                if isinstance(items, list) and items:
                    item_names = ", ".join([str(i.get("name", "Item")) for i in items if i])
                else:
                    item_names = "Products in your order"
                    
                total = matched_order.get("total", 0)
                shipping = matched_order.get("shipping", {})
                address = shipping.get("address", "your location") if isinstance(shipping, dict) else "your location"

                reply = f"{sentiment_prefix}I've found your order **#{clean_id}**!\n\n"
                reply += f"**Status:** {status}\n"
                reply += f"**Items:** {item_names}\n"
                reply += f"**Total:** {_format_currency(total)}\n"
                reply += f"**Shipping to:** {address}\n\n"
                reply += "We're working hard to get it to you. You'll receive an update as soon as the status changes!"
                response["reply"] = reply
            elif user_orders:
                response["reply"] = f"{sentiment_prefix}I couldn't find an order with ID **#{clean_id}** in your recent history. Please double-check the ID from your My Account page."
            else:
                response["reply"] = f"{sentiment_prefix}I see you're looking for order **#{clean_id}**, but I couldn't retrieve your order history. Please ensure you are signed in or try again later."
        else:
            response["reply"] = f"{sentiment_prefix}I'd love to track that for you! Please share your Order ID (e.g., #B8B68662) so I can give you a real-time status update."
        
        response["suggestions"] += ["What is in my cart?", "How do returns work?", "Payment options"]
        return response




    if intent_scores.get("account"):
        response["intent"] = "account"
        response["reply"] = (
            f"Hi {user_name}, you're currently logged in. You can manage your profile, view your wishlist, or reset your password directly from your account settings."
            if is_logged_in else
            "You can create an account or sign in to save your wishlist, view your shopping cart, and leave reviews for your favorite products. Would you like to sign in now?"
        )
        response["suggestions"] = ["Show trending products", "What is in my cart?", "Recommend something for me"]
        return response

    if intent_scores.get("support_hours"):
        response["intent"] = "support_hours"
        response["reply"] = "I'm available 24/7! If you need a human agent, our support team is online Monday to Saturday, 9:00 AM to 9:00 PM. How can I help you right now?"
        response["suggestions"] = ["Payment options", "How do returns work?", "Show trending products"]
        return response

    if intent_scores.get("escalation"):
        response["intent"] = "escalation"
        response["reply"] = "I'm sorry I haven't been able to solve this yet. I can connect you with one of our human experts right now, or you can email us at support@buymore.com."
        response["suggestions"] = ["Speak to a human agent", "Support hours", "Payment options"]
        return response

    if intent_scores.get("contact"):
        response["intent"] = "contact"
        response["reply"] = "You can reach our team anytime at support@buymore.com. We're also available at our main office during business hours (Mon-Sat, 9AM-9PM)."
        response["suggestions"] = ["Support hours", "Show trending products", "Payment options"]
        return response

    if intent_scores.get("stock"):
        response["intent"] = "stock"
        response["reply"] = "It looks like some popular items are moving fast! Most restocks happen within 1-2 weeks. I recommend keeping an eye on the product page or checking out these similar items in the meantime."
        response["suggestions"] = ["Show trending products", "Recommend something for me", "What is in my wishlist?"]

    # Returns / Refunds (Policy FAQ)
    if intent_scores.get("return") or any(w in normalized.split() for w in ["return", "returns", "refund", "refunds", "exchange", "exchanges"]):
        response["intent"] = "return"
        try:
            from knowledge_base import FAQ_POLICIES

            by_id = {doc.get("id"): doc for doc in (FAQ_POLICIES or []) if isinstance(doc, dict)}
            sections = []
            for doc_id in ["doc_returns_1", "doc_returns_2", "doc_refunds_1", "doc_refunds_2"]:
                doc = by_id.get(doc_id)
                if doc and doc.get("text"):
                    title = (doc.get("title") or "Policy").strip()
                    sections.append(f"{title}: {doc['text']}")

            if sections:
                response["reply"] = f"{sentiment_prefix}Here’s how returns/refunds work at BuyMore:\n\n" + "\n\n".join(sections)
            else:
                response["reply"] = f"{sentiment_prefix}You can return most items within 14 days of delivery if they’re unused and in original packaging. If you tell me what item you’re returning, I’ll guide you step-by-step."
        except Exception as e:
            print(f"[ChatBot] Returns policy lookup failed: {e}")
            response["reply"] = f"{sentiment_prefix}You can return most items within 14 days of delivery if they’re unused and in original packaging. If you tell me what item you’re returning, I’ll guide you step-by-step."

        response["suggestions"] = ["Track my order", "Payment options", "Support hours"]
        return response

    # Payment Options (Policy FAQ)
    if intent_scores.get("payment") or ("payment" in normalized and any(w in normalized for w in ["option", "options", "method", "methods", "upi", "card", "wallet", "cod"])):
        response["intent"] = "payment"
        try:
            from knowledge_base import FAQ_POLICIES

            doc = next((d for d in (FAQ_POLICIES or []) if isinstance(d, dict) and d.get("id") == "doc_payment_1"), None)
            if doc and doc.get("text"):
                response["reply"] = f"{sentiment_prefix}{doc['text']}"
            else:
                response["reply"] = f"{sentiment_prefix}We accept major credit/debit cards, UPI, and digital wallets. Share your preferred method and I’ll confirm availability."
        except Exception as e:
            print(f"[ChatBot] Payment policy lookup failed: {e}")
            response["reply"] = f"{sentiment_prefix}We accept major credit/debit cards, UPI, and digital wallets. Share your preferred method and I’ll confirm availability."

        response["suggestions"] = ["Go to checkout", "How do returns work?", "Support hours"]
        return response

    if intent_scores.get("cart"):
        response["intent"] = "cart"
        if not is_logged_in:
            response["reply"] = "Sign in to see your personalized cart! I can help you review your items and suggest matching accessories once you're logged in."
            response["suggestions"] = ["Show trending products", "Recommend something", "Payment options"]
            return response

        if not cart_items:
            response["reply"] = f"Your cart is empty at the moment, {user_name}."
            response["suggestions"] = ["Show trending products", "Recommend electronics", "Recommend something for me"]
            return response

        # Aggregate cart items to show quantity and total
        cart_summary = {}
        total_price = 0
        for item in cart_items:
            name = item.get("name", "Product")
            price = float(item.get("price") or 0)
            qty = int(item.get("quantity", 1))
            cart_summary[name] = cart_summary.get(name, 0) + qty
            total_price += (price * qty)

        reply = "Here’s what’s in your cart:\n"
        for name, qty in cart_summary.items():
            reply += f"- {name} (Qty: {qty})\n"
        
        reply += f"Total: INR {total_price:,.2f}"
        
        response["reply"] = reply
        response["suggestions"] = ["Go to checkout", "Payment options"]
        return response

    if intent_scores.get("wishlist"):
        response["intent"] = "wishlist"
        if not is_logged_in:
            response["reply"] = "Your wishlist is a great place to save items for later! Just sign in to view your saved products and get personalized alerts."
            response["suggestions"] = ["Show trending products", "Recommend fashion", "Account help"]
            return response

        if not wishlist_items:
            response["reply"] = f"💖 Your wishlist is looking a bit lonely, {user_name}."
            response["suggestions"] = ["Show trending products", "Recommend fashion", "Recommend electronics"]
            return response

        reply = f"💖 Here are the items in your wishlist:\n"
        for item in wishlist_items:
            name = item.get("name", "Product")
            reply += f"- {name}\n"
        
        response["reply"] = reply
        response["suggestions"] = ["Move to cart", "Recommend similar", "What is in my cart?"]
        return response

    explicit_product_match = bool(product_matches and _has_explicit_product_mention(message, product_matches[0]))

    if product_matches and explicit_product_match and (intent_scores.get("review") or "rating" in normalized or "review" in normalized):
        product = product_matches[0]
        response["intent"] = "review"
        response["reply"] = f"Excellent choice! {_build_product_summary(product)} Customers really love this one. You can read more detailed reviews or leave your own on the product page!"
        response["suggestions"] = [f"Recommend products like {product.get('name')}", "Show trending products", "What is in my cart?"]
        response["products"] = product_matches[:3]
        return response

    if product_matches and explicit_product_match:
        product = product_matches[0]
        response["intent"] = "product"
        response["reply"] = f"I found the {product.get('name')} for you! {_build_product_summary(product)} Would you like to see reviews or add it to your cart?"
        response["suggestions"] = [f"Reviews for {product.get('name')}", f"Recommend products like {product.get('name')}", "Payment options"]
        response["products"] = product_matches[:3]
        return response
        
    is_trending_query = any(w in normalized.split() for w in ["trending", "deals", "popular", "deal"])
    if intent_scores.get("offer") or is_trending_query:
        from core.recommender import build_todays_deals, get_today_discount_percent
        deals = build_todays_deals(limit=4)
        if deals:
            reply_text = "🔥 Today's Best Deals:\n"
            for d in deals:
                product = d.get("product") or {}
                name = product.get("name", "Product")
                emoji = "🎁"
                lowered_name = name.lower()
                if any(x in lowered_name for x in ["phone", "earbuds", "headphone", "speaker", "audio"]): emoji = "🎧"
                elif any(x in lowered_name for x in ["watch", "smartwatch", "fitness"]): emoji = "⌚"
                elif any(x in lowered_name for x in ["mouse", "keyboard", "controller", "gaming"]): emoji = "🖱️"
                elif any(x in lowered_name for x in ["tv", "monitor", "display", "screen"]): emoji = "📺"
                elif "shoe" in lowered_name: emoji = "👟"
                elif "shirt" in lowered_name or "jacket" in lowered_name or "wear" in lowered_name: emoji = "👕"
                
                discount = get_today_discount_percent(name)
                reply_text += f"\n- {name} {emoji} ({discount}% OFF)"
            
            response["intent"] = "offer"
            response["reply"] = reply_text
            response["products"] = [d.get("product") for d in deals if d.get("product")]
            response["suggestions"] = ["What's in my cart?", "Payment options", "Support hours"]
            return response

    if category:
        response["intent"] = "category"
        filtered = [product for product in products if str(product.get("category") or "").lower() == category]
        filtered.sort(key=lambda item: (float(item.get("rating") or 0), -float(item.get("price") or 0)), reverse=True)
        if budget is not None:
            filtered = [item for item in filtered if float(item.get("price") or 0) <= budget]
        response["products"] = filtered[:4]
        display_category = category.replace("homeappliances", "home appliances")
        if response["products"]:
            response["reply"] = f"I've picked out the best {display_category} for you" + (f" under {_format_currency(budget)}." if budget is not None else ". These are our top-rated options:")
        else:
            response["reply"] = f"I couldn't find any {display_category} right now" + (f" under {_format_currency(budget)}" if budget is not None else "") + ". Would you like to see our overall trending products instead?"
        response["suggestions"] = ["Show trending products", "Recommend something for me", "Payment options"]
        return response

    if intent_scores.get("recommend") or "show me" in normalized or "what should i buy" in normalized or "suggest" in normalized:
        response["intent"] = "recommend"
        if category:
            filtered = [product for product in products if str(product.get("category") or "").lower() == category]
            filtered.sort(key=lambda item: (float(item.get("rating") or 0), int(item.get("review_count") or 0)), reverse=True)
            response["products"] = filtered[:4]
            response["reply"] = f"Based on what's popular, I highly recommend checking out these {category.replace('homeappliances', 'home appliances')}:"
        elif recommendations:
            response["products"] = [entry.get("product") for entry in recommendations[:4] if entry.get("product")]
            response["reply"] = f"Since you're browsing, here are some personalized picks I think you'll love, {user_name}:"
        else:
            ranked = sorted(products, key=lambda item: (float(item.get("rating") or 0), int(item.get("review_count") or 0)), reverse=True)
            response["products"] = ranked[:4]
            response["reply"] = "Here are some of our absolute best-sellers that customers are loving right now:"
        response["suggestions"] = ["What is in my cart?", "Show trending products", "Payment options"]
        return response


    # Final Fallback -> RAG Semantic Knowledge Base Search
    try:
        from rag_engine import retrieve_answer
        rag_match = retrieve_answer(message)
        if rag_match:
            # Standard RAG Fallback for other policy/faq findings
            response["intent"] = "faq_knowledge"
            response["reply"] = f"{sentiment_prefix}I found this info for you regarding **{rag_match['title']}**:\n\n{rag_match['text']}"
            response["suggestions"] = ["Support hours", "Track my order", "Show trending products"]
            return response
    except Exception as e:
        print(f"RAG Engine skipped or failed: {e}")

    response["reply"] = "Can you clarify what you're looking for? I'm here to help with your cart, wishlist, trending products, specific deals, and store policies."
    response["suggestions"] = ["Show trending products", "Track my order", "How do returns work?"]
    return response


def get_bot_payload(user, context=None):
    return build_support_response(user, context=context)


def get_bot_response(user, context=None):
    payload = build_support_response(user, context=context)
    return payload["reply"]
