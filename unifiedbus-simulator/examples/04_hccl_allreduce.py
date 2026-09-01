"""
Example 04: Distributed AI Collective Communication (HCCL) over UnifiedBus
Simulates 4 Ascend NPU accelerator ranks executing Ring-AllReduce & AllGather on tensors.
"""

import sys
import os
import argparse
import time
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "guest_sdk", "python")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unifiedbus.hccl import HCCLContext, ReduceOp


def run_rank(rank: int, world_size: int, tensor_size_mb: int, socket_path: str, barrier: threading.Barrier, results: dict):
    # Initialize HCCL context for this rank
    hccl = HCCLContext(rank=rank, world_size=world_size, socket_path=socket_path)
    
    # Wait for all ranks to connect and set up ring
    barrier.wait()
    time.sleep(0.05)

    # Prepare local tensor
    num_elements = (tensor_size_mb * 1024 * 1024) // 4
    local_tensor = [1.0] * num_elements

    # Execute AllReduce
    barrier.wait()
    reduced_tensor, stats = hccl.all_reduce(local_tensor, op=ReduceOp.SUM)

    results[rank] = stats
    barrier.wait()
    hccl.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", default="/tmp/ub-fabric/fabric.sock")
    parser.add_argument("--world-size", type=int, default=4, help="Number of Ascend NPU ranks")
    parser.add_argument("--size-mb", type=int, default=16, help="Tensor size in MB")
    args = parser.parse_args()

    print("=" * 70)
    print(f" [Example 04] UnifiedBus HCCL Collective Communication ({args.world_size} Ascend NPUs)")
    print(f" Tensor Size: {args.size_mb} MB | Interconnect: UB 800 Gbps Low-Latency Ring")
    print("=" * 70)

    barrier = threading.Barrier(args.world_size)
    results = {}
    threads = []

    print("[1] Spawning NPU collective worker ranks...")
    for r in range(args.world_size):
        t = threading.Thread(
            target=run_rank,
            args=(r, args.world_size, args.size_mb, args.socket, barrier, results)
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    print("\n[2] HCCL AllReduce Benchmark Results across Ranks:")
    print(f"{'Rank':<8} {'Tensor Size':<14} {'Latency':<14} {'Effective BW':<18}")
    print("-" * 60)
    for r in range(args.world_size):
        st = results[r]
        print(f" Rank {r:<3} {st.tensor_bytes / (1024**2):.1f} MB        {st.latency_us:.2f} us       {st.bandwidth_gbps:.2f} GB/s")
    print("=" * 70)


if __name__ == "__main__":
    main()
