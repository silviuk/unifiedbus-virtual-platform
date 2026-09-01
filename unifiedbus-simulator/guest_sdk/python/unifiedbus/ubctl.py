"""
UnifiedBus Management CLI Tool (ubctl)
Used to query topology, inspect configuration space, manage memory pools, and monitor link statistics.
"""

import argparse
import sys
import time
from .device import UBDevice
from daemon.port import UBPacket, OP_QUERY_TOPOLOGY, OP_QUERY_STATS, OP_RESP_OK


def format_bytes(num_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def cmd_topology(args):
    try:
        dev = UBDevice(node_id=0xFFFE, node_type="MGMT_CONTROLLER", socket_path=args.socket)
    except Exception as e:
        print(f"[Error] Cannot connect to UnifiedBus Fabric: {e}")
        sys.exit(1)

    seq = dev._get_seq()
    pkt = UBPacket(opcode=OP_QUERY_TOPOLOGY, src_node=0xFFFE, dst_node=0, seq_num=seq)
    resp = dev.send_sync(pkt)
    dev.close()

    if not resp or resp.opcode != OP_RESP_OK:
        print("[Error] Failed to retrieve topology information.")
        return

    meta = resp.metadata
    print("=" * 75)
    print(f" UnifiedBus (UB) SuperPoD Topology Viewer - {meta.get('switch', 'UB-Switch')}")
    print(f" Fabric Bandwidth: {meta.get('link_bw_gbps', 800.0)} Gbps | Link Status: ACTIVE")
    print("=" * 75)
    print(f"{'Node ID':<10} {'Type':<18} {'TX Traffic':<14} {'RX Traffic':<14} {'Uptime':<10}")
    print("-" * 75)
    
    nodes = meta.get("nodes", [])
    if not nodes:
        print("  No nodes currently attached to the UB fabric.")
    for n in nodes:
        if n["node_id"] == 0xFFFE:
            continue
        print(f"  0x{n['node_id']:04X}    {n['node_type']:<18} {format_bytes(n['tx_bytes']):<14} {format_bytes(n['rx_bytes']):<14} {n['uptime_sec']}s")
    
    pools = meta.get("memory_pools", [])
    if pools:
        print("\n" + "=" * 75)
        print(" Active UB Memory Pools (OBMM / Disaggregated Memory)")
        print("=" * 75)
        print(f"{'Pool ID':<12} {'Owner':<10} {'Size':<14} {'TokenID':<14} {'Permissions':<10}")
        print("-" * 75)
        for p in pools:
            print(f"  0x{p['pool_id']:04X}      Node {p['owner_node']:<5} {format_bytes(p['size_bytes']):<14} 0x{p['token_id']:08X}     {p['permissions']}")
    print("=" * 75)


def cmd_stats(args):
    try:
        dev = UBDevice(node_id=0xFFFE, node_type="MGMT_CONTROLLER", socket_path=args.socket)
    except Exception as e:
        print(f"[Error] Cannot connect to UnifiedBus Fabric: {e}")
        sys.exit(1)

    seq = dev._get_seq()
    pkt = UBPacket(opcode=OP_QUERY_STATS, src_node=0xFFFE, dst_node=0, seq_num=seq)
    resp = dev.send_sync(pkt)
    dev.close()

    if not resp or resp.opcode != OP_RESP_OK:
        print("[Error] Failed to retrieve fabric statistics.")
        return

    meta = resp.metadata
    print("=" * 70)
    print(" UnifiedBus (UB) Interconnect Telemetry & Performance Counters")
    print("=" * 70)
    print(f" Total Routed Packets:     {meta.get('total_packets', 0):,}")
    print(f" Total Routed Flits (64B): {meta.get('total_flits', 0):,}")
    print(f" Total Fabric Throughput:  {format_bytes(meta.get('total_bytes', 0))}")
    print(f" Active Connected Nodes:   {meta.get('active_nodes', 0)}")
    print("-" * 70)
    print(" Recent Event Log:")
    for ev in meta.get("recent_events", [])[-10:]:
        print(f"  [{time.strftime('%H:%M:%S', time.localtime(ev['time']))}] {ev['type']:<12} Node {ev['src']} -> Node {ev['dst']} | {format_bytes(ev['size'])} ({ev['latency_ns']} ns) | {ev['desc']}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="UnifiedBus (UB) Management CLI (ubctl)")
    parser.add_argument("--socket", default="/tmp/ub-fabric/fabric.sock", help="Fabric socket path")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("topology", help="Display connected UB nodes and topology")
    subparsers.add_parser("stats", help="Display fabric traffic and event telemetry")
    subparsers.add_parser("mem", help="Display memory pooling status").set_defaults(func=cmd_topology)

    args = parser.parse_args()
    if args.command == "topology" or args.command == "mem":
        cmd_topology(args)
    elif args.command == "stats":
        cmd_stats(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
