import os
import socket

from dotenv import load_dotenv
import psycopg2
from pymongo import MongoClient
import redis
from qdrant_client import QdrantClient
from neo4j import GraphDatabase
import pika


def log(name: str, ok: bool, detail: str = "") -> None:
    status = "OK" if ok else "FAIL"
    if detail:
        print(f"{name:<10} {status} - {detail}")
    else:
        print(f"{name:<10} {status}")


def load_env() -> None:
    load_dotenv()


def check_tcp(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_postgres():
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    user = os.getenv("POSTGRES_USER", "app")
    password = os.getenv("POSTGRES_PASSWORD", "secret")
    base_db = os.getenv("POSTGRES_DB", "appdb")
    student = os.getenv("STUDENT_NAME", "").strip().lower()
    db = f"{base_db}_{student}" if student else base_db
    dsn = f"host={host} port={port} user={user} password={password} dbname={db} connect_timeout=3"
    if not check_tcp(host, port):
        log("Postgres", False, f"no TCP connection to {host}:{port}")
        return
    try:
        with psycopg2.connect(dsn):
            log("Postgres", True, f"connected to {db}")
    except Exception as exc:
        log("Postgres", False, str(exc))


def check_mongo():
    host = os.getenv("MONGO_HOST", "localhost")
    port = int(os.getenv("MONGO_PORT", "27017"))
    user = os.getenv("MONGO_USER", "root")
    password = os.getenv("MONGO_PASSWORD", "secret")
    base_db = os.getenv("MONGO_DB", "appdb")
    auth_source = os.getenv("MONGO_AUTH_SOURCE", "admin")
    student = os.getenv("STUDENT_NAME", "").strip()
    db = f"{base_db}_{student}" if student else base_db
    if not check_tcp(host, port):
        log("MongoDB", False, f"no TCP connection to {host}:{port}")
        return
    try:
        uri = f"mongodb://{user}:{password}@{host}:{port}/{db}?authSource={auth_source}"
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        dbs = client.list_database_names()
        suffix = "present" if db in dbs else f"not in list {dbs}"
        log("MongoDB", True, f"connected to {db} ({suffix})")
    except Exception as exc:
        log("MongoDB", False, str(exc))


def check_redis():
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    db = int(os.getenv("REDIS_DB", "0"))
    if not check_tcp(host, port):
        log("Redis", False, f"no TCP connection to {host}:{port}")
        return
    try:
        client = redis.Redis(host=host, port=port, db=db, socket_connect_timeout=3, socket_timeout=3)
        client.ping()
        log("Redis", True, f"db {db}")
    except Exception as exc:
        log("Redis", False, str(exc))


def check_qdrant():
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    if not check_tcp(host, port):
        log("Qdrant", False, f"no TCP connection to {host}:{port}")
        return
    try:
        client = QdrantClient(host=host, port=port, timeout=3.0)
        client.get_collections()
        log("Qdrant", True)
    except Exception as exc:
        log("Qdrant", False, str(exc))


def check_neo4j():
    host = os.getenv("NEO4J_HOST", "localhost")
    port = int(os.getenv("NEO4J_PORT", "7687"))
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "secret123")
    uri = f"bolt://{host}:{port}"
    if not check_tcp(host, port):
        log("Neo4j", False, f"no TCP connection to {host}:{port}")
        return
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            session.run("RETURN 1").consume()
        log("Neo4j", True)
    except Exception as exc:
        log("Neo4j", False, str(exc))


def check_rabbit():
    host = os.getenv("RABBITMQ_HOST", "localhost")
    port = int(os.getenv("RABBITMQ_PORT", "5672"))
    user = os.getenv("RABBITMQ_USER", "guest")
    password = os.getenv("RABBITMQ_PASSWORD", "guest")
    if not check_tcp(host, port):
        log("RabbitMQ", False, f"no TCP connection to {host}:{port}")
        return
    try:
        params = pika.ConnectionParameters(
            host=host,
            port=port,
            credentials=pika.PlainCredentials(user, password),
            socket_timeout=3,
            blocked_connection_timeout=3,
        )
        with pika.BlockingConnection(params) as conn:
            conn.process_data_events()
        log("RabbitMQ", True)
    except Exception as exc:
        log("RabbitMQ", False, str(exc))


def main():
    load_env()
    check_postgres()
    check_mongo()
    check_redis()
    check_qdrant()
    check_neo4j()
    check_rabbit()


if __name__ == "__main__":
    main()
