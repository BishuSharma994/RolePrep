from urllib.parse import quote, unquote
from pymongo import MongoClient
from dotenv import load_dotenv
import os

# FORCE LOAD ENV (ONLY SOURCE)
load_dotenv("/root/RolePrep/.env")

mongo_uri = os.getenv("MONGO_URI")

if not mongo_uri:
    raise ValueError("MONGO_URI missing")


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

    username = quote(unquote(username), safe="")
    password = quote(unquote(password), safe="")

    return f"{scheme}://{username}:{password}@{hosts}{suffix}"


client = MongoClient(normalize_mongo_uri(mongo_uri))
db = client["roleprep"]

users = db["users"]
payments = db["payments"]
webhooks = db["webhooks"]
audit_logs = db["audit_logs"]
rate_limits = db["rate_limits"]


def init_db():
    users.create_index("user_id", unique=True)
    payments.create_index("payment_id", unique=True)
    webhooks.create_index("event_id", unique=True)
    audit_logs.create_index("timestamp")
    rate_limits.create_index("user_id", unique=True)
