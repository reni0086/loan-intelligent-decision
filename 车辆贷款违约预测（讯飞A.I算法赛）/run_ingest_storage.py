from src.config import get_config
from src.ingest_storage import (
    batch_ingest_files,
    build_feature_snapshot,
    consume_queue_once,
    create_pseudo_realtime_queue,
    ensure_directories,
    generate_storage_report,
    initialize_sqlite_schema,
    load_structured_tables,
    preprocess_clean_data,
)


def main() -> None:
    cfg = get_config()
    ensure_directories(cfg)
    copied = batch_ingest_files(cfg)
    cleaned_path = preprocess_clean_data(cfg)
    featured_path = build_feature_snapshot(cfg, cleaned_path)
    initialize_sqlite_schema(cfg)
    load_structured_tables(cfg, cleaned_path)
    queue_path = create_pseudo_realtime_queue(cfg, max_events=2000)
    consumed = consume_queue_once(cfg, batch_size=500)
    report_path = generate_storage_report(
        cfg,
        extra={
            "copied_files": copied,
            "cleaned_path": str(cleaned_path),
            "featured_path": str(featured_path),
            "queue_path": str(queue_path),
            "consumed_once": consumed,
        },
    )

    print("Ingest & storage pipeline completed.")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()

