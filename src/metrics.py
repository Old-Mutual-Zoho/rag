# src/metrics.py
import time
from src.database.db_connection import get_db_connection  # assumes you have a helper to connect to your DB

def record_retrieval_accuracy(score, query_id=None):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO rag_metrics (metric_type, value, query_id, timestamp)
            VALUES (%s, %s, %s, NOW())
            """,
            ("retrieval_accuracy", score, query_id)
        )
    conn.commit()
    conn.close()

def record_confidence(conf, query_id=None):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO rag_metrics (metric_type, value, query_id, timestamp)
            VALUES (%s, %s, %s, NOW())
            """,
            ("confidence_score", conf, query_id)
        )
    conn.commit()
    conn.close()

def record_latency(start_time, query_id=None):
    latency = time.time() - start_time
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO rag_metrics (metric_type, value, query_id, timestamp)
            VALUES (%s, %s, %s, NOW())
            """,
            ("response_latency", latency, query_id)
        )
    conn.commit()
    conn.close()

def record_fallback(query_id=None):
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO rag_metrics (metric_type, value, query_id, timestamp)
            VALUES (%s, %s, %s, NOW())
            """,
            ("fallbacks", 1, query_id)
        )
    conn.commit()
    conn.close()