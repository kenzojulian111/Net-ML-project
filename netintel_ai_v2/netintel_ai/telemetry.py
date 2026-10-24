from __future__ import annotations

import platform
import re
import subprocess
import threading
import time
from datetime import datetime, timezone

import psutil

from .config import Settings


def ping(host: str, timeout_ms: int) -> float | None:
    if platform.system().lower() == "windows":
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), host]
    else:
        cmd = ["ping", "-c", "1", "-W", str(max(1, timeout_ms // 1000)), host]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    except (subprocess.SubprocessError, OSError):
        return None

    match = re.search(r"time[=<]\s*(\d+(?:\.\d+)?)\s*ms", result.stdout, re.I)
    return float(match.group(1)) if match else None


def collect_latency(settings: Settings, stop_event: threading.Event, sink) -> None:
    while not stop_event.is_set():
        ts = datetime.now(timezone.utc)
        for name, host in settings.target_servers.items():
            value = ping(host, settings.ping_timeout_ms)
            sink({
                "timestamp": ts.isoformat(),
                "server": name,
                "host": host,
                "latency_ms": value,
            })
        stop_event.wait(settings.ping_interval)


def sample_interface_rate(interface: str, stop_event: threading.Event, interval: float, sink) -> None:
    previous = psutil.net_io_counters(pernic=True).get(interface)
    previous_time = time.monotonic()

    while not stop_event.is_set():
        stop_event.wait(interval)
        current = psutil.net_io_counters(pernic=True).get(interface)
        now = time.monotonic()

        if previous is None or current is None:
            previous = current
            previous_time = now
            continue

        elapsed = max(now - previous_time, 1e-6)
        tx = max(current.bytes_sent - previous.bytes_sent, 0)
        rx = max(current.bytes_recv - previous.bytes_recv, 0)

        sink({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "upload_mbps": tx * 8 / elapsed / 1_000_000,
            "download_mbps": rx * 8 / elapsed / 1_000_000,
            "bytes_sent": current.bytes_sent,
            "bytes_recv": current.bytes_recv,
        })

        previous = current
        previous_time = now
