import os
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

users_col = db["users"]
payments_col = db["payments"]
webhooks_col = db["webhooks"]


def init_db():
    users_col.create_index("user_id", unique=True)
    payments_col.create_index("payment_id", unique=True)
    webhooks_col.create_index("event_id", unique=True)
