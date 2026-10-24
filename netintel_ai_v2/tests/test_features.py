from netintel_ai.capture import PacketMeta
from netintel_ai.features import build_window_features


def test_empty_window():
    result = build_window_features([], 0, 10)
    assert result["packets"] == 0
    assert result["pps"] == 0


def test_packet_features():
    packets = [
        PacketMeta(
            timestamp=1,
            src="192.168.1.2",
            dst="8.8.8.8",
            protocol="UDP",
            src_port=40000,
            dst_port=53,
            length=100,
            tcp_syn=0,
            tcp_rst=0,
            tcp_fin=0,
        ),
        PacketMeta(
            timestamp=2,
            src="192.168.1.2",
            dst="8.8.4.4",
            protocol="UDP",
            src_port=40001,
            dst_port=53,
            length=200,
            tcp_syn=0,
            tcp_rst=0,
            tcp_fin=0,
        ),
    ]

    result = build_window_features(
        packets,
        0,
        10,
        {"download_mbps": 1.5, "upload_mbps": 0.2},
    )

    assert result["packets"] == 2
    assert result["bytes"] == 300
    assert result["unique_dst_ports"] == 1
    assert result["bandwidth_download_mbps"] == 1.5
