"""
Unit Tests for OBMM (Open Borrowed Memory Management) Memory Pooling
"""

import unittest
import os
import sys
import time
import subprocess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "guest_sdk", "python")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unifiedbus.obmm import OBMMClient


class TestOBMMPooling(unittest.TestCase):
    def setUp(self):
        self.sock_path = f"/tmp/ub_test_obmm_{int(time.time()*1000)}.sock"
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

    def test_obmm_export_import_write_read(self):
        node_exporter = OBMMClient(node_id=1, socket_path=self.sock_path)
        node_borrower = OBMMClient(node_id=2, socket_path=self.sock_path)

        token = 0xAA55
        pool_id = node_exporter.export_memory(size_bytes=1024 * 1024, token_id=token, permissions="RW")
        self.assertGreater(pool_id, 0)

        pool_handle = node_borrower.import_memory(pool_id=pool_id, token_id=token)
        self.assertEqual(pool_handle.owner_node, 1)
        self.assertEqual(pool_handle.size, 1024 * 1024)

        test_payload = b"OBMM_SHARED_MEMORY_VERIFICATION"
        lat = pool_handle.write(offset=128, data=test_payload)
        self.assertGreater(lat, 0)

        read_back = pool_handle.read(offset=128, length=len(test_payload))
        self.assertEqual(read_back, test_payload)

        # Test wrong token access
        node_attacker = OBMMClient(node_id=3, socket_path=self.sock_path)
        with self.assertRaises(RuntimeError):
            node_attacker.import_memory(pool_id=pool_id, token_id=0xDEAD)

        node_exporter.close()
        node_borrower.close()
        node_attacker.close()


if __name__ == "__main__":
    unittest.main()
