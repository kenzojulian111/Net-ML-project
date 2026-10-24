from __future__ import annotations

from pathlib import Path
import pandas as pd


def summarize_windows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    return (
        df.groupby("status")
        .agg(
            windows=("status", "count"),
            avg_pps=("pps", "mean"),
            avg_mbps=("bandwidth_download_mbps", "mean"),
            anomalies=("status", lambda x: (x == "ANOMALY").sum()),
        )
        .reset_index()
    )


def rank_destinations(packets) -> pd.DataFrame:
    if not packets:
        return pd.DataFrame(columns=[
            "destination", "bytes", "packets", "traffic_share_pct"
        ])

    rows = {}
    total_bytes = sum(p.length for p in packets)

    for packet in packets:
        current = rows.setdefault(packet.dst, {"bytes": 0, "packets": 0})
        current["bytes"] += packet.length
        current["packets"] += 1

    result = [
        {
            "destination": dst,
            "bytes": values["bytes"],
            "packets": values["packets"],
            "traffic_share_pct": (
                values["bytes"] / total_bytes * 100
                if total_bytes else 0.0
            ),
        }
        for dst, values in rows.items()
    ]

    return (
        pd.DataFrame(result)
        .sort_values("bytes", ascending=False)
        .reset_index(drop=True)
    )
