"""Base collector class for data collection."""

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, List, Optional


@dataclass
class CollectorResult:
    """Result from a collector execution."""

    collector_name: str
    source: str
    success: bool
    data: List[dict] = field(default_factory=list)
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CollectorResult":
        """Create from dictionary."""
        return cls(**data)


class BaseCollector(ABC):
    """Abstract base class for all data collectors."""

    name: str = "base_collector"
    source: str = "unknown"

    def __init__(self, data_dir: str = "./data"):
        """Initialize the collector.

        Args:
            data_dir: Directory to store collected data.
        """
        self.data_dir = data_dir

    @abstractmethod
    def collect(self, **kwargs) -> CollectorResult:
        """Collect data from the source.

        Returns:
            CollectorResult containing the collected data.
        """
        pass

    def save_data(self, result: CollectorResult, subdir: str = "", max_files: int = 3) -> str:
        """Save collected data to disk.

        Args:
            result: The collector result to save.
            subdir: Subdirectory within data_dir.
            max_files: Maximum number of files to keep (default 3 hours).

        Returns:
            Path where data was saved.
        """
        target_dir = os.path.join(self.data_dir, subdir) if subdir else self.data_dir
        os.makedirs(target_dir, exist_ok=True)

        # Use hourly timestamp to avoid duplicates within same hour
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H")
        filename = f"{self.name}_{timestamp}.json"
        filepath = os.path.join(target_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

        # Cleanup old files
        self._cleanup_old_files(target_dir, max_files)

        return filepath

    def _cleanup_old_files(self, target_dir: str, max_files: int = 3) -> None:
        """Remove old files, keeping only the most recent ones.

        Args:
            target_dir: Directory to clean up.
            max_files: Maximum number of files to keep per collector.
        """
        if not os.path.exists(target_dir):
            return

        # Find files for this collector
        files = [f for f in os.listdir(target_dir)
                 if f.startswith(self.name) and f.endswith(".json")]

        if len(files) <= max_files:
            return

        # Sort by filename (which includes timestamp)
        files.sort()

        # Delete oldest files
        files_to_delete = files[:-max_files]
        for filename in files_to_delete:
            filepath = os.path.join(target_dir, filename)
            try:
                os.remove(filepath)
            except Exception:
                pass

    def load_latest(self, subdir: str = "") -> Optional[CollectorResult]:
        """Load the most recent collected data.

        Args:
            subdir: Subdirectory within data_dir.

        Returns:
            The most recent CollectorResult or None.
        """
        target_dir = os.path.join(self.data_dir, subdir) if subdir else self.data_dir
        if not os.path.exists(target_dir):
            return None

        files = [f for f in os.listdir(target_dir)
                 if f.startswith(self.name) and f.endswith(".json")]

        if not files:
            return None

        latest_file = sorted(files)[-1]
        filepath = os.path.join(target_dir, latest_file)

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        return CollectorResult.from_dict(data)

    def load_all_recent(self, subdir: str = "", hours: int = 24) -> List[CollectorResult]:
        """Load all collected data from the past N hours.

        Args:
            subdir: Subdirectory within data_dir.
            hours: Number of hours to look back.

        Returns:
            List of CollectorResults.
        """
        target_dir = os.path.join(self.data_dir, subdir) if subdir else self.data_dir
        if not os.path.exists(target_dir):
            return []

        results = []
        cutoff = datetime.utcnow().timestamp() - (hours * 3600)

        files = [f for f in os.listdir(target_dir)
                 if f.startswith(self.name) and f.endswith(".json")]

        for filename in files:
            filepath = os.path.join(target_dir, filename)
            if os.path.getmtime(filepath) < cutoff:
                continue

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            results.append(CollectorResult.from_dict(data))

        return sorted(results, key=lambda x: x.timestamp, reverse=True)
