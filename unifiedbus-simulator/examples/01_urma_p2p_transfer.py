"""
Example 01: Peer-to-Peer RDMA Memory Transfer via URMA (liburma)
Simulates Kunpeng CPU (Node 1) transferring data directly to/from Ascend NPU (Node 3).
"""

import sys
import os
import argparse
import time

# Ensure guest_sdk is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "guest_sdk", "python")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unifiedbus.urma import URMAContext


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", default="/tmp/ub-fabric/fabric.sock")
    args = parser.parse_args()

    print("=" * 70)
    print(" [Example 01] UnifiedBus URMA Peer-to-Peer RDMA Memory Transfer")
    print("=" * 70)

    # 1. Initialize Kunpeng CPU (Node 1) and Ascend NPU (Node 3)
    print("[1] Initializing URMA Contexts...")
    kunpeng = URMAContext(node_id=1, socket_path=args.socket)
    ascend = URMAContext(node_id=3, socket_path=args.socket)
    print("    Node 1 (Kunpeng CPU) & Node 3 (Ascend NPU) connected to UB Fabric.")

    # 2. Register memory segments
    print("[2] Registering Memory Segments...")
    token = 0xCAFE0001
    seg_size = 64 * 1024  # 64 KB
    kunpeng_seg = kunpeng.register_segment(seg_size, token_id=token, permissions="RW")
    ascend_seg = ascend.register_segment(seg_size, token_id=token, permissions="RW")
    print(f"    Kunpeng Segment ID: {kunpeng_seg.segment_id} ({seg_size} bytes)")
    print(f"    Ascend Segment ID:  {ascend_seg.segment_id} ({seg_size} bytes)")

    # 3. Create communication Jetty
    print("[3] Establishing URMA Jetty connection...")
    jetty = kunpeng.create_jetty(remote_node=3, remote_jetty_id=1, token_id=token)

    # 4. Fill Kunpeng buffer with test pattern
    test_pattern = b"UnifiedBus High-Performance AI Interconnect (Kunpeng <-> Ascend) " * 32
    kunpeng_seg.buffer[0:len(test_pattern)] = test_pattern

    # 5. Perform RDMA Write from Kunpeng -> Ascend
    print("[4] Executing URMA RDMA Write (Kunpeng -> Ascend NPU)...")
    lat_ns = jetty.write(
        local_seg=kunpeng_seg,
        local_offset=0,
        remote_seg_id=ascend_seg.segment_id,
        remote_offset=0,
        length=len(test_pattern)
    )
    print(f"    RDMA Write OK! Simulated Fabric Latency: {lat_ns:.2f} ns")

    # 6. Perform RDMA Read from Ascend -> Kunpeng
    print("[5] Executing URMA RDMA Read back to Kunpeng...")
    read_buf_seg = kunpeng.register_segment(seg_size, token_id=token, permissions="RW")
    read_lat_ns = jetty.read(
        local_seg=read_buf_seg,
        local_offset=0,
        remote_seg_id=ascend_seg.segment_id,
        remote_offset=0,
        length=len(test_pattern)
    )
    read_data = bytes(read_buf_seg.buffer[0:len(test_pattern)])
    print(f"    RDMA Read OK! Simulated Fabric Latency: {read_lat_ns:.2f} ns")

    # 7. Validate Data Integrity
    assert read_data == test_pattern, "Data mismatch in RDMA transfer!"
    print(f"[6] Data Verification PASSED! Transferred {len(test_pattern)} bytes matching perfectly.")
    print("=" * 70)

    kunpeng.close()
    ascend.close()


if __name__ == "__main__":
    main()
