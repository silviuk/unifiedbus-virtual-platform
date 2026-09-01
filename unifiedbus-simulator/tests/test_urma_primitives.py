"""
Unit Tests for URMA (Unified Remote Memory Access) APIs
"""

import unittest
import os
import sys
import time
import subprocess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "guest_sdk", "python")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unifiedbus.urma import URMAContext


class TestURMAPrimitives(unittest.TestCase):
    def setUp(self):
        self.sock_path = f"/tmp/ub_test_urma_{int(time.time()*1000)}.sock"
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

    def test_urma_write_and_read(self):
        node1 = URMAContext(node_id=1, socket_path=self.sock_path)
        node2 = URMAContext(node_id=2, socket_path=self.sock_path)

        token = 0x1234
        seg1 = node1.register_segment(1024, token_id=token, permissions="RW")
        seg2 = node2.register_segment(1024, token_id=token, permissions="RW")

        jetty1 = node1.create_jetty(remote_node=2, remote_jetty_id=1, token_id=token)

        # Write payload
        test_data = b"UnifiedBus RDMA Write Payload 12345"
        seg1.buffer[:len(test_data)] = test_data
        lat_ns = jetty1.write(seg1, 0, seg2.segment_id, 0, len(test_data))
        self.assertGreater(lat_ns, 0)

        # Read payload back
        read_seg = node1.register_segment(1024, token_id=token, permissions="RW")
        read_lat_ns = jetty1.read(read_seg, 0, seg2.segment_id, 0, len(test_data))
        self.assertGreater(read_lat_ns, 0)

        self.assertEqual(bytes(read_seg.buffer[:len(test_data)]), test_data)

        node1.close()
        node2.close()


if __name__ == "__main__":
    unittest.main()
