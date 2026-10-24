from __future__ import annotations

import platform
import threading
import time


class AlertManager:
    def __init__(self, storage, cooldown_seconds: int = 30):
        self.storage = storage
        self.cooldown = cooldown_seconds
        self._last = 0.0
        self._lock = threading.Lock()

    def emit(self, message: str, behavior: str, payload: dict):
        now = time.monotonic()
        with self._lock:
            if now - self._last < self.cooldown:
                return
            self._last = now

        self.storage.insert_alert(
            severity="HIGH",
            status="ANOMALY",
            behavior=behavior,
            message=message,
            payload=payload,
        )

        print(f"\n[ALERT] {message} [{behavior}]")

        if platform.system().lower() == "windows":
            try:
                import winsound
                winsound.Beep(1200, 250)
            except Exception:
                pass
