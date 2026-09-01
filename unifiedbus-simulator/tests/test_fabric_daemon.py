"""
Unit Tests for UnifiedBus Fabric Switch & Packet Protocols
"""

import unittest
import os
import sys
import time
import subprocess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "guest_sdk", "python")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from daemon.port import UBPacket, OP_REG_NODE, OP_RESP_OK
from unifiedbus.device import UBDevice


class TestFabricDaemon(unittest.TestCase):
    def test_packet_serialization_crc(self):
        pkt = UBPacket(
            opcode=0x10,
            src_node=1,
            dst_node=2,
            token_id=0xCAFE,
            virtual_lane=1,
            seq_num=42,
            metadata={"key": "value", "offset": 1024},
            payload=b"HelloWorld1234"
        )
        serialized = pkt.serialize()
        deserialized, consumed = UBPacket.deserialize_from_buffer(serialized)
        
        self.assertIsNotNone(deserialized)
        self.assertEqual(consumed, len(serialized))
        self.assertEqual(deserialized.opcode, 0x10)
        self.assertEqual(deserialized.src_node, 1)
        self.assertEqual(deserialized.dst_node, 2)
        self.assertEqual(deserialized.token_id, 0xCAFE)
        self.assertEqual(deserialized.virtual_lane, 1)
        self.assertEqual(deserialized.seq_num, 42)
        self.assertEqual(deserialized.metadata, {"key": "value", "offset": 1024})
        self.assertEqual(deserialized.payload, b"HelloWorld1234")

    def test_packet_crc_corruption_detection(self):
        pkt = UBPacket(opcode=0x10, src_node=1, dst_node=2, payload=b"TestData")
        data = bytearray(pkt.serialize())
        data[-1] ^= 0xFF
        
        with self.assertRaises(ValueError):
            UBPacket.deserialize_from_buffer(bytes(data))

    def test_fabric_switch_lifecycle(self):
        sock_path = f"/tmp/ub_test_fabric_{int(time.time() * 1000)}.sock"
        cmd = [sys.executable, "-m", "daemon.fabric", "--socket", sock_path]
        proc = subprocess.Popen(cmd)
        
        start_t = time.time()
        while time.time() - start_t < 3.0:
            if os.path.exists(sock_path):
                break
            time.sleep(0.05)

        self.assertTrue(os.path.exists(sock_path))

        dev = UBDevice(node_id=1, node_type="KUNPENG_CPU", socket_path=sock_path)
        self.assertEqual(dev.node_id, 1)
        dev.close()

        proc.terminate()
        proc.wait()
        if os.path.exists(sock_path):
            try:
                os.remove(sock_path)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
