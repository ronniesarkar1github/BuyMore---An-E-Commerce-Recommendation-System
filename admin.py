import core.database as db_layer
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, current_app
from bson import ObjectId
from datetime import datetime, timedelta
import functools
import os
import re



from core.utils import (
    generate_otp, send_email_otp, create_otp_record
)

admin_bp = Blueprint('admin', __name__, 
                     template_folder='../admin/templates',
                     static_folder='../admin/static',
                     static_url_path='/admin/static')


# --- Middleware: Protect Admin Routes ---
def admin_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_id'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Routes: Auth ---
@admin_bp.route('/login', methods=['GET'])
def login():
    return render_template('login.html')

@admin_bp.route('/api/login', methods=['POST'])
def api_login():
    try:
        data = request.get_json() or {}
        email = data.get('email', '').strip().lower()
        if not email:
            return jsonify({"success": False, "message": "Email Required"}), 400

        if db_layer.admins_collection is None:
            return jsonify({"success": False, "message": "Backend Error: DB Connection Failed"}), 500

        admin = db_layer.admins_collection.find_one({"email": email})
        
        if admin:
            otp = generate_otp()
            db_layer.admins_collection.update_one({"_id": admin["_id"]}, {"$set": {
                "otp": otp,
                "otp_expires": datetime.utcnow() + timedelta(minutes=10)
            }})
            # Note: send_email_otp handles both real email and console logging
            success, error = send_email_otp(email, otp, purpose="admin_login")
            if success:
                return jsonify({"success": True, "message": "OTP sent to email", "email": email})
            else:
                return jsonify({"success": False, "message": f"Email service error: {error}"}), 503
        
        return jsonify({"success": False, "message": "Access denied"}), 401
    
    except Exception as e:
        print(f"ADMIN LOGIN CRASH: {e}")
        return jsonify({"success": False, "message": f"Critical Server Error: {str(e)}"}), 500

@admin_bp.route('/api/verify-otp', methods=['POST'])
def verify_otp():
    try:
        data = request.get_json() or {}
        email = data.get('email', '').strip().lower()
        otp = data.get('otp', '')
        
        if not email or not otp:
            return jsonify({"success": False, "message": "Email and OTP are required"}), 400

        if db_layer.admins_collection is None:
             return jsonify({"success": False, "message": "Backend Error: DB Connection Failed"}), 500

        admin = db_layer.admins_collection.find_one({"email": email})
        
        if admin and admin.get('otp') == otp:
            if datetime.utcnow() < admin.get('otp_expires', datetime.min):
                session['admin_id'] = str(admin['_id'])
                session['admin_email'] = admin['email']
                db_layer.admins_collection.update_one({"_id": admin["_id"]}, {"$unset": {"otp": "", "otp_expires": ""}})
                return jsonify({"success": True})
            return jsonify({"success": False, "message": "OTP expired"}), 401
            
        return jsonify({"success": False, "message": "Invalid OTP"}), 401
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@admin_bp.route('/logout')
def logout():
    session.pop('admin_id', None)
    session.pop('admin_email', None)
    return redirect(url_for('admin.login'))

# --- Routes: Main UI ---
@admin_bp.route('/')
@admin_required
def dashboard():
    return render_template('dashboard.html')

@admin_bp.route('/products')
@admin_required
def products():
    return render_template('products.html')

@admin_bp.route('/orders')
@admin_required
def orders():
    return render_template('orders.html')

@admin_bp.route('/payments')
@admin_required
def payments():
    return render_template('payments.html')

@admin_bp.route('/queries')
@admin_required
def queries():
    return render_template('queries.html')

# --- API: Analytics ---
@admin_bp.route('/api/stats')
@admin_required
def stats():
    try:
        if db_layer.orders_collection is None or db_layer.products_collection is None:
            return jsonify({"success": False, "message": "Database not connected"}), 500
        
        total_orders = db_layer.orders_collection.count_documents({})
        total_products = db_layer.products_collection.count_documents({})
        
        orders = list(db_layer.orders_collection.find({"status": {"$ne": "Cancelled"}}))
        total_revenue = sum(float(order.get('total') or order.get('total_amount') or 0) for order in orders)
        
        recent_orders = list(db_layer.orders_collection.find().sort("created_at", -1).limit(5))
        for order in recent_orders:
            order["_id"] = str(order["_id"])
            if 'created_at' in order and isinstance(order['created_at'], datetime):
                order['created_at'] = order['created_at'].strftime("%Y-%m-%d %H:%M")

        return jsonify({
            "total_orders": total_orders,
            "total_products": total_products,
            "total_revenue": round(total_revenue, 2),
            "recent_orders": recent_orders
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- API: Products ---
@admin_bp.route('/api/products', methods=['GET'])
@admin_required
def admin_get_products():
    if db_layer.products_collection is None: return jsonify([])
    products = list(db_layer.products_collection.find())
    for p in products:
        p['_id'] = str(p['_id'])
    return jsonify(products)

@admin_bp.route('/api/products', methods=['POST'])
@admin_required
def add_product():
    data = request.get_json() or {}
    if db_layer.products_collection is None: return jsonify({"success": False})
    
    try:
        product = {
            "name": data['name'],
            "price": float(data['price']),
            "description": data['description'],
            "category": data['category'],
            "stock": int(data['stock']),
            "image": data.get('image', ''),
            "rating": 0,
            "review_count": 0,
            "created_at": datetime.utcnow()
        }
        db_layer.products_collection.insert_one(product)
        from core.recommender import mark_recommender_dirty
        mark_recommender_dirty()
        try:
            from productrecommendation import reload_recommendation_model
            reload_recommendation_model()
        except Exception as e:
            current_app.logger.warning(f"Recommendation model reload failed: {e}")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

@admin_bp.route('/api/products/<id>', methods=['PUT', 'DELETE'])
@admin_required
def manage_product(id):
    if db_layer.products_collection is None: return jsonify({"success": False})
    
    if request.method == 'DELETE':
        db_layer.products_collection.delete_one({"_id": ObjectId(id)})
        from core.recommender import mark_recommender_dirty
        mark_recommender_dirty()
        try:
            from productrecommendation import reload_recommendation_model
            reload_recommendation_model()
        except Exception as e:
            current_app.logger.warning(f"Recommendation model reload failed: {e}")
        return jsonify({"success": True})
    
    data = request.get_json() or {}
    try:
        update_data = {
            "name": data['name'],
            "price": float(data['price']),
            "description": data['description'],
            "category": data['category'],
            "stock": int(data['stock'])
        }
        if 'image' in data:
            update_data['image'] = data['image']
            
        db_layer.products_collection.update_one({"_id": ObjectId(id)}, {"$set": update_data})
        from core.recommender import mark_recommender_dirty
        mark_recommender_dirty()
        try:
            from productrecommendation import reload_recommendation_model
            reload_recommendation_model()
        except Exception as e:
            current_app.logger.warning(f"Recommendation model reload failed: {e}")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

# --- API: Orders ---
@admin_bp.route('/api/orders', methods=['GET'])
@admin_required
def admin_get_orders():
    if db_layer.orders_collection is None:
        return jsonify([])
    
    try:
        orders = list(db_layer.orders_collection.find().sort("created_at", -1))
        for o in orders:
            o['_id'] = str(o['_id'])
            if 'created_at' in o and isinstance(o['created_at'], datetime):
                o['created_at'] = o['created_at'].strftime("%Y-%m-%d %H:%M")
        return jsonify(orders)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/api/orders/<id>', methods=['GET'])
@admin_required
def get_order_detail(id):
    if db_layer.orders_collection is None: return jsonify({})
    try:
        order = db_layer.orders_collection.find_one({"_id": ObjectId(id)})
        if order:
            order['_id'] = str(order['_id'])
            if 'created_at' in order and isinstance(order['created_at'], datetime):
                order['created_at'] = order['created_at'].strftime("%Y-%m-%d %H:%M")
            return jsonify(order)
        return jsonify({"success": False}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/api/orders/<id>/status', methods=['PATCH'])
@admin_required
def update_order_status(id):
    data = request.get_json() or {}
    status = data.get('status')
    if db_layer.orders_collection is None: return jsonify({"success": False})
    try:
        db_layer.orders_collection.update_one({"_id": ObjectId(id)}, {"$set": {"status": status}})
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

# --- API: Payments ---
@admin_bp.route('/api/payments', methods=['GET'])
@admin_required
def admin_get_payments():
    if db_layer.payments_collection is None: return jsonify([])
    try:
        # Fetch directly from payments collection
        payments_cursor = list(db_layer.payments_collection.find().sort("created_at", -1))
        payments = []
        for p in payments_cursor:
            payments.append({
                "_id": str(p["_id"]),
                "order_id": p.get("order_id", "N/A"),
                "user_email": p.get("user_email", "N/A"),
                "method": p.get("method", "CARD"),
                "amount": p.get("amount", 0),
                "payment-status": p.get("payment-status", "Paid")
            })
        return jsonify(payments)
    except Exception as e:
        print(f"Error fetching payments: {e}")
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/api/payments/<id>/status', methods=['PATCH'])
@admin_required
def admin_update_payment_status(id):
    if db_layer.payments_collection is None or db_layer.orders_collection is None:
        return jsonify({"success": False, "message": "Database error"}), 500
    try:
        data = request.get_json() or {}
        new_status = data.get("status", "Paid")
        
        # 1. Update the payment record
        payment_record = db_layer.payments_collection.find_one({"_id": ObjectId(id)})
        if not payment_record:
            return jsonify({"success": False, "message": "Payment record not found"}), 404
            
        db_layer.payments_collection.update_one({"_id": ObjectId(id)}, {"$set": {"payment-status": new_status}})
        
        # 2. Update the associated order (if order_id exists)
        order_id = payment_record.get("order_id")
        if order_id and order_id != "N/A":
            try:
                db_layer.orders_collection.update_one({"_id": ObjectId(order_id)}, {"$set": {"payment-status": new_status}})
            except Exception as oe:
                print(f"Failed to update linked order status: {oe}")
                
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error updating payment status: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# --- API: Contact Queries ---
@admin_bp.route('/api/queries', methods=['GET'])
@admin_required
def admin_get_queries():
    if db_layer.contact_reports_collection is None: return jsonify([])
    try:
        queries = list(db_layer.contact_reports_collection.find().sort("created_at", -1))
        for q in queries:
            q['_id'] = str(q['_id'])
            if 'created_at' in q and isinstance(q['created_at'], datetime):
                q['created_at'] = q['created_at'].strftime("%Y-%m-%d %H:%M")
        return jsonify(queries)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/api/queries/<id>/status', methods=['PATCH'])
@admin_required
def update_query_status(id):
    data = request.get_json() or {}
    status = data.get('status')
    response = data.get('response', '')
    if db_layer.contact_reports_collection is None: return jsonify({"success": False})
    try:
        db_layer.contact_reports_collection.update_one({"_id": ObjectId(id)}, {"$set": {
            "status": status,
            "admin_response": response,
            "updated_at": datetime.utcnow()
        }})
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400
