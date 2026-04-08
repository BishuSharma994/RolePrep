from urllib.parse import quote, unquote

from pymongo import MongoClient

from backend.utils.env_loader import env_search_paths, get_env_value, load_environment

load_environment()

mongo_uri = get_env_value("MONGO_URI")
if not mongo_uri:
    raise ValueError(f"Missing MONGO_URI | searched: {env_search_paths()}")


def normalize_mongo_uri(uri: str) -> str:
    if "://" not in uri:
        return uri

    scheme, remainder = uri.split("://", 1)
    if "@" not in remainder:
        return uri

    authority, suffix = (remainder.split("/", 1) + [""])[:2]
    suffix = f"/{suffix}" if suffix else ""

    credentials, hosts = authority.rsplit("@", 1)
    if ":" not in credentials:
        return uri

    username, password = credentials.split(":", 1)
    encoded_username = quote(unquote(username), safe="")
    encoded_password = quote(unquote(password), safe="")
    return f"{scheme}://{encoded_username}:{encoded_password}@{hosts}{suffix}"


client = MongoClient(normalize_mongo_uri(mongo_uri))
db = client["roleprep"]
users = db["users"]
payments = db["payments"]
webhooks = db["webhooks"]
audit_logs = db["audit_logs"]
rate_limits = db["rate_limits"]
feedbacks = db["feedbacks"]


def init_db():
    users.create_index("user_id", unique=True)
    users.create_index("last_active_at")
    users.create_index("created_at")
    payments.create_index("payment_id", unique=True)
    payments.create_index("status")
    webhooks.create_index("event_id", unique=True)
    webhooks.create_index("event_type")
    webhooks.create_index("received_at")
    audit_logs.create_index("timestamp")
    rate_limits.create_index("user_id", unique=True)
    feedbacks.create_index("session_id")
    feedbacks.create_index("user_id")
    feedbacks.create_index("created_at")
