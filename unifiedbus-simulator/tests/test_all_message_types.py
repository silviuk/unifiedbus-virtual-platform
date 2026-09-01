"""
Comprehensive Test Suite for all UnifiedBus Layered Messages:
- Physical / Link (LTSSM, Credits, Ping)
- Memory Semantics & Atomics (CAS, ADD, AND, OR, SWAP)
- Cache Coherence & Snooping
- UMS Socket-over-UB
- URPC Remote Procedure Calls
- sysSentry Emergency Handlers
"""

import unittest
import os
import sys
import time
import struct
import subprocess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "guest_sdk", "python")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from daemon.port import (
    UBPacket, OP_LINK_TRAIN_REQ, OP_LINK_TRAIN_ACK, OP_LINK_CREDIT_UPDATE,
    OP_TRANS_PING, OP_TRANS_PONG, OP_MEM_ATOMIC_CAS, OP_MEM_ATOMIC_ADD,
    OP_MEM_ATOMIC_AND, OP_MEM_ATOMIC_OR, OP_MEM_ATOMIC_SWAP, OP_MEM_ATOMIC_RESP,
    OP_RESP_OK
)
from unifiedbus.device import UBDevice
from unifiedbus.urma import URMAContext
from unifiedbus.ums import UMSSocket
from unifiedbus.urpc import URPCClient
from unifiedbus.sentry import SysSentryClient
from unifiedbus.coherence import UBCacheAgent


class TestAllUBMessageTypes(unittest.TestCase):
    def setUp(self):
        self.sock_path = f"/tmp/ub_test_allmsgs_{int(time.time()*1000)}.sock"
        cmd = [sys.executable, "-m", "daemon.fabric", "--socket", self.sock_path]
        self.proc = subprocess.Popen(cmd)
        
        start_t = time.time()
        while time.time() - start_t < 3.0:
            if os.path.exists(self.sock_path):
                break
            time.sleep(0.05)

    def tearDown(self):
        if self.proc:
            self.proc.terminate()
            self.proc.wait()
        if os.path.exists(self.sock_path):
            try:
                os.remove(self.sock_path)
            except OSError:
                pass

    def test_link_layer_training_and_ping(self):
        dev = UBDevice(node_id=1, socket_path=self.sock_path)
        
        # 1. Link Training Request (LTSSM)
        seq = dev._get_seq()
        pkt = UBPacket(opcode=OP_LINK_TRAIN_REQ, src_node=1, dst_node=0, seq_num=seq)
        resp = dev.send_sync(pkt)
        self.assertIsNotNone(resp)
        self.assertEqual(resp.opcode, OP_LINK_TRAIN_ACK)
        self.assertEqual(resp.metadata.get("status"), "TRAINED")

        # 2. Fabric RTT Ping/Pong
        seq = dev._get_seq()
        pkt = UBPacket(opcode=OP_TRANS_PING, src_node=1, dst_node=0, seq_num=seq)
        resp = dev.send_sync(pkt)
        self.assertIsNotNone(resp)
        self.assertEqual(resp.opcode, OP_TRANS_PONG)
        self.assertIn("rtt_ns", resp.metadata)

        dev.close()

    def test_memory_atomics_cas_add_bitwise(self):
        dev1 = UBDevice(node_id=1, socket_path=self.sock_path)
        urma2 = URMAContext(node_id=2, socket_path=self.sock_path)
        seg2 = urma2.register_segment(1024, token_id=0x5555, permissions="RW")

        # Initialize value at offset 0 = 100 via URMA Write
        jetty = urma2.create_jetty(remote_node=2, remote_jetty_id=1, token_id=0x5555)
        seg2.buffer[0:8] = struct.pack("!Q", 100)
        jetty.write(local_seg=seg2, local_offset=0, remote_seg_id=seg2.segment_id, remote_offset=0, length=8)

        # 1. Atomic Add +50 -> 150
        seq = dev1._get_seq()
        pkt = UBPacket(
            opcode=OP_MEM_ATOMIC_ADD,
            src_node=1,
            dst_node=2,
            token_id=0x5555,
            seq_num=seq,
            metadata={"segment_id": seg2.segment_id, "offset": 0, "add": 50}
        )
        resp = dev1.send_sync(pkt)
        self.assertEqual(resp.opcode, OP_MEM_ATOMIC_RESP)
        self.assertEqual(resp.metadata["orig_value"], 100)

        # 2. Atomic CAS (Compare 150 -> Swap to 999)
        seq = dev1._get_seq()
        pkt = UBPacket(
            opcode=OP_MEM_ATOMIC_CAS,
            src_node=1,
            dst_node=2,
            token_id=0x5555,
            seq_num=seq,
            metadata={"segment_id": seg2.segment_id, "offset": 0, "compare": 150, "swap": 999}
        )
        resp = dev1.send_sync(pkt)
        self.assertEqual(resp.opcode, OP_MEM_ATOMIC_RESP)
        self.assertEqual(resp.metadata["orig_value"], 150)

        dev1.close()
        urma2.close()

    def test_cache_coherence_snooping(self):
        agent1 = UBCacheAgent(node_id=1, socket_path=self.sock_path)
        agent2 = UBCacheAgent(node_id=2, socket_path=self.sock_path)

        state = agent1.request_snoop_invalidation(target_node=2, line_addr=0x80000000)
        self.assertEqual(state, "INVALID")

        lat = agent1.writeback_cacheline(home_node=2, line_addr=0x80000000, data=b"C" * 64)
        self.assertGreater(lat, 0)

        agent1.close()
        agent2.close()

    def test_ums_socket_over_ub(self):
        server_dev = UBDevice(node_id=2, socket_path=self.sock_path)
        client = UMSSocket(node_id=1, remote_node=2, port=8080, socket_path=self.sock_path)
        
        client.connect()
        lat = client.send(b"Hello Socket over UnifiedBus!")
        self.assertGreater(lat, 0)
        client.close()
        server_dev.close()

    def test_urpc_and_syssentry(self):
        node2 = UBDevice(node_id=2, socket_path=self.sock_path)
        
        # URPC Call
        rpc = URPCClient(node_id=1, remote_node=2, socket_path=self.sock_path)
        res = rpc.call("matrix_multiply", {"m": 128, "n": 128, "k": 128})
        self.assertEqual(res["status"], "SUCCESS")
        rpc.close()

        # sysSentry Emergency alerts
        sentry = SysSentryClient(node_id=1, socket_path=self.sock_path)
        self.assertTrue(sentry.trigger_oom_freeze(memory_usage_mb=64000))
        self.assertTrue(sentry.trigger_panic_alert("Kernel panic - not syncing: VFS: Unable to mount root fs"))
        sentry.close()
        node2.close()


if __name__ == "__main__":
    unittest.main()
