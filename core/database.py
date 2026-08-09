from pymongo import MongoClient
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv(override=True)

# Connection Details
MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "ecommerceDB")

if not MONGO_URI:
    raise ValueError("âŒ MONGO_URI is not set in .env file!")

client = None
db = None

# Collections
users_collection = None
cart_collection = None
wishlist_collection = None
products_collection = None
reviews_collection = None
orders_collection = None
click_events_collection = None
payments_collection = None
queries_collection = None
admins_collection = None
contact_reports_collection = None

def init_db():
    global client, db, users_collection, cart_collection, wishlist_collection, \
           products_collection, reviews_collection, orders_collection, \
           click_events_collection, payments_collection, queries_collection, \
           admins_collection, contact_reports_collection

    print(f"Attempting to connect to MongoDB at: {MONGO_URI}")
    try:
        # Initialize Client
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)

        # Verify Connection
        client.admin.command('ping')
        print("âœ… Successfully pinged MongoDB Atlas.")

        # Select Database
        db = client[DATABASE_NAME]
        print(f"âœ… Connected to database: {DATABASE_NAME}")

        # Initialize Collections
        users_collection = db["users"]
        cart_collection = db["carts"]
        wishlist_collection = db["wishlists"]
        products_collection = db["products"]
        reviews_collection = db["reviews"]
        orders_collection = db["orders"]
        click_events_collection = db["click_events"]
        payments_collection = db["payments"]
        queries_collection = db["queries"]
        admins_collection = db["admins"]
        contact_reports_collection = db["contact_reports"]

        print("âœ… All database collections initialized successfully.")

        # List collections to verify
        existing = db.list_collection_names()
        print(f"ðŸ“¦ Collections in DB: {existing}")

        return db

    except Exception as e:
        print(f"âŒ MongoDB connection error: {e}")
        return None


def ensure_db_indexes():
    if users_collection is not None:
        users_collection.create_index("email", unique=True)
    if products_collection is not None:
        products_collection.create_index("name", unique=True)
        products_collection.create_index("category")
        products_collection.create_index("brand")
        products_collection.create_index("price")
        products_collection.create_index("rating")
        products_collection.create_index("review_count")
    if cart_collection is not None:
        cart_collection.create_index("user_id", unique=True)
    if wishlist_collection is not None:
        wishlist_collection.create_index("user_id", unique=True)
    if orders_collection is not None:
        orders_collection.create_index("user_id")
        orders_collection.create_index("created_at")
    if click_events_collection is not None:
        click_events_collection.create_index("user_id")
        click_events_collection.create_index("product_name")
        click_events_collection.create_index("event_type")
        click_events_collection.create_index("source")
        click_events_collection.create_index("created_at")
        click_events_collection.create_index([("user_id", 1), ("created_at", -1)])
    print("âœ… Indexes ensured.")


def get_product_stock(product_name):
    if products_collection is None or not product_name:
        return None
    product = products_collection.find_one({"name": product_name})
    if not product:
        return None
    try:
        return max(0, int(product.get("stock", 0)))
    except (TypeError, ValueError):
        return 0


def get_product_by_name(product_name):
    if products_collection is None or not product_name:
        return None
    return products_collection.find_one(
        {"name": product_name},
        {"name": 1, "category": 1, "brand": 1, "price": 1}
    )


def log_interaction_event(
    user_id,
    product_name,
    event_type="click",
    source="unknown",
    quantity=None,
    metadata=None
):
    from datetime import datetime
    if not user_id or click_events_collection is None or not product_name:
        return False

    product = get_product_by_name(product_name)
    if not product:
        return False

    from core.recommender import normalize_interaction_event_type
    normalized_type = normalize_interaction_event_type(event_type)

    event_doc = {
        "user_id": user_id,
        "product_name": product_name,
        "category": product.get("category"),
        "event_type": normalized_type,
        "source": (source or "unknown").strip(),
        "created_at": datetime.utcnow()
    }

    try:
        quantity_value = max(1, int(quantity)) if quantity is not None else None
    except (TypeError, ValueError):
        quantity_value = None
    if quantity_value is not None:
        event_doc["quantity"] = quantity_value

    if isinstance(metadata, dict) and metadata:
        compact_metadata = {k: v for k, v in metadata.items() if v is not None}
        if compact_metadata:
            event_doc["metadata"] = compact_metadata

    try:
        click_events_collection.insert_one(event_doc)
        return True
    except Exception as e:
        print(f"❌ Error logging interaction: {e}")
        return False




def get_db_status():
    """
    Lightweight health/status payload for diagnostics.
    Never returns credentials.
    """
    status = {
        "connected": False,
        "database": DATABASE_NAME,
        "collections_initialized": False,
        "collections": [],
        "products_count": None,
        "checked_at": datetime.utcnow().isoformat()
    }

    if client is None or db is None:
        return status

    try:
        client.admin.command("ping")
        status["connected"] = True
    except Exception:
        return status

    try:
        cols = db.list_collection_names()
        status["collections"] = cols
        status["collections_initialized"] = all(
            c is not None
            for c in [
                users_collection, cart_collection, wishlist_collection,
                products_collection, reviews_collection, orders_collection,
                click_events_collection, payments_collection, queries_collection,
                admins_collection, contact_reports_collection
            ]
        )
    except Exception:
        pass

    try:
        if products_collection is not None:
            status["products_count"] = products_collection.count_documents({})
    except Exception:
        pass

    return status
