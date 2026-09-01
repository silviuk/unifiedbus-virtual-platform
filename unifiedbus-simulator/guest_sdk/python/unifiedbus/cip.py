"""
UnifiedBus CIP (Confidentiality and Integrity Protection) Client SDK
Enables applications to perform hardware-accelerated encrypted memory writes & reads
with TokenID key derivation and MAC integrity verification.
"""

from typing import Tuple, Optional
from daemon.cip import CIPEngine, CIP_SUITE_AES_256_GCM, CIP_SUITE_SM4_GCM
from daemon.port import UBPacket, FLAG_CIP_ENCRYPTED, OP_URMA_WRITE, OP_URMA_READ, OP_URMA_READ_RESP, OP_RESP_OK
from .device import UBDevice
from .urma import URMAContext, URMASegment, URMAJetty


class CIPSecureJetty(URMAJetty):
    """
    Jetty endpoint with hardware-accelerated CIP Authenticated Encryption enabled.
    """
    def __init__(self, context: 'CIPSecureContext', local_jetty_id: int, remote_node: int, remote_jetty_id: int, token_id: int):
        super().__init__(context, local_jetty_id, remote_node, remote_jetty_id, token_id)
        self.cip = CIPEngine(cipher_suite=CIP_SUITE_AES_256_GCM)

    def write_encrypted(self, local_seg: URMASegment, local_offset: int, remote_seg_id: int, remote_offset: int, length: int) -> float:
        """
        Performs CIP-encrypted and MAC-tagged RDMA Write.
        """
        plaintext = bytes(local_seg.buffer[local_offset:local_offset + length])
        seq = self.context.device._get_seq()
        
        # Hardware CIP Authenticated Encryption
        ciphertext, auth_tag = self.cip.encrypt_and_tag(
            payload=plaintext,
            token_id=self.token_id,
            seq_num=seq
        )

        pkt = UBPacket(
            opcode=OP_URMA_WRITE,
            src_node=self.context.node_id,
            dst_node=self.remote_node,
            token_id=self.token_id,
            flags=FLAG_CIP_ENCRYPTED,
            seq_num=seq,
            auth_tag=auth_tag,
            metadata={"segment_id": remote_seg_id, "offset": remote_offset},
            payload=ciphertext
        )
        
        resp = self.context.device.send_sync(pkt)
        if not resp or resp.opcode != OP_RESP_OK:
            err = resp.metadata.get("error", "CIP Write failed") if resp else "No response"
            raise RuntimeError(f"CIP Secure Write rejected: {err}")
        return resp.metadata.get("sim_latency_ns", 0.0)


class CIPSecureContext(URMAContext):
    """
    URMA Context with integrated CIP Security layer.
    """
    def __init__(self, node_id: int, socket_path: str = "/tmp/ub-fabric/fabric.sock"):
        super().__init__(node_id=node_id, socket_path=socket_path)

    def create_secure_jetty(self, remote_node: int, remote_jetty_id: int, token_id: int = 0) -> CIPSecureJetty:
        local_jetty_id = self._next_jetty_id
        self._next_jetty_id += 1

        jetty = CIPSecureJetty(self, local_jetty_id, remote_node, remote_jetty_id, token_id)
        self.jetties[local_jetty_id] = jetty
        return jetty
