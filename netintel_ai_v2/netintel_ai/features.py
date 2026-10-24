from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Iterable

import numpy as np
import pandas as pd

from .capture import PacketMeta


def entropy(values: Iterable) -> float:
    values = list(values)
    if not values:
        return 0.0
    counts = Counter(values)
    total = len(values)
    return float(-sum((n / total) * math.log2(n / total) for n in counts.values()))


def build_window_features(
    packets: list[PacketMeta],
    start_ts: float,
    end_ts: float,
    bandwidth: dict | None = None,
) -> dict:
    duration = max(end_ts - start_ts, 1e-6)

    if not packets:
        return {
            "window_start": start_ts,
            "window_end": end_ts,
            "packets": 0,
            "bytes": 0,
            "pps": 0.0,
            "bytes_per_sec": 0.0,
            "unique_src_ips": 0,
            "unique_dst_ips": 0,
            "unique_dst_ports": 0,
            "max_unique_dst_ports_per_src": 0,
            "unique_flows": 0,
            "tcp_packets": 0,
            "udp_packets": 0,
            "icmp_packets": 0,
            "tcp_syn": 0,
            "tcp_rst": 0,
            "tcp_fin": 0,
            "src_ip_entropy": 0.0,
            "dst_ip_entropy": 0.0,
            "dst_port_entropy": 0.0,
            "src_port_entropy": 0.0,
            "bandwidth_download_mbps": float((bandwidth or {}).get("download_mbps", 0.0)),
            "bandwidth_upload_mbps": float((bandwidth or {}).get("upload_mbps", 0.0)),
        }

    src_ips = [p.src for p in packets]
    dst_ips = [p.dst for p in packets]
    dst_ports = [p.dst_port for p in packets if p.dst_port is not None]
    src_ports = [p.src_port for p in packets if p.src_port is not None]

    flows = {
        (p.src, p.dst, p.protocol, p.src_port, p.dst_port)
        for p in packets
    }

    ports_per_src = defaultdict(set)
    for p in packets:
        if p.dst_port is not None:
            ports_per_src[p.src].add(p.dst_port)

    return {
        "window_start": start_ts,
        "window_end": end_ts,
        "packets": len(packets),
        "bytes": sum(p.length for p in packets),
        "pps": len(packets) / duration,
        "bytes_per_sec": sum(p.length for p in packets) / duration,
        "unique_src_ips": len(set(src_ips)),
        "unique_dst_ips": len(set(dst_ips)),
        "unique_dst_ports": len(set(dst_ports)),
        "max_unique_dst_ports_per_src": max((len(v) for v in ports_per_src.values()), default=0),
        "unique_flows": len(flows),
        "tcp_packets": sum(p.protocol == "TCP" for p in packets),
        "udp_packets": sum(p.protocol == "UDP" for p in packets),
        "icmp_packets": sum(p.protocol == "ICMP" for p in packets),
        "tcp_syn": sum(p.tcp_syn for p in packets),
        "tcp_rst": sum(p.tcp_rst for p in packets),
        "tcp_fin": sum(p.tcp_fin for p in packets),
        "src_ip_entropy": entropy(src_ips),
        "dst_ip_entropy": entropy(dst_ips),
        "dst_port_entropy": entropy(dst_ports),
        "src_port_entropy": entropy(src_ports),
        "bandwidth_download_mbps": float((bandwidth or {}).get("download_mbps", 0.0)),
        "bandwidth_upload_mbps": float((bandwidth or {}).get("upload_mbps", 0.0)),
    }


FEATURE_COLUMNS = [
    "packets",
    "bytes",
    "pps",
    "bytes_per_sec",
    "unique_src_ips",
    "unique_dst_ips",
    "unique_dst_ports",
    "max_unique_dst_ports_per_src",
    "unique_flows",
    "tcp_packets",
    "udp_packets",
    "icmp_packets",
    "tcp_syn",
    "tcp_rst",
    "tcp_fin",
    "src_ip_entropy",
    "dst_ip_entropy",
    "dst_port_entropy",
    "src_port_entropy",
    "bandwidth_download_mbps",
    "bandwidth_upload_mbps",
]


def frame(features: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(features)
