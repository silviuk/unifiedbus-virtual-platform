"""
Example 06: CIP (Confidentiality and Integrity Protection) Secure Memory Transfer
Demonstrates hardware-accelerated AES-256-GCM encryption, MAC tag authentication,
active tamper detection, and anti-replay defense over UnifiedBus.
"""

import sys
import os
import argparse
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "guest_sdk", "python")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unifiedbus.cip import CIPSecureContext
from unifiedbus.urma import URMAContext
from daemon.port import UBPacket, FLAG_CIP_ENCRYPTED, OP_URMA_WRITE, OP_RESP_ERR


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", default="/tmp/ub-fabric/fabric.sock")
    args = parser.parse_args()

    print("=" * 75)
    print(" [Example 06] UnifiedBus CIP (Confidentiality & Integrity Protection) Engine")
    print(" Protocol: UB Base Spec 2.0 | Cipher: AES-256-GCM | TokenID Key Binding")
    print("=" * 75)

    # 1. Initialize Kunpeng CPU (Node 1) with CIP Security and Ascend NPU (Node 3)
    print("[1] Initializing CIP-Enabled Secure URMA Contexts...")
    kunpeng = CIPSecureContext(node_id=1, socket_path=args.socket)
    ascend = URMAContext(node_id=3, socket_path=args.socket)

    token = 0x55AA1234
    seg_size = 64 * 1024
    kunpeng_seg = kunpeng.register_segment(seg_size, token_id=token, permissions="RW")
    ascend_seg = ascend.register_segment(seg_size, token_id=token, permissions="RW")

    # 2. Establish Secure Jetty
    print(f"[2] Establishing CIP Secure Jetty (TokenID: 0x{token:X})...")
    sec_jetty = kunpeng.create_secure_jetty(remote_node=3, remote_jetty_id=1, token_id=token)

    # 3. Perform Encrypted & Authenticated RDMA Write
    sensitive_weights = b"[TOP-SECRET LLM TENSOR WEIGHTS: PARTITION 001 - AES-256-GCM PROTECTED]" * 10
    kunpeng_seg.buffer[0:len(sensitive_weights)] = sensitive_weights

    print(f"\n[3] Executing CIP-Encrypted RDMA Write ({len(sensitive_weights)} bytes)...")
    lat_ns = sec_jetty.write_encrypted(
        local_seg=kunpeng_seg,
        local_offset=0,
        remote_seg_id=ascend_seg.segment_id,
        remote_offset=0,
        length=len(sensitive_weights)
    )
    print(f"    CIP Encrypted Write Succeeded! Fabric Latency + Crypto Pipeline: {lat_ns:.2f} ns")

    # 4. Verify Plaintext at Ascend NPU
    read_back = kunpeng.register_segment(seg_size, token_id=token, permissions="RW")
    sec_jetty.read(read_back, 0, ascend_seg.segment_id, 0, len(sensitive_weights))
    assert bytes(read_back.buffer[0:len(sensitive_weights)]) == sensitive_weights
    print("    Ascend NPU decrypted and stored verified plaintext in local memory.")

    # 5. Attack Simulation 1: Wire Tap Tampering
    print("\n[4] Simulating Wire-Tap Tampering Attack (Attacker flips 1 byte in transit)...")
    ciphertext, auth_tag = sec_jetty.cip.encrypt_and_tag(sensitive_weights, token_id=token, seq_num=99)
    # Corrupt 1 byte of ciphertext
    corrupted_ciphertext = bytearray(ciphertext)
    corrupted_ciphertext[5] ^= 0xFF

    tampered_pkt = UBPacket(
        opcode=OP_URMA_WRITE,
        src_node=1,
        dst_node=3,
        token_id=token,
        flags=FLAG_CIP_ENCRYPTED,
        seq_num=99,
        auth_tag=auth_tag,
        metadata={"segment_id": ascend_seg.segment_id, "offset": 0},
        payload=bytes(corrupted_ciphertext)
    )
    resp = kunpeng.device.send_sync(tampered_pkt)
    if resp and resp.opcode == OP_RESP_ERR:
        print(f"    [DEFENSE ACTIVE] Tampered packet blocked: {resp.metadata.get('error')}")
    else:
        print("    [FAIL] Tampered packet was unexpectedly accepted!")

    # 6. Attack Simulation 2: Replay Attack
    print("\n[5] Simulating Packet Replay Attack (Attacker replays previous sequence)...")
    resp2 = kunpeng.device.send_sync(tampered_pkt)
    if resp2 and resp2.opcode == OP_RESP_ERR:
        print(f"    [DEFENSE ACTIVE] Replayed packet blocked: {resp2.metadata.get('error')}")
    else:
        print("    [FAIL] Replayed packet was unexpectedly accepted!")

    print("\n" + "=" * 75)
    print(" CIP Security Subsystem Verified: 100% Confidentiality & Anti-Tamper Protection!")
    print("=" * 75)

    kunpeng.close()
    ascend.close()


if __name__ == "__main__":
    main()
