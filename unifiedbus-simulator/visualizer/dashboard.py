"""
UnifiedBus Interactive Web Visualizer & Telemetry Dashboard Server
"""

import http.server
import socketserver
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "guest_sdk", "python")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unifiedbus.device import UBDevice
from daemon.port import UBPacket, OP_QUERY_TOPOLOGY, OP_QUERY_STATS, OP_RESP_OK

PORT = 8088
SOCKET_PATH = "/tmp/ub-fabric/fabric.sock"
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_GET(self):
        if self.path == "/api/topology":
            self._handle_api_topology()
        elif self.path == "/api/stats":
            self._handle_api_stats()
        else:
            super().do_GET()

    def _handle_api_topology(self):
        try:
            dev = UBDevice(node_id=0xFFFD, node_type="DASHBOARD_COLLECTOR", socket_path=SOCKET_PATH)
            pkt = UBPacket(opcode=OP_QUERY_TOPOLOGY, src_node=0xFFFD, dst_node=0, seq_num=dev._get_seq())
            resp = dev.send_sync(pkt, timeout=2.0)
            dev.close()
            data = resp.metadata if resp else {"nodes": [], "memory_pools": []}
        except Exception as e:
            data = {"error": str(e), "nodes": [], "memory_pools": []}

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _handle_api_stats(self):
        try:
            dev = UBDevice(node_id=0xFFFD, node_type="DASHBOARD_COLLECTOR", socket_path=SOCKET_PATH)
            pkt = UBPacket(opcode=OP_QUERY_STATS, src_node=0xFFFD, dst_node=0, seq_num=dev._get_seq())
            resp = dev.send_sync(pkt, timeout=2.0)
            dev.close()
            data = resp.metadata if resp else {}
        except Exception as e:
            data = {"error": str(e)}

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))


def main():
    import argparse
    parser = argparse.ArgumentParser(description="UnifiedBus Real-Time Visualizer Dashboard")
    parser.add_argument("--port", type=int, default=PORT, help=f"HTTP server port (default: {PORT})")
    parser.add_argument("--socket", default=SOCKET_PATH, help="UB Fabric socket path")
    args = parser.parse_args()

    global SOCKET_PATH
    SOCKET_PATH = args.socket

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", args.port), DashboardHandler) as httpd:
        print("=" * 70)
        print(f" [UnifiedBus Dashboard] Web Visualizer active at http://localhost:{args.port}")
        print(f" Connecting to UB Fabric at {SOCKET_PATH}")
        print("=" * 70)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nDashboard stopped.")


if __name__ == "__main__":
    main()
