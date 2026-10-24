from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import streamlit as st

from netintel_ai.storage import Storage


DB_PATH = Path("data/network.db")

st.set_page_config(
    page_title="NetIntel AI",
    layout="wide",
)

st.title("NetIntel AI")
st.caption("Network telemetry, flow behavior, and ML anomaly detection")

storage = Storage(DB_PATH)

windows = storage.query("""
    SELECT
        id,
        window_start,
        window_end,
        packets,
        pps,
        bandwidth_download_mbps,
        bandwidth_upload_mbps,
        unique_dst_ports,
        ensemble_score,
        ensemble_votes,
        status,
        behavior
    FROM windows
    ORDER BY id DESC
    LIMIT 200
""")

latency = storage.query("""
    SELECT timestamp, server, latency_ms
    FROM latency
    ORDER BY id DESC
    LIMIT 300
""")

bandwidth = storage.query("""
    SELECT timestamp, upload_mbps, download_mbps
    FROM bandwidth
    ORDER BY id DESC
    LIMIT 300
""")

alerts = storage.query("""
    SELECT timestamp, severity, behavior, message
    FROM alerts
    ORDER BY id DESC
    LIMIT 50
""")


if windows.empty:
    st.info("Belum ada data. Jalankan main.py terlebih dahulu.")
    st.stop()


latest = windows.iloc[0]

c1, c2, c3, c4 = st.columns(4)

c1.metric("Status", str(latest["status"]))
c2.metric("Packets", int(latest["packets"]))
c3.metric("Download", f"{latest['bandwidth_download_mbps']:.2f} Mbps")
c4.metric("Anomaly Votes", int(latest["ensemble_votes"]))


st.subheader("Network Windows")

st.line_chart(
    windows.sort_values("id").set_index("id")[
        [
            "pps",
            "bandwidth_download_mbps",
            "bandwidth_upload_mbps",
        ]
    ]
)

st.subheader("Latency")

if not latency.empty:
    latency["timestamp"] = pd.to_datetime(latency["timestamp"])
    latency = latency.sort_values("timestamp")
    pivot = latency.pivot(
        index="timestamp",
        columns="server",
        values="latency_ms",
    )
    st.line_chart(pivot)
else:
    st.info("Belum ada latency data.")


st.subheader("Anomalies")

anomalies = windows[
    windows["status"] == "ANOMALY"
].copy()

if anomalies.empty:
    st.success("Tidak ada anomaly terdeteksi pada window yang tersimpan.")
else:
    st.dataframe(
        anomalies[
            [
                "window_start",
                "packets",
                "pps",
                "bandwidth_download_mbps",
                "unique_dst_ports",
                "ensemble_score",
                "ensemble_votes",
                "behavior",
            ]
        ],
        use_container_width=True,
    )


st.subheader("Alerts")

if alerts.empty:
    st.info("Belum ada alert.")
else:
    st.dataframe(
        alerts,
        use_container_width=True,
    )

st.caption(
    "Refresh halaman untuk mengambil data terbaru."
)
