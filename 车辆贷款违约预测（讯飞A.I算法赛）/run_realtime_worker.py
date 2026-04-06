from src.config import get_config
from src.realtime_api import run_micro_batch_worker


def main() -> None:
    cfg = get_config()
    result = run_micro_batch_worker(cfg, iterations=5, batch_size=200, interval_sec=0.5)
    print("Realtime worker completed.")
    print(result)


if __name__ == "__main__":
    main()

