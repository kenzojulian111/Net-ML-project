from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class Settings:
    interface: str | None = None
    window_seconds: int = 10
    baseline_windows: int = 12
    monitor_windows: int = 36
    packet_flush_seconds: int = 1
    ping_interval: int = 5
    ping_timeout_ms: int = 1000
    model_contamination: float = 0.05
    db_path: Path = Path("data/network.db")
    export_dir: Path = Path("exports")
    alert_cooldown_seconds: int = 30
    target_servers: dict[str, str] = field(default_factory=lambda: {
        "Cloudflare": "1.1.1.1",
        "Google DNS": "8.8.8.8",
        "Quad9": "9.9.9.9",
    })

    def prepare(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)
