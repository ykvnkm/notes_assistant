import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from pymongo import MongoClient


def sanitize_suffix(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def get_db_and_collection() -> Dict[str, str]:
    base_db = os.getenv("MONGO_DB", "appdb")
    student = os.getenv("STUDENT_NAME", "").strip()
    db_name = f"{base_db}_{student}" if student else base_db
    base_collection = "note_versions"
    collection = (
        f"{base_collection}_{sanitize_suffix(student.lower())}" if student else base_collection
    )
    return {"db_name": db_name, "collection": collection}


def get_client() -> MongoClient:
    host = os.getenv("MONGO_HOST", "localhost")
    port = int(os.getenv("MONGO_PORT", "27017"))
    user = os.getenv("MONGO_USER", "root")
    password = os.getenv("MONGO_PASSWORD", "secret")
    auth_source = os.getenv("MONGO_AUTH_SOURCE", "admin")
    uri = f"mongodb://{user}:{password}@{host}:{port}/?authSource={auth_source}"
    return MongoClient(uri, serverSelectionTimeoutMS=3000)


def save_version(note: Dict[str, Any]) -> Dict[str, Any]:
    """
    note: dict with keys id, title, content, tags, created_at, updated_at
    """
    cfg = get_db_and_collection()
    client = get_client()
    db = client[cfg["db_name"]]
    coll = db[cfg["collection"]]

    note_id = note["id"]
    # find current max version
    last = coll.find_one({"note_id": note_id}, sort=[("version", -1)], projection={"version": 1})
    next_version = int(last["version"]) + 1 if last and "version" in last else 1

    doc = {
        "note_id": note_id,
        "version": next_version,
        "title": note.get("title"),
        "content": note.get("content"),
        "tags": note.get("tags", []),
        "created_at": note.get("created_at"),
        "updated_at": note.get("updated_at"),
        "saved_at": datetime.utcnow(),
    }
    coll.insert_one(doc)
    return doc


def get_versions(note_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    cfg = get_db_and_collection()
    client = get_client()
    db = client[cfg["db_name"]]
    coll = db[cfg["collection"]]
    cursor = (
        coll.find({"note_id": note_id})
        .sort("version", -1)
        .limit(limit)
    )
    versions: List[Dict[str, Any]] = []
    for doc in cursor:
        doc["_id"] = str(doc["_id"])
        versions.append(doc)
    return versions


def get_version(note_id: int, version: int) -> Optional[Dict[str, Any]]:
    cfg = get_db_and_collection()
    client = get_client()
    db = client[cfg["db_name"]]
    coll = db[cfg["collection"]]
    doc = coll.find_one({"note_id": note_id, "version": version})
    if not doc:
        return None
    doc["_id"] = str(doc["_id"])
    return doc


def delete_versions(note_id: int) -> int:
    cfg = get_db_and_collection()
    client = get_client()
    db = client[cfg["db_name"]]
    coll = db[cfg["collection"]]
    res = coll.delete_many({"note_id": note_id})
    return res.deleted_count
