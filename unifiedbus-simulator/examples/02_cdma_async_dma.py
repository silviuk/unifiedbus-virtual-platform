"""
Example 02: High-Throughput Asynchronous DMA with CDMA (libcdma)
Simulates batch descriptor submission and non-blocking completion wait.
"""

import sys
import os
import argparse
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "guest_sdk", "python")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unifiedbus.cdma import CDMAEngine
from unifiedbus.urma import URMAContext


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", default="/tmp/ub-fabric/fabric.sock")
    args = parser.parse_args()

    print("=" * 70)
    print(" [Example 02] UnifiedBus CDMA Asynchronous Direct Memory Access")
    print("=" * 70)

    # 1. Target Node 4 (Ascend NPU) prepares target memory segment
    target_node = URMAContext(node_id=4, socket_path=args.socket)
    target_seg = target_node.register_segment(1024 * 1024, token_id=0x5555, permissions="RW")

    # 2. Host Node 1 initializes CDMA Engine
    host_cdma = CDMAEngine(node_id=1, socket_path=args.socket)

    # 3. Submit multiple asynchronous DMA write tasks in parallel
    print("[1] Submitting batch of asynchronous CDMA DMA writes...")
    tasks = []
    chunk_size = 32 * 1024  # 32 KB
    num_chunks = 8

    for i in range(num_chunks):
        payload = f"CDMA_BATCH_CHUNK_{i:02d}_".encode('utf-8') * (chunk_size // 20)
        offset = i * chunk_size
        task = host_cdma.submit_dma_write(
            dst_node=4,
            dst_seg_id=target_seg.segment_id,
            dst_offset=offset,
            data=payload,
            token_id=0x5555
        )
        tasks.append(task)

    print(f"    Submitted {num_chunks} DMA tasks ({num_chunks * chunk_size / 1024} KB total).")

    # 4. Wait for all tasks to complete
    print("[2] Awaiting asynchronous DMA completions...")
    for idx, t in enumerate(tasks):
        success = t.wait(timeout=5.0)
        assert success, f"Task {idx} timed out!"
        print(f"    Task {idx:02d} completed | Simulated Transfer Latency: {t.elapsed_sim_latency_ns:.2f} ns")

    print("[3] All CDMA batch tasks successfully processed!")
    print("=" * 70)

    host_cdma.close()
    target_node.close()


if __name__ == "__main__":
    main()
