"""Kafka consumer for real-time loan application processing."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import joblib

from features_v3 import add_features
from src.decision import score_from_probability
from service.flask.config import Settings
from service.flask.model_loader import predict_default, predict_fraud, predict_limit
from service.flask.repositories.mysql_repo import _connect

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logger = logging.getLogger("kafka_consumer")

# Kafka bootstrap servers
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'lending_application')
KAFKA_GROUP_ID = os.getenv('KAFKA_GROUP_ID', 'loan_decision_group')
KAFKA_AUTO_OFFSET_RESET = os.getenv('KAFKA_AUTO_OFFSET_RESET', 'latest')


def _insert_decision(result: dict) -> None:
    """Write a decision result to MySQL realtime_decisions table."""
    conn = _connect(Settings.MYSQL_DB_RT)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO realtime_decisions
                (customer_id, default_probability, default_pred, fraud_probability,
                 fraud_pred, predicted_limit, credit_score)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (
                result.get("customer_id"),
                result.get("default_probability"),
                result.get("default_pred"),
                result.get("fraud_probability"),
                result.get("fraud_pred"),
                result.get("predicted_limit"),
                result.get("credit_score"),
            ))
        conn.commit()
        logger.info("Inserted decision for customer %s", result.get("customer_id"))
    finally:
        conn.close()


def _process_message(msg_value: bytes) -> dict | None:
    """
    Process a single Kafka message (loan application record).
    Returns a decision dict, or None on failure.
    """
    try:
        # Parse JSON payload
        record = json.loads(msg_value)
        customer_id = record.get("customer_id")
        if not customer_id:
            logger.warning("Message missing customer_id, skipping")
            return None

        # Build feature DataFrame
        df = pd.DataFrame([record])

        # Apply feature engineering
        feat_df = add_features(df).replace([pd.NA, np.inf, -np.inf], None)

        # Run predictions
        try:
            default_result = predict_default([record])
            fraud_result = predict_fraud([record])
            limit_result = predict_limit([record])

            default_prob = default_result[0]["default_probability"]
            fraud_prob = fraud_result[0]["fraud_probability"]
            limit_val = limit_result[0]["predicted_limit"]
        except Exception as e:
            logger.error("Prediction failed for customer %s: %s", customer_id, e)
            # Fallback to default values
            default_prob = 0.5
            fraud_prob = 0.1
            limit_val = 10000.0

        # Calculate credit score
        credit_score = score_from_probability([default_prob])[0]

        decision = {
            "customer_id": customer_id,
            "default_probability": float(default_prob),
            "default_pred": int(default_prob >= 0.5),
            "fraud_probability": float(fraud_prob),
            "fraud_pred": int(fraud_prob >= 0.5),
            "predicted_limit": float(max(0, limit_val)),
            "credit_score": float(credit_score),
        }
        return decision

    except json.JSONDecodeError as e:
        logger.error("Failed to parse message JSON: %s", e)
        return None
    except Exception as e:
        logger.error("Unexpected error processing message: %s", e)
        return None


def _run_with_kafka():
    """Run the consumer using the kafka-python library (if available)."""
    try:
        from kafka import KafkaConsumer
    except ImportError:
        logger.error("kafka-python not installed. Install with: pip install kafka-python")
        logger.info("Falling back to simulated mode.")
        return False

    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(','),
        group_id=KAFKA_GROUP_ID,
        auto_offset_reset=KAFKA_AUTO_OFFSET_RESET,
        enable_auto_commit=True,
        value_deserializer=lambda m: m,
        consumer_timeout_ms=1000,
    )

    logger.info(
        "Kafka consumer started. Bootstrap: %s, Topic: %s, Group: %s",
        KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC, KAFKA_GROUP_ID
    )

    msg_count = 0
    error_count = 0

    for message in consumer:
        msg_count += 1
        decision = _process_message(message.value)
        if decision:
            _insert_decision(decision)
        else:
            error_count += 1

        if msg_count % 100 == 0:
            logger.info(
                "Processed %d messages, errors: %d",
                msg_count, error_count
            )

    consumer.close()
    return True


def _run_simulated(max_events: int = 1000, interval_sec: float = 0.5):
    """
    Run in simulated mode when Kafka is not available.
    Reads from a JSONL file as a proxy for Kafka messages.
    """
    # Try to read from the realtime queue file
    from src.config import get_config
    cfg = get_config()
    queue_path = Path(cfg.queue_path)

    if not queue_path.exists():
        logger.warning(
            "Queue file not found: %s. Creating simulated events.", queue_path
        )
        _create_simulated_events(cfg, max_events)

    logger.info(
        "Running in simulated mode. Reading from: %s", queue_path
    )

    with queue_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    if not lines:
        logger.warning("Queue file is empty. Nothing to process.")
        return

    events_to_process = lines[:max_events]
    remaining = lines[max_events:]

    # Write back remaining
    with queue_path.open("w", encoding="utf-8") as f:
        f.writelines(remaining)

    processed = 0
    for line in events_to_process:
        decision = _process_message(line.encode("utf-8"))
        if decision:
            _insert_decision(decision)
            processed += 1

        if processed % 100 == 0:
            logger.info("Processed %d simulated events", processed)

        time.sleep(interval_sec)

    logger.info("Simulated mode complete. Processed %d events.", processed)


def _create_simulated_events(cfg, max_events: int = 1000):
    """Create simulated loan application events when no data is available."""
    from src.ingest_storage import create_pseudo_realtime_queue
    create_pseudo_realtime_queue(cfg, max_events=max_events)
    logger.info("Created %d simulated events in %s", max_events, cfg.queue_path)


def main():
    """Main entry point."""
    logger.info("="*50)
    logger.info("Loan Decision Kafka Consumer")
    logger.info("Kafka: %s, Topic: %s", KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC)
    logger.info("="*50)

    kafka_available = os.getenv("ENABLE_KAFKA", "false").lower() == "true"

    if kafka_available:
        success = _run_with_kafka()
        if success:
            logger.info("Kafka consumer finished.")
        else:
            logger.info("Kafka consumer encountered an error.")
    else:
        logger.info("Kafka not enabled. Running in simulated mode.")
        _run_simulated(max_events=1000)


if __name__ == "__main__":
    main()
