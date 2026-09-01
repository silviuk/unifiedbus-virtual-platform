"""
Example 03: Disaggregated Memory Pooling with OBMM (libobmm / UBs Mem)
Simulates Node 7 (Pooled Memory Appliance) loaning memory to Node 1 (Kunpeng CPU)
and Node 3 (Ascend NPU) with TokenID security.
"""

import sys
import os
import argparse
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "guest_sdk", "python")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unifiedbus.obmm import OBMMClient


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", default="/tmp/ub-fabric/fabric.sock")
    args = parser.parse_args()

    print("=" * 70)
    print(" [Example 03] UnifiedBus OBMM Disaggregated Memory Pooling")
    print("=" * 70)

    # 1. Initialize Memory Pool Appliance (Node 7)
    mem_node = OBMMClient(node_id=7, socket_path=args.socket)
    
    # 2. Node 7 exports a 16 GB global memory pool
    pool_token = 0xABCD1234
    pool_size = 16 * 1024 * 1024 * 1024  # 16 GB
    print(f"[1] Node 7 exporting 16 GB memory pool (TokenID: 0x{pool_token:X})...")
    pool_id = mem_node.export_memory(size_bytes=pool_size, token_id=pool_token, permissions="RW")
    print(f"    Exported Pool ID: 0x{pool_id:04X}")

    # 3. Kunpeng Host (Node 1) imports the pool
    print("\n[2] Kunpeng Host (Node 1) importing pool 0x{:04X}...".format(pool_id))
    kunpeng = OBMMClient(node_id=1, socket_path=args.socket)
    kunpeng_pool = kunpeng.import_memory(pool_id=pool_id, token_id=pool_token)
    print(f"    Imported successfully! Mapped size: {kunpeng_pool.size / (1024**3):.1f} GB")

    # 4. Kunpeng writes an AI model embedding partition into the remote pool
    embedding_data = b"[Embedding Weights Vector Part 0: Kunpeng to Remote HBM Pool]" * 50
    print(f"[3] Kunpeng writing {len(embedding_data)} bytes into remote pool offset 0x1000...")
    lat_ns = kunpeng_pool.write(offset=0x1000, data=embedding_data)
    print(f"    Write acknowledged! UMMU Translation & Bus Latency: {lat_ns:.2f} ns")

    # 5. Ascend NPU (Node 3) imports the exact same pool and reads the embeddings
    print("\n[4] Ascend NPU (Node 3) importing the shared memory pool...")
    ascend = OBMMClient(node_id=3, socket_path=args.socket)
    ascend_pool = ascend.import_memory(pool_id=pool_id, token_id=pool_token)
    
    print("[5] Ascend NPU reading embeddings directly from remote pool...")
    read_back = ascend_pool.read(offset=0x1000, length=len(embedding_data))
    assert read_back == embedding_data, "Data mismatch in shared memory pool!"
    print(f"    Ascend NPU read back {len(read_back)} bytes correctly!")

    # 6. Test TokenID Security Isolation (Node with wrong TokenID fails)
    print("\n[6] Testing TokenID Security Isolation (unauthorized node access)...")
    rogue_node = OBMMClient(node_id=8, socket_path=args.socket)
    try:
        rogue_node.import_memory(pool_id=pool_id, token_id=0xDEADBEEF)
        print("    [FAIL] Rogue node unexpectedly accessed pool!")
    except Exception as e:
        print(f"    [PASS] Rogue access rejected as expected: {e}")

    print("=" * 70)
    mem_node.close()
    kunpeng.close()
    ascend.close()
    rogue_node.close()


if __name__ == "__main__":
    main()
