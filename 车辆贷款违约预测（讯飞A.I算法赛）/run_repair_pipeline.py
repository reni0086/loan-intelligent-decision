from src.config import get_config
from src.repair import run_repair_pipeline


def main() -> None:
    cfg = get_config()
    repaired_path, report_path = run_repair_pipeline(cfg)
    print("Repair pipeline completed.")
    print(f"Repaired data: {repaired_path}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()

