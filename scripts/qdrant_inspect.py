import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient


def main():
    load_dotenv()
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    student = os.getenv("STUDENT_NAME", "").strip().lower()
    col = f"notes_vectors_{student}" if student else "notes_vectors"

    client = QdrantClient(host=host, port=port, timeout=3.0)

    print(f"Host: {host}:{port}")
    print("Collections:")
    cols = client.get_collections()
    for c in cols.collections:
        print(f" - {c.name}")

    if col not in [c.name for c in cols.collections]:
        print(f"Collection {col} not found.")
        return

    info = client.get_collection(col)
    count = client.count(col, exact=True).count
    print(f"\nCollection: {col}")
    print(f"Vectors size: {info.config.params.vectors.size}")
    print(f"Distance: {info.config.params.vectors.distance}")
    print(f"Points count: {count}")

    if count == 0:
        return

    # покажем первые несколько точек (id и payload)
    points = client.scroll(col, limit=10, with_payload=True, with_vectors=False)[0]
    print("\nSample points (up to 5):")
    for p in points:
        print(f"id={p.id}, payload={p.payload}")


if __name__ == "__main__":
    main()
