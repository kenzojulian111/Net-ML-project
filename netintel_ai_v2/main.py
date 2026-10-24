from __future__ import annotations

import argparse
import threading
import time
from pathlib import Path

import pandas as pd

from netintel_ai.alerts import AlertManager
from netintel_ai.capture import PacketBuffer, capture, list_interfaces
from netintel_ai.classification import classify_behavior
from netintel_ai.config import Settings
from netintel_ai.features import build_window_features, frame
from netintel_ai.models import fit_models, score_models, validate_labeled_dataset
from netintel_ai.reporting import rank_destinations
from netintel_ai.storage import Storage
from netintel_ai.telemetry import collect_latency, sample_interface_rate


def choose_interface(preselected: str | None) -> str:
    if preselected:
        return preselected

    interfaces = list_interfaces()

    print("\nNetwork interfaces:\n")
    for i, (_, name, ips) in enumerate(interfaces):
        print(f"[{i}] {name}")
        print(f"    IP: {', '.join(ips) or '-'}")

    choice = int(input("\nPilih interface: "))
    return interfaces[choice][0]


def collect_baseline(
    settings: Settings,
    buffer: PacketBuffer,
    bandwidth_state: dict,
) -> pd.DataFrame:
    start = time.time()
    rows = []
    last = start

    print(f"\nBaseline collection: {settings.baseline_windows} windows")

    for i in range(settings.baseline_windows):
        end = last + settings.window_seconds
        time.sleep(max(0, end - time.time()))

        packets = buffer.snapshot_between(last, end)
        row = build_window_features(
            packets,
            last,
            end,
            bandwidth_state.copy(),
        )

        rows.append(row)
        last = end

        print(
            f"\rBaseline [{i + 1}/{settings.baseline_windows}] "
            f"packets={row['packets']} "
            f"pps={row['pps']:.1f} "
            f"mbps={row['bandwidth_download_mbps']:.2f}",
            end="",
        )

    print()
    return frame(rows)


def monitor(
    settings: Settings,
    buffer: PacketBuffer,
    models,
    storage: Storage,
    alert_manager: AlertManager,
    bandwidth_state: dict,
):
    last = time.time()

    print(f"\nRealtime monitoring: {settings.monitor_windows} windows")

    for i in range(settings.monitor_windows):
        end = last + settings.window_seconds
        time.sleep(max(0, end - time.time()))

        packets = buffer.snapshot_between(last, end)
        row = build_window_features(
            packets,
            last,
            end,
            bandwidth_state.copy(),
        )

        current = frame([row])
        scored = score_models(models, current)
        result = scored.iloc[0].to_dict()
        behavior = classify_behavior(scored.iloc[0])

        result["model"] = ",".join(models.keys())
        result["behavior"] = behavior

        storage.insert_window(result)

        status = result["status"]
        print(
            f"\rMonitor [{i + 1}/{settings.monitor_windows}] "
            f"status={status:<7} "
            f"pps={row['pps']:>9.1f} "
            f"download={row['bandwidth_download_mbps']:>7.2f} Mbps "
            f"dst_ports={row['unique_dst_ports']:>4} "
            f"votes={int(result['ensemble_votes'])}",
            end="",
        )

        if status == "ANOMALY":
            alert_manager.emit(
                message=(
                    f"Network anomaly detected: "
                    f"pps={row['pps']:.1f}, "
                    f"download={row['bandwidth_download_mbps']:.2f} Mbps"
                ),
                behavior=behavior,
                payload=result,
            )

        last = end

    print()


def start_telemetry_threads(settings, storage, interface, bandwidth_state, stop_event):
    def latency_sink(row):
        storage.insert_latency(row)

    def bandwidth_sink(row):
        bandwidth_state.clear()
        bandwidth_state.update(row)
        storage.insert_bandwidth(row)

    threads = [
        threading.Thread(
            target=collect_latency,
            args=(settings, stop_event, latency_sink),
            daemon=True,
        ),
        threading.Thread(
            target=sample_interface_rate,
            args=(interface, stop_event, settings.packet_flush_seconds, bandwidth_sink),
            daemon=True,
        ),
    ]

    for thread in threads:
        thread.start()

    return threads


def validate_from_csv(path: Path, models):
    dataset = pd.read_csv(path)
    result = validate_labeled_dataset(models, dataset)
    print("\nModel validation:")
    print(result.to_string(index=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interface", default=None)
    parser.add_argument("--capture-time", type=int, default=None)
    parser.add_argument("--baseline", type=int, default=12)
    parser.add_argument("--monitor", type=int, default=36)
    parser.add_argument("--window", type=int, default=10)
    parser.add_argument("--db", default="data/network.db")
    parser.add_argument("--validate", default=None)
    args = parser.parse_args()

    settings = Settings(
        interface=args.interface,
        window_seconds=args.window,
        baseline_windows=args.baseline,
        monitor_windows=args.monitor,
        db_path=Path(args.db),
    )

    if args.capture_time:
        settings.monitor_windows = max(
            1,
            args.capture_time // settings.window_seconds
        )

    settings.prepare()

    interface = choose_interface(settings.interface)
    settings.interface = interface

    print(f"\nSelected interface: {interface}")
    print(f"Window: {settings.window_seconds}s")
    print(f"Baseline windows: {settings.baseline_windows}")
    print(f"Monitor windows: {settings.monitor_windows}")

    buffer = PacketBuffer()
    storage = Storage(settings.db_path)
    alert_manager = AlertManager(
        storage,
        settings.alert_cooldown_seconds,
    )

    bandwidth_state = {
        "upload_mbps": 0.0,
        "download_mbps": 0.0,
        "bytes_sent": 0,
        "bytes_recv": 0,
    }

    stop_event = threading.Event()

    telemetry_threads = start_telemetry_threads(
        settings,
        storage,
        interface,
        bandwidth_state,
        stop_event,
    )

    capture_thread = threading.Thread(
        target=capture,
        args=(
            interface,
            (settings.baseline_windows + settings.monitor_windows)
            * settings.window_seconds + 5,
            buffer,
        ),
        daemon=True,
    )

    capture_thread.start()

    try:
        baseline = collect_baseline(
            settings,
            buffer,
            bandwidth_state,
        )

        print("\nTraining models...")
        models = fit_models(
            baseline,
            settings.model_contamination,
        )

        for name in models:
            print(f"Model ready: {name}")

        if args.validate:
            validate_from_csv(
                Path(args.validate),
                models,
            )

        monitor(
            settings,
            buffer,
            models,
            storage,
            alert_manager,
            bandwidth_state,
        )

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        stop_event.set()

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    excel_path = settings.export_dir / f"network_ai_{timestamp}.xlsx"
    storage.export_excel(excel_path)

    print(f"\nDatabase: {settings.db_path}")
    print(f"Excel: {excel_path}")

    destination_df = rank_destinations(
        buffer.snapshot_since(time.time() - (
            settings.window_seconds *
            (settings.baseline_windows + settings.monitor_windows)
        ))
    )

    if not destination_df.empty:
        print("\nTop destinations:")
        print(destination_df.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
