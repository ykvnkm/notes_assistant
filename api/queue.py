import json
import os
from functools import lru_cache
from typing import Dict

import pika


@lru_cache(maxsize=1)
def get_connection():
    host = os.getenv("RABBITMQ_HOST", "zorin.space")
    port = int(os.getenv("RABBITMQ_PORT", "10009"))
    user = os.getenv("RABBITMQ_USER", "guest")
    password = os.getenv("RABBITMQ_PASSWORD", "guest")
    params = pika.ConnectionParameters(
        host=host,
        port=port,
        credentials=pika.PlainCredentials(user, password),
        heartbeat=30,
        blocked_connection_timeout=5,
    )
    return pika.BlockingConnection(params)


def _default_queue_name() -> str:
    student = os.getenv("STUDENT_NAME", "").strip().lower()
    if student:
        return f"notes_tasks_{student}"
    return "notes_tasks"


@lru_cache(maxsize=1)
def get_queue_name() -> str:
    # Если явно указана очередь, берём её. Иначе формируем notes_tasks_<student>.
    return os.getenv("RABBITMQ_QUEUE") or _default_queue_name()


def publish_note_event(action: str, note: Dict) -> None:
    """
    Отправить событие в очередь RabbitMQ.
    action: note_created | note_updated | note_deleted
    note: словарь заметки (id, title, content, tags, timestamps)
    """
    connection = get_connection()
    channel = connection.channel()
    queue_name = get_queue_name()
    channel.queue_declare(queue=queue_name, durable=True)

    payload = json.dumps({"action": action, "note": note}, default=str)
    channel.basic_publish(
        exchange="",
        routing_key=queue_name,
        body=payload.encode("utf-8"),
        properties=pika.BasicProperties(
            delivery_mode=2,  # persistent
            content_type="application/json",
        ),
    )
