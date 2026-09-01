"""
Unit Tests for CDMA (Crystal Direct Memory Access) APIs
"""

import unittest
import os
import sys
import time
import subprocess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "guest_sdk", "python")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unifiedbus.cdma import CDMAEngine
from unifiedbus.urma import URMAContext


class TestCDMAEngine(unittest.TestCase):
    def setUp(self):
        self.sock_path = f"/tmp/ub_test_cdma_{int(time.time()*1000)}.sock"
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

    def test_cdma_async_write_completion(self):
        node2 = URMAContext(node_id=2, socket_path=self.sock_path)
        target_seg = node2.register_segment(65536, token_id=0x999, permissions="RW")

        cdma = CDMAEngine(node_id=1, socket_path=self.sock_path)
        data = b"CDMA_DATA_TEST_STREAM" * 10

        task = cdma.submit_dma_write(
            dst_node=2,
            dst_seg_id=target_seg.segment_id,
            dst_offset=0,
            data=data,
            token_id=0x999
        )

        done = task.wait(timeout=3.0)
        self.assertTrue(done)
        self.assertTrue(task.descriptors[0].completed)
        self.assertIsNone(task.descriptors[0].error)
        self.assertGreater(task.elapsed_sim_latency_ns, 0)

        cdma.close()
        node2.close()


if __name__ == "__main__":
    unittest.main()
