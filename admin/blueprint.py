from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, current_app
from bson import ObjectId
from datetime import datetime, timedelta
import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import functools

admin_bp = Blueprint('admin', __name__, template_folder='templates')

# --- Middleware: Protect Admin Routes ---
def admin_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_id'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

# --- OTP Helper ---
def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

def send_otp_email(recipient_email, otp):
    smtp_server = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("EMAIL_PORT", "587"))
    smtp_user = os.getenv("EMAIL_USERNAME") # Matches .env
    smtp_pass = os.getenv("EMAIL_PASSWORD")
    sender_email = os.getenv("EMAIL_FROM", smtp_user)

    if not all([smtp_user, smtp_pass]):
        print("SMTP credentials missing. Logging OTP to console.")
        print(f"DEBUG: OTP for {recipient_email} is {otp}")
        return True

    # EMERGENCY LOGGING: Write OTP to local file in case email hangs or fails
    try:
        debug_path = os.path.join(os.getcwd(), 'ADMIN_OTP_DEBUG.txt')
        with open(debug_path, 'a') as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Email: {recipient_email} | OTP: {otp}\n")
    except Exception as e:
        print(f"Debug logging failed: {e}")

    try:
        msg = MIMEMultipart("alternative")
        msg['From'] = f"BuyMore Admin <{sender_email}>"
        msg['To'] = recipient_email
        msg['Subject'] = f"BuyMore Admin OTP: {otp}"
        
        logo_url = "https://cdn-icons-png.flaticon.com/512/3144/3144456.png"
        
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f7fbf9; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 40px auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05); border-top: 5px solid #ef4444; }}
                .header {{ background: linear-gradient(135deg, #16123f, #2a2566); padding: 30px 20px; text-align: center; }}
                .header img {{ width: 60px; height: 60px; margin-bottom: 10px; filter: brightness(0) invert(1); }}
                .header h1 {{ color: #ffffff; margin: 0; font-size: 24px; letter-spacing: 1px; }}
                .content {{ padding: 40px 30px; text-align: center; color: #16123f; }}
                .content h2 {{ margin-top: 0; font-size: 22px; color: #ef4444; }}
                .content p {{ font-size: 16px; color: #4f5673; line-height: 1.6; margin-bottom: 30px; }}
                .otp-box {{ background-color: #fef2f2; border: 2px dashed #ef4444; border-radius: 8px; padding: 20px; font-size: 32px; font-weight: bold; color: #ef4444; letter-spacing: 5px; margin: 0 auto 30px auto; max-width: 250px; text-align: center; }}
                .footer {{ background-color: #f1f5f9; padding: 20px; text-align: center; font-size: 14px; color: #64748b; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <img src="{logo_url}" alt="BuyMore Logo" />
                    <h1>BuyMore Admin</h1>
                </div>
                <div class="content">
                    <h2>Admin Authentication required</h2>
                    <p>Hello Admin, a login attempt requires your verification. Use the secure OTP below to access the Admin Dashboard.</p>
                    <div class="otp-box">{otp}</div>
                    <p>This code expires in <strong>10 minutes</strong>. If you did not initiate this login, please investigate potential unauthorized access.</p>
                </div>
                <div class="footer">
                    &copy; {datetime.utcnow().year} BuyMore Admin Portal.
                </div>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(f"Hello Admin,\n\nYour security code for BuyMore Admin Panel is: {otp}\n\nThis code expires in 10 minutes.", 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        # Add timeout to prevent server hang
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending SMTP: {e}")
        return False

# --- Helper: Get DB Handle ---
def get_db():
    db = current_app.config.get('db')
    if db is None:
        print("CRITICAL: Database handle not found in app.config['db']")
    return db

# --- Routes: Auth ---
@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            email = request.json.get('email', '').strip().lower()
            if not email:
                return jsonify({"success": False, "message": "Email Required"}), 400

            db = get_db()
            if db is None:
                return jsonify({"success": False, "message": "Backend Error: DB Connection Failed"}), 500

            admin = db.admins.find_one({"email": email})
            
            if admin:
                otp = generate_otp()
                db.admins.update_one({"_id": admin["_id"]}, {"$set": {
                    "otp": otp,
                    "otp_expires": datetime.utcnow() + timedelta(minutes=10)
                }})
                if send_otp_email(email, otp):
                    return jsonify({"success": True, "message": "OTP sent to email", "email": email})
                else:
                    return jsonify({"success": False, "message": "Email service error. Please try again later."}), 503
            
            return jsonify({"success": False, "message": "Access denied"}), 401
        
        except Exception as e:
            print(f"ADMIN LOGIN CRASH: {e}")
            return jsonify({"success": False, "message": f"Critical Server Error: {str(e)}"}), 500
    
    return render_template('admin/login.html')

@admin_bp.route('/verify-otp', methods=['POST'])
def verify_otp():
    try:
        email = request.json.get('email', '').strip().lower()
        otp = request.json.get('otp', '')
        
        db = get_db()
        if db is None:
             return jsonify({"success": False, "message": "Backend Error: DB Connection Failed"}), 500

        admin = db.admins.find_one({"email": email})
        
        if admin and admin.get('otp') == otp:
            if datetime.utcnow() < admin.get('otp_expires', datetime.min):
                session['admin_id'] = str(admin['_id'])
                session['admin_email'] = admin['email']
                db.admins.update_one({"_id": admin["_id"]}, {"$unset": {"otp": "", "otp_expires": ""}})
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
    return render_template('admin/dashboard.html')

@admin_bp.route('/products')
@admin_required
def products():
    return render_template('admin/products.html')

@admin_bp.route('/orders')
@admin_required
def orders():
    return render_template('admin/orders.html')

@admin_bp.route('/payments')
@admin_required
def payments():
    return render_template('admin/payments.html')

@admin_bp.route('/queries')
@admin_required
def queries():
    return render_template('admin/queries.html')

# --- API: Analytics ---
@admin_bp.route('/api/stats')
@admin_required
def stats():
    try:
        db = get_db()
        if db is None: return jsonify({})
        
        total_orders = db.orders.count_documents({})
        total_products = db.products.count_documents({})
        
        orders = db.orders.find({"status": {"$ne": "Cancelled"}})
        total_revenue = sum(float(order.get('total') or order.get('total_amount') or 0) for order in orders)
        
        recent_orders = list(db.orders.find().sort("created_at", -1).limit(5))
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
def get_products():
    db = get_db()
    if db is None: return jsonify([])
    products = list(db.products.find())
    for p in products:
        p['_id'] = str(p['_id'])
    return jsonify(products)

@admin_bp.route('/api/products', methods=['POST'])
@admin_required
def add_product():
    data = request.json
    db = get_db()
    if db is None: return jsonify({"success": False})
    
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
    db.products.insert_one(product)
    return jsonify({"success": True})

@admin_bp.route('/api/products/<id>', methods=['PUT', 'DELETE'])
@admin_required
def manage_product(id):
    db = get_db()
    if db is None: return jsonify({"success": False})
    
    if request.method == 'DELETE':
        db.products.delete_one({"_id": ObjectId(id)})
        return jsonify({"success": True})
    
    data = request.json
    update_data = {
        "name": data['name'],
        "price": float(data['price']),
        "description": data['description'],
        "category": data['category'],
        "stock": int(data['stock'])
    }
    if 'image' in data:
        update_data['image'] = data['image']
        
    db.products.update_one({"_id": ObjectId(id)}, {"$set": update_data})
    return jsonify({"success": True})

# --- API: Orders ---
@admin_bp.route('/api/orders', methods=['GET'])
@admin_required
def get_orders():
    db = get_db()
    if db is None:
        print("DEBUG: admin.get_orders - DB handle is NONE")
        return jsonify([])
    
    try:
        orders = list(db.orders.find().sort("created_at", -1))
        print(f"DEBUG: admin.get_orders - Found {len(orders)} orders in '{db.name}.orders'")
        
        for o in orders:
            o['_id'] = str(o['_id'])
            if 'created_at' in o and isinstance(o['created_at'], datetime):
                o['created_at'] = o['created_at'].strftime("%Y-%m-%d %H:%M")
        return jsonify(orders)
    except Exception as e:
        print(f"DEBUG: admin.get_orders - EXCEPTION: {str(e)}")
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/api/orders/<id>', methods=['GET'])
@admin_required
def get_order_detail(id):
    db = get_db()
    if db is None: return jsonify({})
    order = db.orders.find_one({"_id": ObjectId(id)})
    if order:
        order['_id'] = str(order['_id'])
        if 'created_at' in order and isinstance(order['created_at'], datetime):
            order['created_at'] = order['created_at'].strftime("%Y-%m-%d %H:%M")
        return jsonify(order)
    return jsonify({"success": False}), 404

@admin_bp.route('/api/orders/<id>/status', methods=['PATCH'])
@admin_required
def update_order_status(id):
    status = request.json.get('status')
    db = get_db()
    if db is None: return jsonify({"success": False})
    db.orders.update_one({"_id": ObjectId(id)}, {"$set": {"status": status}})
    return jsonify({"success": True})

# --- API: Payments ---
@admin_bp.route('/api/payments', methods=['GET'])
@admin_required
def get_payments():
    db = get_db()
    if db is None: return jsonify([])
    payments = list(db.payments.find().sort("created_at", -1))
    for p in payments:
        p['_id'] = str(p['_id'])
        if 'created_at' in p and isinstance(p['created_at'], datetime):
            p['created_at'] = p['created_at'].strftime("%Y-%m-%d %H:%M")
    return jsonify(payments)

# --- API: Contact Queries ---
@admin_bp.route('/api/queries', methods=['GET'])
@admin_required
def get_queries():
    db = get_db()
    if db is None: return jsonify([])
    queries = list(db.queries.find().sort("created_at", -1))
    for q in queries:
        q['_id'] = str(q['_id'])
        if 'created_at' in q and isinstance(q['created_at'], datetime):
            q['created_at'] = q['created_at'].strftime("%Y-%m-%d %H:%M")
    return jsonify(queries)

@admin_bp.route('/api/queries/<id>/status', methods=['PATCH'])
@admin_required
def update_query_status(id):
    status = request.json.get('status')
    response = request.json.get('response', '')
    db = get_db()
    if db is None: return jsonify({"success": False})
    db.queries.update_one({"_id": ObjectId(id)}, {"$set": {
        "status": status,
        "admin_response": response,
        "updated_at": datetime.utcnow()
    }})
    return jsonify({"success": True})

