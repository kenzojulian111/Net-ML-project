from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd


class Storage:
    def __init__(self, path: Path):
        self.path = str(path)
        self._init()

    def _connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def _init(self):
        with self._connect() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS windows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    window_start REAL,
                    window_end REAL,
                    packets INTEGER,
                    bytes INTEGER,
                    pps REAL,
                    bytes_per_sec REAL,
                    unique_src_ips INTEGER,
                    unique_dst_ips INTEGER,
                    unique_dst_ports INTEGER,
                    max_unique_dst_ports_per_src INTEGER,
                    unique_flows INTEGER,
                    tcp_packets INTEGER,
                    udp_packets INTEGER,
                    icmp_packets INTEGER,
                    tcp_syn INTEGER,
                    tcp_rst INTEGER,
                    tcp_fin INTEGER,
                    src_ip_entropy REAL,
                    dst_ip_entropy REAL,
                    dst_port_entropy REAL,
                    src_port_entropy REAL,
                    bandwidth_download_mbps REAL,
                    bandwidth_upload_mbps REAL,
                    model TEXT,
                    ensemble_score REAL,
                    ensemble_votes INTEGER,
                    status TEXT,
                    behavior TEXT
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS latency (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    server TEXT,
                    host TEXT,
                    latency_ms REAL
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS bandwidth (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    upload_mbps REAL,
                    download_mbps REAL,
                    bytes_sent INTEGER,
                    bytes_recv INTEGER
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    severity TEXT,
                    status TEXT,
                    behavior TEXT,
                    message TEXT,
                    payload TEXT
                )
            """)
            con.commit()

    def insert_window(self, row: dict):
        keys = [
            "window_start", "window_end", "packets", "bytes", "pps",
            "bytes_per_sec", "unique_src_ips", "unique_dst_ips",
            "unique_dst_ports", "max_unique_dst_ports_per_src",
            "unique_flows", "tcp_packets", "udp_packets", "icmp_packets",
            "tcp_syn", "tcp_rst", "tcp_fin", "src_ip_entropy",
            "dst_ip_entropy", "dst_port_entropy", "src_port_entropy",
            "bandwidth_download_mbps", "bandwidth_upload_mbps", "model",
            "ensemble_score", "ensemble_votes", "status", "behavior",
        ]
        values = [row.get(k) for k in keys]
        placeholders = ",".join("?" for _ in keys)

        with self._connect() as con:
            con.execute(
                f"INSERT INTO windows ({','.join(keys)}) VALUES ({placeholders})",
                values,
            )
            con.commit()

    def insert_latency(self, row: dict):
        with self._connect() as con:
            con.execute(
                "INSERT INTO latency (timestamp, server, host, latency_ms) VALUES (?, ?, ?, ?)",
                (row["timestamp"], row["server"], row["host"], row["latency_ms"]),
            )
            con.commit()

    def insert_bandwidth(self, row: dict):
        with self._connect() as con:
            con.execute(
                "INSERT INTO bandwidth (timestamp, upload_mbps, download_mbps, bytes_sent, bytes_recv) VALUES (?, ?, ?, ?, ?)",
                (
                    row["timestamp"],
                    row["upload_mbps"],
                    row["download_mbps"],
                    row["bytes_sent"],
                    row["bytes_recv"],
                ),
            )
            con.commit()

    def insert_alert(self, severity: str, status: str, behavior: str, message: str, payload: dict):
        with self._connect() as con:
            con.execute(
                "INSERT INTO alerts (timestamp, severity, status, behavior, message, payload) VALUES (datetime('now'), ?, ?, ?, ?, ?)",
                (severity, status, behavior, message, json.dumps(payload, default=str)),
            )
            con.commit()

    def query(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        with self._connect() as con:
            return pd.read_sql_query(sql, con, params=params)

    def export_excel(self, path: Path):
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            self.query("SELECT * FROM windows ORDER BY id").to_excel(writer, sheet_name="Windows", index=False)
            self.query("SELECT * FROM latency ORDER BY id").to_excel(writer, sheet_name="Latency", index=False)
            self.query("SELECT * FROM bandwidth ORDER BY id").to_excel(writer, sheet_name="Bandwidth", index=False)
            self.query("SELECT * FROM alerts ORDER BY id").to_excel(writer, sheet_name="Alerts", index=False)
