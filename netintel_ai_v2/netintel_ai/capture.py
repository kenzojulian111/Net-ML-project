from __future__ import annotations

import platform
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from collections import deque
from typing import Deque, Iterable

import psutil
from scapy.all import sniff, IP, TCP, UDP, ICMP
from scapy.config import conf

try:
    conf.use_pcap = True
except Exception:
    pass


@dataclass(slots=True)
class PacketMeta:
    timestamp: float
    src: str
    dst: str
    protocol: str
    src_port: int | None
    dst_port: int | None
    length: int
    tcp_syn: int
    tcp_rst: int
    tcp_fin: int


class PacketBuffer:
    def __init__(self, maxlen: int = 250_000):
        self._data: Deque[PacketMeta] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def append(self, item: PacketMeta) -> None:
        with self._lock:
            self._data.append(item)

    def snapshot_since(self, start_ts: float) -> list[PacketMeta]:
        with self._lock:
            return [x for x in self._data if x.timestamp >= start_ts]

    def snapshot_between(self, start_ts: float, end_ts: float) -> list[PacketMeta]:
        with self._lock:
            return [
                x for x in self._data
                if start_ts <= x.timestamp < end_ts
            ]


def packet_to_meta(packet) -> PacketMeta | None:
    if not packet.haslayer(IP):
        return None

    ip = packet[IP]
    protocol = "OTHER"
    src_port = None
    dst_port = None
    syn = rst = fin = 0

    if packet.haslayer(TCP):
        protocol = "TCP"
        tcp = packet[TCP]
        src_port = int(tcp.sport)
        dst_port = int(tcp.dport)
        flags = int(tcp.flags)
        syn = 1 if flags & 0x02 else 0
        rst = 1 if flags & 0x04 else 0
        fin = 1 if flags & 0x01 else 0
    elif packet.haslayer(UDP):
        protocol = "UDP"
        udp = packet[UDP]
        src_port = int(udp.sport)
        dst_port = int(udp.dport)
    elif packet.haslayer(ICMP):
        protocol = "ICMP"

    return PacketMeta(
        timestamp=float(getattr(packet, "time", datetime.now(timezone.utc).timestamp())),
        src=ip.src,
        dst=ip.dst,
        protocol=protocol,
        src_port=src_port,
        dst_port=dst_port,
        length=len(packet),
        tcp_syn=syn,
        tcp_rst=rst,
        tcp_fin=fin,
    )


def list_interfaces() -> list[tuple[str, str, list[str]]]:
    addresses = psutil.net_if_addrs()
    result = []
    for name in addresses:
        ips = []
        for addr in addresses[name]:
            if getattr(addr, "address", None):
                ips.append(addr.address)
        result.append((name, name, ips))
    return result


def capture(interface: str, seconds: int, buffer: PacketBuffer) -> None:
    def handler(packet) -> None:
        meta = packet_to_meta(packet)
        if meta is not None:
            buffer.append(meta)

    sniff(
        iface=interface,
        prn=handler,
        store=False,
        timeout=seconds,
    )


def interface_counters(interface: str):
    return psutil.net_io_counters(pernic=True).get(interface)
