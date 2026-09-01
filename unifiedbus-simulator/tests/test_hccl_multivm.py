"""
Unit Tests for HCCL (Huawei Collective Communication Library) over UB
"""

import unittest
import os
import sys
import time
import subprocess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "guest_sdk", "python")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unifiedbus.hccl import HCCLContext, ReduceOp


class TestHCCLMultiVM(unittest.TestCase):
    def setUp(self):
        self.sock_path = f"/tmp/ub_test_hccl_{int(time.time()*1000)}.sock"
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

    def test_hccl_allreduce_and_allgather(self):
        rank0 = HCCLContext(rank=0, world_size=2, socket_path=self.sock_path)
        rank1 = HCCLContext(rank=1, world_size=2, socket_path=self.sock_path)

        tensor = [1.0] * 1024
        
        res, stats = rank0.all_reduce(tensor, op=ReduceOp.SUM)
        self.assertEqual(stats.op_name, "AllReduce")
        self.assertEqual(stats.tensor_bytes, 1024 * 4)
        self.assertGreater(stats.latency_us, 0)

        res_gather, stats_gather = rank0.all_gather(tensor)
        self.assertEqual(stats_gather.op_name, "AllGather")
        self.assertEqual(len(res_gather), 2048)

        rank0.close()
        rank1.close()


if __name__ == "__main__":
    unittest.main()
