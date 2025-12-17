import json
import os
import sys
from functools import partial

import pika
from dotenv import load_dotenv


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


def consume(queue_name: str):
    conn = get_connection()
    channel = conn.channel()
    channel.queue_declare(queue=queue_name, durable=True)

    def handle(ch, method, properties, body):
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            payload = body.decode("utf-8", errors="replace")
        print(f"[x] Received from {queue_name}: {payload}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=queue_name, on_message_callback=handle, auto_ack=False)
    print(f"[*] Waiting for messages in '{queue_name}'. Press CTRL+C to exit.")
    channel.start_consuming()


def main():
    load_dotenv()
    queue_name = os.getenv("RABBITMQ_QUEUE")
    student = os.getenv("STUDENT_NAME", "")
    if not queue_name:
        queue_name = f"notes_tasks_{student}" if student else "notes_tasks"
    consume(queue_name)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped")
        sys.exit(0)
