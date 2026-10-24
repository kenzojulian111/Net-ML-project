from __future__ import annotations

import pandas as pd


def classify_behavior(row: pd.Series) -> str:
    pps = float(row.get("pps", 0))
    bytes_per_sec = float(row.get("bytes_per_sec", 0))
    syn = float(row.get("tcp_syn", 0))
    dst_ports = float(row.get("unique_dst_ports", 0))
    max_ports = float(row.get("max_unique_dst_ports_per_src", 0))
    rst = float(row.get("tcp_rst", 0))

    if pps > 50_000 or bytes_per_sec > 50_000_000:
        return "volumetric"

    if max_ports >= 50 or dst_ports >= 100:
        return "scanning"

    if syn > 2_000 and rst > 500:
        return "syn_flood_like"

    if syn > 1_000:
        return "connection_burst"

    return "other"
