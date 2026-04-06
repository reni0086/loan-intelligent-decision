#!/usr/bin/env python3
"""Kafka Producer — CSV records → Kafka topics (loan system streaming pipeline).

Supports two modes:
  --mode batch  : Read a CSV file and push all records to Kafka (bulk simulation)
  --mode http    : Start an HTTP server; external systems POST loan applications
                  and this script forwards them to the Kafka lending_application topic
  --mode stream  : Monitor a directory for new CSV files and stream them continuously

Usage:
  # Push test.csv records to Kafka (batch, 10k records):
  python kafka_producer.py --mode batch --csv test.csv --limit 10000

  # Push entire training set with snappy compression:
  python kafka_producer.py --mode batch --csv car_loan_train.csv --compression snappy

  # Start HTTP server for external system integration:
  python kafka_producer.py --mode http --port 8080

  # Stream new CSV files dropped into a directory:
  python kafka_producer.py --mode stream --watch-dir /data/flume/spool

Environment variables:
  KAFKA_BROKERS   Bootstrap servers (default: localhost:9092)
  KAFKA_TOPIC     Target topic  (default: lending_application)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import zlib
from pathlib import Path
from typing import Any, Iterator, Optional
from queue import Queue
import threading
from datetime import datetime

import pandas as pd
from kafka import KafkaProducer
from kafka.errors import KafkaError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("kafka_producer")

# Defaults
KAFKA_BROKERS: str = os.getenv("KAFKA_BROKERS", "localhost:9092")
DEFAULT_TOPIC: str = os.getenv("KAFKA_TOPIC", "lending_application")


# =============================================================================
#  Kafka Producer Helper
# =============================================================================

def _make_producer(
    bootstrap_servers: str,
    compression: str | None = None,
    acks: int = 1,
    batch_size: int = 16384,
    linger_ms: int = 10,
) -> KafkaProducer:
    kwargs: dict[str, Any] = {
        "bootstrap_servers": bootstrap_servers,
        "value_serializer": lambda v: json.dumps(v, default=str).encode("utf-8"),
        "key_serializer": lambda k: str(k).encode("utf-8") if k is not None else None,
        "acks": acks,
        "batch_size": batch_size,
        "linger_ms": linger_ms,
        "retries": 3,
        "max_block_ms": 30000,
    }
    if compression:
        kwargs["compression_type"] = compression

    return KafkaProducer(**kwargs)


def _row_to_kafka_event(row: pd.Series, topic: str) -> dict[str, Any]:
    """Convert a CSV row to a Kafka event payload.

    Drops the loan_default label column (not available at application time) and
    enriches with metadata fields used by downstream consumers.
    """
    payload = row.drop(labels=["loan_default"], errors="ignore").to_dict()
    payload["_topic"] = topic
    payload["_produced_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    payload["_source"] = "csv_producer"
    return payload


def _read_csv_batches(
    csv_path: str,
    batch_size: int = 500,
    limit: int | None = None,
) -> Iterator[pd.DataFrame]:
    """Yield DataFrame chunks from a large CSV file to avoid OOM."""
    chunk_iter = pd.read_csv(csv_path, chunksize=batch_size)
    count = 0
    for chunk in chunk_iter:
        yield chunk
        count += len(chunk)
        if limit and count >= limit:
            break


# =============================================================================
#  Batch Mode — CSV → Kafka
# =============================================================================

def run_batch_mode(
    csv_path: str,
    topic: str,
    bootstrap_servers: str,
    compression: str | None,
    limit: int | None,
    report_every: int = 5000,
) -> None:
    """Read CSV file in batches and publish each row as a Kafka message."""
    producer = _make_producer(bootstrap_servers, compression=compression)
    total_sent = 0
    t0 = time.time()

    logger.info("[BATCH] CSV: %s  →  Kafka topic: %s  brokers: %s", csv_path, topic, bootstrap_servers)

    for batch in _read_csv_batches(csv_path, batch_size=500, limit=limit):
        for _, row in batch.iterrows():
            event = _row_to_kafka_event(row, topic)
            try:
                future = producer.send(
                    topic,
                    key=int(row["customer_id"]),
                    value=event,
                )
                future.add_callback(lambda _r: None)   # suppress success callback noise
                total_sent += 1
                if total_sent % report_every == 0:
                    elapsed = time.time() - t0
                    rate = total_sent / elapsed
                    logger.info(
                        "[BATCH] sent %d records (%.1f rec/s, %.1fs elapsed)",
                        total_sent, rate, elapsed,
                    )
            except KafkaError as e:
                logger.error("[BATCH] Kafka error on customer_id=%s: %s", row.get("customer_id"), e)

    producer.flush()
    producer.close()
    elapsed = time.time() - t0
    logger.info(
        "[BATCH] DONE — %d records sent to %s in %.1fs (%.1f rec/s)",
        total_sent, topic, elapsed, total_sent / elapsed,
    )


# =============================================================================
#  HTTP Mode — HTTP Server → Kafka
# =============================================================================

async def _handle_request(request: Any, producer: KafkaProducer, topic: str) -> dict[str, Any]:
    """Handle a single POST /apply JSON request."""
    try:
        body = await request.json()
    except Exception as e:
        return {"status": "error", "message": f"Invalid JSON: {e}"}

    # Validate required fields
    required = ["customer_id", "disbursed_amount", "credit_score"]
    missing = [f for f in required if f not in body]
    if missing:
        return {"status": "error", "message": f"Missing fields: {missing}"}

    body["_topic"] = topic
    body["_produced_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    body["_source"] = "http_api"

    try:
        future = producer.send(topic, key=int(body["customer_id"]), value=body)
        record_metadata = future.get(timeout=10)
        return {
            "status": "ok",
            "customer_id": body["customer_id"],
            "topic": record_metadata.topic,
            "partition": record_metadata.partition,
            "offset": record_metadata.offset,
        }
    except KafkaError as e:
        return {"status": "error", "message": str(e)}


def _start_http_mode(port: int, bootstrap_servers: str, topic: str) -> None:
    """Start a simple aiohttp HTTP server that forwards POSTed records to Kafka.

    POST http://localhost:{port}/apply
    Content-Type: application/json
    Body: {"customer_id": 100001, "disbursed_amount": 35000, "credit_score": 720, ...}
    """
    try:
        import aiohttp
    except ImportError:
        logger.error("aiohttp not installed. Run: pip install aiohttp")
        sys.exit(1)

    producer = _make_producer(bootstrap_servers, acks=1, linger_ms=0)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = aiohttp.web.Application()

    async def apply_handler(request: aiohttp.web_request.Request) -> aiohttp.web_response.Response:
        result = await _handle_request(request, producer, topic)
        status = 200 if result.get("status") == "ok" else 400
        return aiohttp.web.json_response(result, status=status)

    async def health_handler(_: aiohttp.web_request.Request) -> aiohttp.web_response.Response:
        return aiohttp.web.json_response({"status": "producer_ok", "brokers": bootstrap_servers})

    app.router.add_post("/apply", apply_handler)
    app.router.add_get("/health", health_handler)

    logger.info(
        "[HTTP] Kafka producer listening on http://0.0.0.0:%d/apply  →  topic: %s",
        port, topic,
    )
    aiohttp.web.run_app(app, host="0.0.0.0", port=port, loop=loop, print=None)


# =============================================================================
#  Stream Mode — Watch directory for new CSV files → Kafka
# =============================================================================

def _watch_directory(
    watch_dir: str,
    topic: str,
    bootstrap_servers: str,
    compression: str | None,
    poll_interval: int = 5,
) -> None:
    """Monitor a directory; any new CSV file is streamed to Kafka on detection."""
    producer = _make_producer(bootstrap_servers, compression=compression)
    seen: set[str] = set()
    logger.info("[STREAM] Watching %s for new CSV files...", watch_dir)

    while True:
        try:
            csv_files = sorted(Path(watch_dir).glob("*.csv"))
            for fpath in csv_files:
                if str(fpath) in seen:
                    continue
                seen.add(str(fpath))
                logger.info("[STREAM] New file detected: %s", fpath.name)
                t0 = time.time()
                count = 0
                for batch in _read_csv_batches(str(fpath), batch_size=500):
                    for _, row in batch.iterrows():
                        event = _row_to_kafka_event(row, topic)
                        producer.send(topic, key=int(row["customer_id"]), value=event)
                        count += 1
                    producer.flush()
                elapsed = time.time() - t0
                logger.info(
                    "[STREAM] %s done: %d records → %s in %.1fs (%.1f rec/s)",
                    fpath.name, count, topic, elapsed, count / elapsed,
                )
        except Exception as e:
            logger.error("[STREAM] Error scanning directory: %s", e)

        time.sleep(poll_interval)


# =============================================================================
#  CLI entry point
# =============================================================================

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Kafka Producer: CSV / HTTP / Directory → Kafka lending_application topic",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--mode",
        choices=["batch", "http", "stream"],
        default="batch",
        help="batch: push CSV file records to Kafka  |  http: HTTP REST server  |  stream: watch directory",
    )
    p.add_argument("--csv", default="test.csv", help="CSV file path (batch mode)")
    p.add_argument("--limit", type=int, default=None, help="Max number of records to send (batch mode)")
    p.add_argument(
        "--compression",
        choices=["gzip", "snappy", "lz4", "zstd"],
        default=None,
        help="Kafka message compression (default: none, recommend: snappy for high throughput)",
    )
    p.add_argument("--batch-size", type=int, default=16384, help="Kafka producer batch.size")
    p.add_argument("--brokers", default=KAFKA_BROKERS, help="Kafka bootstrap servers")
    p.add_argument("--topic", default=DEFAULT_TOPIC, help="Target Kafka topic")
    p.add_argument("--port", type=int, default=8080, help="HTTP server port (http mode)")
    p.add_argument("--watch-dir", default="/data/flume/spool", help="Directory to watch (stream mode)")
    p.add_argument("--poll-interval", type=int, default=5, help="Directory poll interval in seconds")
    p.add_argument(
        "--report-every", type=int, default=5000,
        help="Log progress every N records (batch mode)",
    )
    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    logger.info("[PRODUCER] mode=%s  brokers=%s  topic=%s", args.mode, args.brokers, args.topic)

    if args.mode == "batch":
        csv_path = Path(args.csv)
        if not csv_path.exists():
            logger.error("CSV file not found: %s", csv_path)
            sys.exit(1)
        run_batch_mode(
            csv_path=str(csv_path),
            topic=args.topic,
            bootstrap_servers=args.brokers,
            compression=args.compression,
            limit=args.limit,
            report_every=args.report_every,
        )

    elif args.mode == "http":
        _start_http_mode(port=args.port, bootstrap_servers=args.brokers, topic=args.topic)

    elif args.mode == "stream":
        watch_dir = Path(args.watch_dir)
        watch_dir.mkdir(parents=True, exist_ok=True)
        _watch_directory(
            watch_dir=str(watch_dir),
            topic=args.topic,
            bootstrap_servers=args.brokers,
            compression=args.compression,
            poll_interval=args.poll_interval,
        )


if __name__ == "__main__":
    main()
