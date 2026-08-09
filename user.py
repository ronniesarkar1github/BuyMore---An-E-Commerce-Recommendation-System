from flask import Blueprint, render_template, jsonify, session, request, redirect, url_for
from bson import ObjectId, json_util
import core.database as db_layer
from core.database import (
    get_product_stock, get_product_by_name, log_interaction_event
)
from core.utils import (
    normalize_email, is_valid_email, validate_password, 
    hash_password, verify_password, start_user_session,
    generate_otp, send_email_otp, create_otp_record,
    get_current_user_id, normalize_text_value
)
from core.recommender import (
    get_recommender_snapshot, build_recommendation_results,
    get_trending_products, serialize_product, resolve_product_line_price,
    mark_recommender_dirty, analyze_sentiment_text, recompute_product_rating,
    build_support_chat_context, build_todays_deals,
    build_frequently_bought_together_recommendations_for_product,
    RECOMMENDER_SNAPSHOT_TTL_SECONDS, TODAYS_DEALS_DEFAULT_LIMIT, 
    SEARCH_RANK_WEIGHTS, SEARCH_MIN_CONTENT_SCORE,
    get_product_brand_value, get_product_tags, rank_products_by_content_query,
    build_search_score_map, get_product_quality_score,
    get_product_rating_value, get_product_review_count,
    get_product_review_stats, apply_product_review_stats
)

from chatbot import get_bot_payload
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import os
import re

# Import new recommendation system
from productrecommendation import get_recommendations_for_product

_chat_sessions = defaultdict(list)


user_bp = Blueprint('user', __name__)

@user_bp.route("/")
@user_bp.route("/home")
def home():
    return render_template("home.html")

@user_bp.route("/about")
def about():
    return render_template("about.html")

@user_bp.route("/api/contact", methods=["POST"])
def submit_contact():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    phone = data.get("phone", "").strip()
    topic = data.get("topic", "").strip()
    message = data.get("message", "").strip()
    
    if not all([name, email, phone, topic, message]):
        return jsonify({"success": False, "message": "All fields are required"}), 400
        
    try:
        db_layer.contact_reports_collection.insert_one({
            "name": name,
            "email": email,
            "phone": phone,
            "topic": topic,
            "message": message,
            "status": "Pending",
            "created_at": datetime.utcnow()
        })
        return jsonify({"success": True, "message": "Request Submitted"}), 200
    except Exception as e:
        print(f"Error submitting contact request: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

@user_bp.route("/account")
def account():
    return render_template("account.html")

@user_bp.route("/addtocart")
def addtocart():
    return render_template("addtocart.html")

@user_bp.route("/checkout")
def checkout():
    return render_template("checkout.html")

@user_bp.route("/electronics")
def electronics():
    return render_template("electronics.html")

@user_bp.route("/fashion")
def fashion():
    return render_template("fashion.html")

@user_bp.route("/furniture")
def furniture():
    return render_template("furniture.html")

@user_bp.route("/gadgets")
def gadgets():
    return render_template("gadgets.html")

@user_bp.route("/homeappliances")
def homeappliances():
    return render_template("homeappliances.html")

@user_bp.route("/groceries")
def groceries():
    return render_template("groceries.html")

@user_bp.route("/signin")
def signin():
    return render_template("signin.html")

@user_bp.route("/signup")
def signup():
    return render_template("signup.html")

@user_bp.route("/wishlist")
def wishlist():
    return render_template("wishlist.html")

@user_bp.route("/support")
def support():
    return render_template("support.html")

@user_bp.route("/search")
def search():
    return render_template("search.html")

# API Routes
@user_bp.route("/api/check_session", methods=["GET"])
def check_session():
    if "user_id" in session:
        return jsonify({
            "logged_in": True,
            "user": {"name": session.get("user_name"), "email": session.get("user_email")}
        })
    return jsonify({"logged_in": False})


@user_bp.route("/api/db/status", methods=["GET"])
def db_status():
    """
    Runtime DB diagnostics to confirm MongoDB connection + product visibility.
    """
    try:
        payload = db_layer.get_db_status()
        return jsonify({"success": True, "status": payload})
    except Exception as e:
        return jsonify({"success": False, "message": "Failed to read DB status", "error": str(e)}), 500

@user_bp.route("/api/register", methods=["POST"])
def register():
    if db_layer.users_collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    email = normalize_email(data.get("email"))
    password = data.get("password", "")
    
    if not name or not email or not password:
        return jsonify({"success": False, "message": "All fields are required"}), 400

    if not is_valid_email(email):
        return jsonify({"success": False, "message": "Please enter a valid email address"}), 400

    is_valid_password, password_error = validate_password(password)
    if not is_valid_password:
        return jsonify({"success": False, "message": password_error}), 400
    
    existing_user = db_layer.users_collection.find_one({"email": email})
    if existing_user:
        return jsonify({"success": False, "message": "Email already registered"}), 400
    
    user_doc = {
        "name": name,
        "email": email,
        "password": hash_password(password),
        "created_at": datetime.utcnow()
    }
    
    try:
        db_layer.users_collection.insert_one(user_doc)
        return jsonify({"success": True, "message": "Registration successful! Please sign in."})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@user_bp.route("/api/login", methods=["POST"])
def login():
    if db_layer.users_collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    
    data = request.get_json() or {}
    login_input = normalize_email(data.get("login"))
    password = data.get("password", "")
    
    if not login_input or not password:
        return jsonify({"success": False, "message": "Email and password are required"}), 400

    if not is_valid_email(login_input):
        return jsonify({"success": False, "message": "Please enter a valid email address"}), 400
    
    user = db_layer.users_collection.find_one({"email": login_input})
    
    if not user:
        return jsonify({"success": False, "message": "User not found. Please sign up first."}), 404
    
    if verify_password(password, user["password"]):
        start_user_session(user)
        return jsonify({
            "success": True, 
            "message": "Login successful!",
            "user": {"name": user["name"], "email": user["email"]}
        })
    else:
        return jsonify({"success": False, "message": "Invalid password"}), 401

@user_bp.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully"})

@user_bp.route("/api/cart", methods=["GET"])
def get_cart():
    if not get_current_user_id():
        return jsonify({"success": False, "message": "Login required"}), 401
    if db_layer.cart_collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    user_id = get_current_user_id()
    try:
        cart = db_layer.cart_collection.find_one({"user_id": user_id}) or {}
        items = list(cart.get("items", []))
        has_updates = False
        product_cache = {}

        for item in items:
            product_name = str((item or {}).get("name") or "").strip()
            if not product_name:
                continue
            if product_name not in product_cache:
                product_cache[product_name] = db_layer.products_collection.find_one({"name": product_name}) if db_layer.products_collection is not None else None
            product = product_cache.get(product_name)
            if not product:
                continue
            product = apply_product_review_stats(product)

            resolved_price = resolve_product_line_price(product, (item or {}).get("price"))
            try:
                current_price = float((item or {}).get("price") or 0)
            except (TypeError, ValueError):
                current_price = 0.0

            if abs(current_price - resolved_price) > 0.01:
                item["price"] = resolved_price
                has_updates = True
            if not item.get("image") and product.get("image"):
                item["image"] = product.get("image")
                has_updates = True
            if not item.get("category") and product.get("category"):
                item["category"] = product.get("category")
                has_updates = True
            rating = get_product_rating_value(product)
            review_count = get_product_review_count(product)
            if item.get("rating") != rating:
                item["rating"] = rating
                has_updates = True
            if item.get("review_count") != review_count:
                item["review_count"] = review_count
                has_updates = True

        if has_updates:
            db_layer.cart_collection.update_one({"user_id": user_id}, {"$set": {"items": items}}, upsert=True)

        return jsonify({"success": True, "items": items})
    except Exception as e:
        print(f"/api/cart error: {e}")
        return jsonify({"success": False, "message": "Database error"}), 500

@user_bp.route("/api/wishlist", methods=["GET"])
def get_wishlist():
    if not get_current_user_id():
        return jsonify({"success": False, "message": "Login required"}), 401
    if db_layer.wishlist_collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    user_id = get_current_user_id()
    try:
        wishlist = db_layer.wishlist_collection.find_one({"user_id": user_id}) or {}
        items = list(wishlist.get("items", []))
        has_updates = False
        product_cache = {}

        for item in items:
            product_name = str((item or {}).get("name") or "").strip()
            if not product_name:
                continue
            
            # Fetch catalog data if available
            if product_name not in product_cache:
                product_cache[product_name] = db_layer.products_collection.find_one({"name": product_name}) if db_layer.products_collection is not None else None
            
            product = product_cache.get(product_name)
            if product:
                product = apply_product_review_stats(product)
                # Update item details from product catalog (latest data)
                item["price"] = product.get("price")
                item["image"] = product.get("image")
                item["category"] = product.get("category")
                item["rating"] = get_product_rating_value(product)
                item["review_count"] = get_product_review_count(product)
            else:
                print(f"DEBUG: Wishlist item '{product_name}' not found in products collection.")

        return jsonify({"success": True, "items": items})
    except Exception as e:
        print(f"/api/wishlist error: {e}")
        return jsonify({"success": False, "message": "Database error"}), 500

@user_bp.route("/api/user/profile", methods=["GET"])
def get_user_profile():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"success": False, "message": "Login required"}), 401
        
    try:
        user = db_layer.users_collection.find_one({"_id": ObjectId(user_id)}, {"password": 0})
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404
            
        cart = db_layer.cart_collection.find_one({"user_id": user_id}) if db_layer.cart_collection else None
        wishlist = db_layer.wishlist_collection.find_one({"user_id": user_id}) if db_layer.wishlist_collection else None
        cart_count = len(cart.get("items", []) if cart else [])
        wishlist_count = len(wishlist.get("items", []) if wishlist else [])
        
        return json_util.dumps({
            "success": True,
            "user": {"name": user.get("name"), "email": user.get("email")},
            "cart_count": cart_count,
            "wishlist_count": wishlist_count
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@user_bp.route("/api/cart/add", methods=["POST"])
def cart_add():
    if not get_current_user_id():
        return jsonify({"success": False, "message": "Login required"}), 401
    if db_layer.cart_collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    data = request.get_json() or {}
    product = data.get("product") or {}
    quantity = data.get("quantity", 1)
    user_id = get_current_user_id()

    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Invalid quantity"}), 400
    if quantity < 1:
        return jsonify({"success": False, "message": "Quantity must be at least 1"}), 400

    product_name = str(product.get("name") or "").strip()
    if not product_name:
        return jsonify({"success": False, "message": "Product name is required"}), 400

    product_record = db_layer.products_collection.find_one({"name": product_name}) if db_layer.products_collection is not None else None
    if not product_record:
        return jsonify({"success": False, "message": "Product not found"}), 404
    product_record = apply_product_review_stats(product_record)

    resolved_price = resolve_product_line_price(product_record, product.get("price"))
    if resolved_price <= 0:
        return jsonify({"success": False, "message": "Invalid product price"}), 400

    max_stock = get_product_stock(product_name)
    if max_stock is None:
        return jsonify({"success": False, "message": "Product not found"}), 404

    cart = db_layer.cart_collection.find_one({"user_id": user_id})
    if not cart:
        cart = {"user_id": user_id, "items": []}

    current_qty = 0
    for item in cart.get("items", []):
        if item.get("name") == product_name:
            current_qty = int(item.get("quantity", 1))
            break

    if current_qty + quantity > max_stock:
        return jsonify({
            "success": False,
            "message": "Out of stock! Only " + str(max_stock) + " unit(s) available for " + product_name + ".",
            "out_of_stock": True,
            "stock": max_stock,
            "current_qty": current_qty
        }), 400

    found = False
    for item in cart.get("items", []):
        if item.get("name") == product_name:
            item["quantity"] += quantity
            item["price"] = resolved_price
            if product_record.get("image"):
                item["image"] = product_record.get("image")
            if product_record.get("category"):
                item["category"] = product_record.get("category")
            item["rating"] = get_product_rating_value(product_record)
            item["review_count"] = get_product_review_count(product_record)
            found = True
            break
    if not found:
        cart["items"].append({
            "name": product_name,
            "price": resolved_price,
            "image": product_record.get("image") or product.get("image"),
            "category": product_record.get("category"),
            "rating": get_product_rating_value(product_record),
            "review_count": get_product_review_count(product_record),
            "quantity": quantity
        })

    db_layer.cart_collection.replace_one({"user_id": user_id}, cart, upsert=True)
    log_interaction_event(
        user_id=user_id,
        product_name=product_name,
        event_type="cart_add",
        source="cart_add_api",
        quantity=quantity
    )
    mark_recommender_dirty()
    return jsonify({"success": True, "message": "Added to cart"})

@user_bp.route("/api/cart/remove", methods=["POST"])
def cart_remove():
    if not get_current_user_id():
        return jsonify({"success": False, "message": "Login required"}), 401
    if db_layer.cart_collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    data = request.get_json()
    idx = data.get("index")
    user_id = get_current_user_id()
    
    cart = db_layer.cart_collection.find_one({"user_id": user_id})
    if cart and cart.get("items") and idx is not None:
        try:
            cart["items"].pop(int(idx))
            db_layer.cart_collection.replace_one({"user_id": user_id}, cart)
            mark_recommender_dirty()
        except (IndexError, ValueError):
            return jsonify({"success": False, "message": "Invalid index"}), 400
    return jsonify({"success": True, "message": "Removed from cart"})

@user_bp.route("/api/cart/update_quantity", methods=["POST"])
def cart_update_quantity():
    if not get_current_user_id():
        return jsonify({"success": False, "message": "Login required"}), 401
    if db_layer.cart_collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    data = request.get_json()
    idx = data.get("index")
    quantity = data.get("quantity")
    user_id = get_current_user_id()

    try:
        idx = int(idx)
        quantity = int(quantity)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Invalid index or quantity"}), 400

    cart = db_layer.cart_collection.find_one({"user_id": user_id})
    if not cart or not cart.get("items") or idx < 0 or idx >= len(cart["items"]):
        return jsonify({"success": False, "message": "Item not found"}), 404

    product_name = cart["items"][idx].get("name", "")
    max_stock = get_product_stock(product_name)
    if max_stock is None:
        return jsonify({"success": False, "message": "Product not found"}), 404

    if quantity > max_stock:
        return jsonify({
            "success": False,
            "message": "Out of stock! Only " + str(max_stock) + " unit(s) available for " + product_name + ".",
            "out_of_stock": True,
            "stock": max_stock
        }), 400

    if quantity < 1:
        cart["items"].pop(idx)
    else:
        cart["items"][idx]["quantity"] = quantity

    db_layer.cart_collection.replace_one({"user_id": user_id}, cart)
    mark_recommender_dirty()
    return jsonify({"success": True, "message": "Cart updated"})

@user_bp.route("/api/wishlist/add", methods=["POST"])
def wishlist_add():
    if not get_current_user_id():
        return jsonify({"success": False, "message": "Login required"}), 401
    if db_layer.wishlist_collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    data = request.get_json()
    product = data.get("product", {})
    user_id = get_current_user_id()
    
    wishlist = db_layer.wishlist_collection.find_one({"user_id": user_id})
    if not wishlist:
        wishlist = {"user_id": user_id, "items": []}
    
    if not any(item.get("name") == product.get("name") for item in wishlist.get("items", [])):
        wishlist["items"].append(product)
        db_layer.wishlist_collection.replace_one({"user_id": user_id}, wishlist, upsert=True)
        mark_recommender_dirty()
    
    return jsonify({"success": True, "message": "Added to wishlist"})

@user_bp.route("/api/wishlist/remove", methods=["POST"])
def wishlist_remove():
    if not get_current_user_id():
        return jsonify({"success": False, "message": "Login required"}), 401
    if db_layer.wishlist_collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500
    data = request.get_json()
    product_name = data.get("productName")
    user_id = get_current_user_id()
    
    db_layer.wishlist_collection.update_one(
        {"user_id": user_id},
        {"$pull": {"items": {"name": product_name}}}
    )
    mark_recommender_dirty()
    return jsonify({"success": True, "message": "Removed from wishlist"})

@user_bp.route("/api/interactions/click", methods=["POST"])
def track_product_click():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"success": True, "tracked": False, "message": "Anonymous click ignored"})
    if db_layer.click_events_collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500

    data = request.get_json() or {}
    product_name = (data.get("productName") or data.get("product_name") or "").strip()
    source = (data.get("source") or "product_click").strip()
    if not product_name:
        return jsonify({"success": False, "message": "Product name is required"}), 400

    tracked = log_interaction_event(
        user_id=user_id,
        product_name=product_name,
        event_type="click",
        source=source
    )
    if not tracked:
        return jsonify({"success": False, "message": "Product not found"}), 404

    mark_recommender_dirty()
    return jsonify({"success": True, "tracked": True})

@user_bp.route("/api/interactions/view", methods=["POST"])
def track_product_view():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"success": True, "tracked": False, "message": "Anonymous view ignored"})
    if db_layer.click_events_collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500

    data = request.get_json() or {}
    product_name = (data.get("productName") or data.get("product_name") or "").strip()
    source = (data.get("source") or "product_view").strip()
    if not product_name:
        return jsonify({"success": False, "message": "Product name is required"}), 400

    tracked = log_interaction_event(
        user_id=user_id,
        product_name=product_name,
        event_type="view",
        source=source
    )
    if not tracked:
        return jsonify({"success": False, "message": "Product not found"}), 404

    mark_recommender_dirty()
    return jsonify({"success": True, "tracked": True})

@user_bp.route("/api/orders/place", methods=["POST"])
def place_order():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"success": False, "message": "Login required"}), 401
    if db_layer.cart_collection is None or db_layer.orders_collection is None or db_layer.products_collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500

    data = request.get_json() or {}
    shipping = data.get("shipping") or {}
    payment = (data.get("payment") or "").strip()

    required_fields = {
        "fullName": "Full name",
        "phone": "Phone number",
        "address": "Address",
        "city": "City",
        "state": "State",
        "pincode": "Pincode"
    }
    for key, label in required_fields.items():
        if not str(shipping.get(key) or "").strip():
            return jsonify({"success": False, "message": label + " is required"}), 400

    if not re.fullmatch(r"[0-9]{10}", str(shipping.get("phone") or "")):
        return jsonify({"success": False, "message": "Please enter a valid 10-digit phone number"}), 400
    if not re.fullmatch(r"[0-9]{6}", str(shipping.get("pincode") or "")):
        return jsonify({"success": False, "message": "Please enter a valid 6-digit pincode"}), 400
    if not payment:
        return jsonify({"success": False, "message": "Payment method is required"}), 400

    cart = db_layer.cart_collection.find_one({"user_id": user_id}) or {}
    items = list(cart.get("items", []))
    if not items:
        return jsonify({"success": False, "message": "Your cart is empty"}), 400

    validated_items = []
    subtotal = 0.0
    for item in items:
        product_name = (item or {}).get("name")
        try:
            quantity = max(1, int((item or {}).get("quantity", 1) or 1))
        except (TypeError, ValueError):
            quantity = 1
        product = db_layer.products_collection.find_one({"name": product_name})
        if not product:
            return jsonify({"success": False, "message": "Product not found: " + str(product_name)}), 404
        stock = get_product_stock(product_name)
        if stock is None or quantity > stock:
            return jsonify({
                "success": False,
                "message": "Insufficient stock for " + str(product_name),
                "product_name": product_name,
                "stock": stock or 0
            }), 400

        line_price = resolve_product_line_price(product, (item or {}).get("price"))
        if line_price <= 0:
            return jsonify({"success": False, "message": "Invalid price for " + str(product_name)}), 400
        subtotal += line_price * quantity
        validated_items.append({
            "name": product_name,
            "price": line_price,
            "quantity": quantity,
            "image": product.get("image") or item.get("image"),
            "category": product.get("category")
        })

    order_doc = {
        "user_id": user_id,
        "user_email": session.get("user_email", ""),
        "user_name": session.get("user_name", ""),
        "items": validated_items,
        "shipping": shipping,
        "payment": payment,
        "payment-status": "Pending" if "cash on delivery" in payment.lower() else "Paid",
        "total": round(subtotal, 2),
        "status": "placed",
        "created_at": datetime.utcnow()
    }

    try:
        result = db_layer.orders_collection.insert_one(order_doc)
        
        # Deduct stock
        for item in validated_items:
            db_layer.products_collection.update_one(
                {"name": item["name"]},
                {"$inc": {"stock": -item["quantity"]}}
            )
            log_interaction_event(
                user_id=user_id,
                product_name=item["name"],
                event_type="purchase",
                source="checkout",
                quantity=item["quantity"]
            )

        # Clear cart
        db_layer.cart_collection.delete_one({"user_id": user_id})
        
        mark_recommender_dirty()

        # Save to payments collection
        try:
            db_layer.payments_collection.insert_one({
                "order_id": str(result.inserted_id),
                "user_id": user_id,
                "user_email": shipping.get("email") or session.get("user_email") or "N/A",
                "method": payment,
                "amount": round(subtotal, 2),
                "payment-status": order_doc["payment-status"],
                "created_at": order_doc["created_at"]
            })
        except Exception as pe:
            print(f"Failed to log payment record: {pe}")

        return jsonify({
            "success": True,
            "order_id": str(result.inserted_id),
            "message": "Order placed successfully!"
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to place order: {str(e)}"}), 500

@user_bp.route("/api/orders", methods=["GET"])
def get_user_orders():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"success": False, "message": "Not logged in"}), 401
        
    if db_layer.orders_collection is None:
        return jsonify([]), 200
        
    try:
        user_orders = list(db_layer.orders_collection.find({"user_id": user_id}).sort("created_at", -1))
        
        for order in user_orders:
            order["_id"] = str(order["_id"])
            if "created_at" in order and isinstance(order["created_at"], datetime):
                order["created_at"] = order["created_at"].strftime("%Y-%m-%d %H:%M")
                
        return jsonify(user_orders)
    except Exception as e:
        print(f"Error fetching user orders: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@user_bp.route("/api/products", methods=["GET"])
def get_products():
    if db_layer.products_collection is None:
        return jsonify({"success": False, "message": "Database error"}), 500
    snapshot = get_recommender_snapshot()
    popularity = snapshot.get("popularity", Counter())

    category = (request.args.get("category", "all") or "all").strip().lower()
    query_text = (request.args.get("q") or request.args.get("search") or "").strip().lower()
    brand = normalize_text_value(request.args.get("brand"))
    tags_param = (request.args.get("tags") or "").strip().lower()
    tag_mode = (request.args.get("tag_mode") or "any").strip().lower()
    sort_by = (request.args.get("sort") or ("relevance" if query_text else "rating_desc")).strip().lower()
    limit_param = request.args.get("limit")

    try:
        min_rating = float(request.args.get("min_rating", 0) or 0)
    except (TypeError, ValueError):
        min_rating = 0

    try:
        min_price = float(request.args.get("min_price", 0) or 0)
    except (TypeError, ValueError):
        min_price = 0

    try:
        max_price = float(request.args.get("max_price", 0) or 0)
    except (TypeError, ValueError):
        max_price = 0

    raw_min_reviews = (
        request.args.get("min_reviews")
        or request.args.get("reviews")
        or request.args.get("review_count_min")
        or 0
    )
    raw_max_reviews = request.args.get("max_reviews", 0)
    try:
        min_reviews = max(0, int(raw_min_reviews or 0))
    except (TypeError, ValueError):
        min_reviews = 0
    try:
        max_reviews = max(0, int(raw_max_reviews or 0))
    except (TypeError, ValueError):
        max_reviews = 0

    try:
        limit = max(1, min(int(limit_param), 200)) if limit_param is not None else None
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "limit must be a number"}), 400

    tags_filter = [normalize_text_value(tag) for tag in tags_param.split(",") if normalize_text_value(tag)]
    products = list(snapshot.get("catalog", []))
    review_stats = get_product_review_stats([product.get("name") for product in products if product.get("name")])
    products = [apply_product_review_stats(product, review_stats) for product in products]

    if category != "all":
        products = [
            product for product in products
            if (product.get("category") or "").strip().lower() == category
        ]

    if brand:
        products = [
            product for product in products
            if get_product_brand_value(product) == brand
        ]

    if tags_filter:
        requested_tags = set(tags_filter)
        if tag_mode == "all":
            products = [
                product for product in products
                if requested_tags.issubset(set(get_product_tags(product)))
            ]
        else:
            products = [
                product for product in products
                if requested_tags.intersection(set(get_product_tags(product)))
            ]

    if min_rating > 0:
        products = [
            product for product in products
            if float(product.get("rating") or 0) >= min_rating
        ]

    if min_reviews > 0:
        products = [
            product for product in products
            if get_product_review_count(product) >= min_reviews
        ]

    if max_reviews > 0:
        products = [
            product for product in products
            if get_product_review_count(product) <= max_reviews
        ]

    if min_price > 0:
        products = [
            product for product in products
            if float(product.get("price") or 0) >= min_price
        ]

    if max_price > 0:
        products = [
            product for product in products
            if float(product.get("price") or 0) <= max_price
        ]

    relevance_scores = {}
    search_score_map = {}
    if query_text:
        ranked_entries = rank_products_by_content_query(
            query_text,
            products,
            tfidf_model=snapshot.get("tfidf_model"),
            include_scores=True,
            min_score=SEARCH_MIN_CONTENT_SCORE
        )
        relevance_scores = {
            (entry.get("product") or {}).get("name"): float(entry.get("score", 0) or 0)
            for entry in ranked_entries
            if (entry.get("product") or {}).get("name")
        }
        products = [entry.get("product") for entry in ranked_entries if entry.get("product")]
        search_score_map = build_search_score_map(products, relevance_scores, popularity)

        if sort_by == "price_asc":
            products.sort(key=lambda product: float((product or {}).get("price") or 0))
        elif sort_by == "price_desc":
            products.sort(key=lambda product: float((product or {}).get("price") or 0), reverse=True)
        elif sort_by == "rating_desc":
            products.sort(
                key=lambda product: (
                    get_product_rating_value(product),
                    get_product_review_count(product),
                    relevance_scores.get((product or {}).get("name"), 0)
                ),
                reverse=True
            )
        elif sort_by == "popularity_desc":
            products.sort(
                key=lambda product: (
                    float(popularity.get((product or {}).get("name"), 0)),
                    get_product_quality_score(product),
                    relevance_scores.get((product or {}).get("name"), 0)
                ),
                reverse=True
            )
        elif sort_by == "reviews_desc":
            products.sort(
                key=lambda product: (
                    get_product_review_count(product),
                    get_product_rating_value(product),
                    relevance_scores.get((product or {}).get("name"), 0)
                ),
                reverse=True
            )
        else:
            products.sort(
                key=lambda product: (
                    float((search_score_map.get((product or {}).get("name"), {}) or {}).get("hybrid", 0)),
                    float((search_score_map.get((product or {}).get("name"), {}) or {}).get("relevance", 0)),
                    get_product_quality_score(product)
                ),
                reverse=True
            )
    else:
        if sort_by == "price_asc":
            products.sort(key=lambda product: float((product or {}).get("price") or 0))
        elif sort_by == "price_desc":
            products.sort(key=lambda product: float((product or {}).get("price") or 0), reverse=True)
        elif sort_by == "reviews_desc":
            products.sort(key=lambda product: get_product_review_count(product), reverse=True)
        elif sort_by == "popularity_desc":
            products.sort(key=lambda product: float(popularity.get((product or {}).get("name"), 0)), reverse=True)
        else:
            products.sort(
                key=lambda product: (
                    get_product_rating_value(product),
                    get_product_review_count(product),
                    get_product_quality_score(product),
                    (product or {}).get("name", "")
                ),
                reverse=True
            )

    serialized_products = [serialize_product(p, review_stats=review_stats) for p in (products[:limit] if limit else products)]
    return jsonify({
        "success": True,
        "count": len(serialized_products),
        "total_matches": len(products),
        "filters": {
            "category": category,
            "brand": brand,
            "min_rating": min_rating,
            "min_reviews": min_reviews,
            "min_price": min_price,
            "max_price": max_price,
            "sort": sort_by,
            "limit": limit
        },
        "products": serialized_products
    })

@user_bp.route("/api/search", methods=["GET"])
def search_products():
    return get_products()


@user_bp.route("/api/deals/today", methods=["GET"])
def get_todays_deals():
    if db_layer.products_collection is None:
        return jsonify({"success": False, "message": "Database error"}), 500

    category = request.args.get("category")
    limit_param = request.args.get("limit")
    
    try:
        try:
            limit = (
                int(limit_param)
                if limit_param is not None
                else TODAYS_DEALS_DEFAULT_LIMIT
            )
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "limit must be a number"}), 400

        snapshot = get_recommender_snapshot()
        user_id = get_current_user_id()
        deals = build_todays_deals(
            limit=limit,
            category=category,
            user_id=user_id,
            snapshot=snapshot
        )

        return jsonify({
            "success": True,
            "date": datetime.utcnow().date().isoformat(),
            "category": category or "all",
            "personalized": bool(user_id),
            "count": len(deals),
            "deals": deals
        })
    except Exception as e:
        current_app.logger.error(f"Error building today's deals: {str(e)}")
        return jsonify({
            "success": False, 
            "message": "An internal error occurred while fetching deals",
            "error": str(e) if current_app.debug else None
        }), 500

@user_bp.route("/api/recommendations", methods=["GET"])
def get_recommendations():
    if db_layer.products_collection is None:
        return jsonify({"success": False, "message": "Database error"}), 500

    product_name = (request.args.get("product_name") or request.args.get("product") or "").strip()
    limit_param = request.args.get("limit", 6)

    try:
        limit = max(1, min(int(limit_param), 20))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "limit must be a number"}), 400

    if not product_name:
        return jsonify({"success": False, "message": "Product name is required"}), 400

    try:
        # Use the new recommendation system
        recommendations = get_recommendations_for_product(product_name, limit)
        
        # Format the response to match the expected structure
        formatted_recommendations = []
        for rec in recommendations:
            product = rec["product"]
            # Convert ObjectId to string if present
            if "_id" in product and hasattr(product["_id"], '__str__'):
                product["_id"] = str(product["_id"])
            
            formatted_recommendations.append({
                "product": product,
                "score": rec["score"],
                "reason": rec.get("reason"),
                "matched_tags": rec.get("matched_tags") or []
            })

        return jsonify({
            "success": True,
            "recommendations": formatted_recommendations,
            "frequently_bought_together": []  # Not implemented in new system yet
        })
    except Exception as e:
        print(f"Error getting recommendations: {e}")
        return jsonify({"success": False, "message": "Error generating recommendations"}), 500

@user_bp.route("/api/reviews", methods=["GET"])
def get_reviews():
    if db_layer.reviews_collection is None:
        return jsonify({"success": False, "message": "Database error"}), 500
    product_name = (request.args.get("product") or "").strip()
    if not product_name:
        return jsonify({"success": False, "message": "Product name is required"}), 400
    try:
        reviews = list(db_layer.reviews_collection.find({"product_name": product_name}).sort("created_at", -1))
        for r in reviews:
            if not r.get("sentiment"):
                r["sentiment"] = analyze_sentiment_text(r.get("comment", ""), r.get("rating"))
            r["_id"] = str(r["_id"])
        return jsonify({"success": True, "reviews": reviews})
    except Exception as e:
        return jsonify({"success": False, "message": "Database error", "error": str(e)}), 500

@user_bp.route("/api/reviews", methods=["POST"])
def add_review():
    if not get_current_user_id():
        return jsonify({"success": False, "message": "Login required"}), 401
    if db_layer.reviews_collection is None:
        return jsonify({"success": False, "message": "Database error"}), 500
    data = request.get_json() or {}
    product_name = (data.get("product_name") or "").strip()
    comment = (data.get("comment") or "").strip()
    rating = data.get("rating")

    if not product_name or not comment:
        return jsonify({"success": False, "message": "Product name and comment are required"}), 400
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Rating must be an integer"}), 400
        
    user_id = get_current_user_id()
    user_name = (data.get("user_name") or "").strip() or (session.get("user_name") or "User")
    sentiment = analyze_sentiment_text(comment, rating)

    review_doc = {
        "product_name": product_name,
        "user_id": user_id,
        "user_name": user_name,
        "rating": rating,
        "comment": comment,
        "sentiment": sentiment,
        "created_at": datetime.utcnow()
    }

    try:
        result = db_layer.reviews_collection.insert_one(review_doc)
        review_doc["_id"] = str(result.inserted_id)
        recompute_product_rating(product_name)
        mark_recommender_dirty()
        return jsonify({"success": True, "review": review_doc})
    except Exception as e:
        return jsonify({"success": False, "message": "Failed to save review", "error": str(e)}), 500

@user_bp.route("/api/contact", methods=["POST"])
def contact_submit():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    message = (data.get("message") or "").strip()
    
    if not name or not email or not message:
        return jsonify({"success": False, "message": "All fields are required"}), 400
        
    query_doc = {
        "name": name,
        "email": email,
        "message": message,
        "status": "Pending",
        "created_at": datetime.utcnow()
    }
    
    try:
        if db_layer.queries_collection is not None:
            db_layer.queries_collection.insert_one(query_doc)
            return jsonify({"success": True})
        return jsonify({"success": False, "message": "Database not connected"}), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@user_bp.route("/api/support/chat", methods=["POST"])
def support_chat():
    try:

        data = request.get_json() or {}
        message = (data.get("message") or "").strip()
        session_id = (data.get("session_id") or "default_session").strip()
        
        if not message:

            return jsonify({"success": False, "message": "Message is required"}), 400
            
        print(f"[SupportAPI] Chat Request - Session: {session_id}, Msg: {message[:30]}...")
        
        # 1. Build Context
        print(f"[SupportAPI] Building context for user: {session.get('user_id')}")
        context = build_support_chat_context(message, session_id=session_id, user_id=session.get("user_id"))
        
        # 2. Analyze Sentiment (Optional enrichment)
        try:
            sentiment_payload = analyze_sentiment_text(message)
            if sentiment_payload:
                context["sentiment"] = sentiment_payload
        except Exception as se:
            print(f"[SupportAPI] Sentiment analysis skipped: {se}")

        # 3. Get response from engine
        print(f"[SupportAPI] Fetching bot payload for message: '{message[:30]}...'")
        payload = get_bot_payload(message, context=context)
        
        # 4. Store in session for continuity (volatile)
        _chat_sessions[session_id].append({"role": "user", "text": message})
        _chat_sessions[session_id].append({"role": "bot", "text": payload.get("reply", "")})
        _chat_sessions[session_id] = _chat_sessions[session_id][-20:]

        # 5. Safe Serialization
        # Remove any non-serializable objects from the payload if they exist
        serializable_payload = {
            "success": True,
            "reply": str(payload.get("reply", "")),
            "suggestions": list(payload.get("suggestions", [])),
            "products": list(payload.get("products", [])),
            "category": payload.get("category"),
            "intent": payload.get("intent")
        }
        
        print(f"[SupportAPI] Success. Intent: {serializable_payload.get('intent')}")
        return jsonify(serializable_payload)

    except Exception as e:
        print(f"[SupportAPI] CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "reply": "I'm having a bit of trouble connecting to my knowledge base right now. Could you please try again in a moment?",
            "suggestions": ["Show trending products", "Support hours"],
            "error_fallback": True
        })


@user_bp.route("/api/escalate", methods=["POST"])
def escalate_to_human():
    data = request.get_json() or {}
    session_id = data.get("session_id", "anonymous")
    message = data.get("message", "User requested human agent.")
    
    return jsonify({
        "success": True, 
        "reply": "Transitioning you to a human expert... I've shared our conversation history with them. They will join shortly.",
        "suggestions": ["Support hours", "Payment options"]
    })

@user_bp.route("/api/sentiment", methods=["POST"])
def analyze_sentiment():
    data = request.get_json() or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"success": False, "message": "Text is required"}), 400

    payload = analyze_sentiment_text(text)
    if payload is None:
        return jsonify({
            "success": False,
            "message": "Sentiment model not available"
        }), 500

    return jsonify({
        "success": True,
        "label": payload.get("label"),
        "score": payload.get("score")
    })

@user_bp.route("/api/recommendations/status", methods=["GET"])
def get_recommendation_status():
    snapshot = get_recommender_snapshot()
    association_model = snapshot.get("association_model") or {}
    return jsonify({
        "success": True,
        "trained_at": snapshot.get("trained_at").isoformat() if snapshot.get("trained_at") else None,
        "product_count": snapshot.get("product_count", 0),
        "interaction_user_count": len(snapshot.get("user_interaction_matrix", {})),
        "association_rule_count": int(association_model.get("rule_count", 0) or 0),
        "association_order_count": int(association_model.get("total_orders", 0) or 0),
        "snapshot_ttl_seconds": RECOMMENDER_SNAPSHOT_TTL_SECONDS
    })

# --- Forgot Password API Routes ---
@user_bp.route("/api/forgot_password/send_otp", methods=["POST"])
def forgot_password_send_otp():
    if db_layer.users_collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500

    data = request.get_json() or {}
    method = data.get("method")
    value = normalize_email(data.get("value"))

    if method != "email" or not value:
        return jsonify({"success": False, "message": "Email is required"}), 400

    user = db_layer.users_collection.find_one({"email": value})
    if not user:
        return jsonify({"success": False, "message": "No account found with this email"}), 404

    otp = generate_otp()
    
    # Store OTP in DB
    db_layer.users_collection.update_one({"_id": user["_id"]}, {"$set": {
        "reset_otp": otp,
        "reset_otp_expires": datetime.utcnow() + timedelta(minutes=10)
    }})
    
    success, error = send_email_otp(value, otp)
    if success:
        return jsonify({"success": True, "message": "OTP sent to your email", "otp": otp})  # Return OTP for demo handling in testing
    else:
        return jsonify({"success": False, "message": f"Failed to send email: {error}"}), 500

@user_bp.route("/api/forgot_password/verify_otp", methods=["POST"])
def forgot_password_verify_otp():
    if db_layer.users_collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500

    data = request.get_json() or {}
    value = normalize_email(data.get("value"))
    otp = data.get("otp", "").strip()

    if not value or not otp:
        return jsonify({"success": False, "message": "Email and OTP are required"}), 400

    user = db_layer.users_collection.find_one({"email": value})
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    if user.get("reset_otp") == otp:
        if datetime.utcnow() < user.get("reset_otp_expires", datetime.min):
            # In a production app you'd set a secure verified flag here
            db_layer.users_collection.update_one({"_id": user["_id"]}, {"$set": {"reset_verified": True}})
            return jsonify({"success": True, "message": "OTP verified successfully"})
        return jsonify({"success": False, "message": "OTP has expired"}), 401

    return jsonify({"success": False, "message": "Invalid OTP"}), 401

@user_bp.route("/api/forgot_password/reset", methods=["POST"])
def forgot_password_reset():
    if db_layer.users_collection is None:
        return jsonify({"success": False, "message": "Database connection error"}), 500

    data = request.get_json() or {}
    value = normalize_email(data.get("value"))
    new_password = data.get("newPassword", "")

    if not value or not new_password:
        return jsonify({"success": False, "message": "Missing information"}), 400

    user = db_layer.users_collection.find_one({"email": value})
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    if not user.get("reset_verified"):
        return jsonify({"success": False, "message": "Please verify your OTP first"}), 403

    is_valid_password, password_error = validate_password(new_password)
    if not is_valid_password:
        return jsonify({"success": False, "message": password_error}), 400

    db_layer.users_collection.update_one({"_id": user["_id"]}, {
        "$set": {"password": hash_password(new_password)},
        "$unset": {"reset_otp": "", "reset_otp_expires": "", "reset_verified": ""}
    })

    return jsonify({"success": True, "message": "Password successfully reset"})
