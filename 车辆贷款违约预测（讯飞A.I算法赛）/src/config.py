from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectConfig:
    base_dir: Path
    train_csv: Path
    test_csv: Path
    data_lake_dir: Path
    sqlite_path: Path
    queue_path: Path
    artifacts_dir: Path
    monitoring_dir: Path

    @property
    def raw_dir(self) -> Path:
        return self.data_lake_dir / "raw"

    @property
    def cleaned_dir(self) -> Path:
        return self.data_lake_dir / "cleaned"

    @property
    def featured_dir(self) -> Path:
        return self.data_lake_dir / "featured"

    @property
    def model_dir(self) -> Path:
        return self.data_lake_dir / "model"


def get_config(base_dir: Path | None = None) -> ProjectConfig:
    root = (base_dir or Path.cwd()).resolve()
    return ProjectConfig(
        base_dir=root,
        train_csv=root / "car_loan_train.csv",
        test_csv=root / "test.csv",
        data_lake_dir=root / "data_lake",
        sqlite_path=root / "data_lake" / "loan_system.db",
        queue_path=root / "data_lake" / "raw" / "realtime_queue.jsonl",
        artifacts_dir=root / "artifacts",
        monitoring_dir=root / "monitoring",
    )

