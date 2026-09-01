"""
Unit Tests for UnifiedBus CIP (Confidentiality and Integrity Protection)
"""

import unittest
import os
import sys
import time
import subprocess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "guest_sdk", "python")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from daemon.cip import CIPEngine, CIP_SUITE_AES_256_GCM
from unifiedbus.cip import CIPSecureContext
from unifiedbus.urma import URMAContext


class TestCIPSecurity(unittest.TestCase):
    def setUp(self):
        self.sock_path = f"/tmp/ub_test_cip_{int(time.time()*1000)}.sock"
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

    def test_cip_engine_encrypt_decrypt(self):
        cip = CIPEngine(cipher_suite=CIP_SUITE_AES_256_GCM)
        token_id = 0xCAFE1234
        seq = 100
        payload = b"SecretTensorWeights456"

        ciphertext, tag = cip.encrypt_and_tag(payload, token_id, seq)
        self.assertNotEqual(ciphertext, payload)
        self.assertEqual(len(tag), 16)

        # Valid decryption
        valid, decrypted, msg = cip.decrypt_and_verify(ciphertext, tag, token_id, seq, src_node=1)
        self.assertTrue(valid)
        self.assertEqual(decrypted, payload)

        # Tampered ciphertext
        corrupted = bytearray(ciphertext)
        corrupted[0] ^= 0x01
        valid, _, err = cip.decrypt_and_verify(bytes(corrupted), tag, token_id, seq_num=101, src_node=1)
        self.assertFalse(valid)
        self.assertIn("Integrity Error", err)

        # Wrong TokenID
        valid, _, err = cip.decrypt_and_verify(ciphertext, tag, token_id=0xDEADBEEF, seq_num=102, src_node=1)
        self.assertFalse(valid)

    def test_cip_secure_write_over_fabric(self):
        kunpeng = CIPSecureContext(node_id=1, socket_path=self.sock_path)
        ascend = URMAContext(node_id=2, socket_path=self.sock_path)

        token = 0x8888
        seg1 = kunpeng.register_segment(1024, token_id=token, permissions="RW")
        seg2 = ascend.register_segment(1024, token_id=token, permissions="RW")

        sec_jetty = kunpeng.create_secure_jetty(remote_node=2, remote_jetty_id=1, token_id=token)

        data = b"ENCRYPTED_UB_DATA_PAYLOAD"
        seg1.buffer[0:len(data)] = data
        lat = sec_jetty.write_encrypted(seg1, 0, seg2.segment_id, 0, len(data))
        self.assertGreater(lat, 0)

        # Read back to verify plain data
        read_seg = kunpeng.register_segment(1024, token_id=token, permissions="RW")
        sec_jetty.read(read_seg, 0, seg2.segment_id, 0, len(data))
        self.assertEqual(bytes(read_seg.buffer[0:len(data)]), data)

        kunpeng.close()
        ascend.close()


if __name__ == "__main__":
    unittest.main()
