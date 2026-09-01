"""
Unified Remote Memory Access (liburma) High-Level Python API
Implements endpoints (Jetties), registered Segments, and RDMA-style memory operations.
"""

from typing import Optional, Union, Dict, Any
import time
from .device import UBDevice
from daemon.port import (
    UBPacket, OP_REG_SEG, OP_UNREG_SEG, OP_CREATE_JETTY,
    OP_URMA_WRITE, OP_URMA_READ, OP_URMA_READ_RESP, OP_URMA_ATOMIC_CAS,
    OP_URMA_ATOMIC_ADD, OP_URMA_SEND, OP_URMA_RECV, OP_RESP_OK, OP_RESP_ERR
)


class URMASegment:
    def __init__(self, segment_id: int, base_addr: int, size: int, token_id: int, permissions: str, buffer: Optional[bytearray] = None):
        self.segment_id = segment_id
        self.base_addr = base_addr
        self.size = size
        self.token_id = token_id
        self.permissions = permissions
        self.buffer = buffer if buffer is not None else bytearray(size)


class URMAJetty:
    def __init__(self, context: 'URMAContext', local_jetty_id: int, remote_node: int, remote_jetty_id: int, token_id: int):
        self.context = context
        self.local_jetty_id = local_jetty_id
        self.remote_node = remote_node
        self.remote_jetty_id = remote_jetty_id
        self.token_id = token_id

    def write(self, local_seg: URMASegment, local_offset: int, remote_seg_id: int, remote_offset: int, length: int) -> float:
        """
        Executes synchronous RDMA Write.
        Returns simulated transfer latency in nanoseconds.
        """
        payload = bytes(local_seg.buffer[local_offset:local_offset + length])
        seq = self.context.device._get_seq()
        pkt = UBPacket(
            opcode=OP_URMA_WRITE,
            src_node=self.context.node_id,
            dst_node=self.remote_node,
            token_id=self.token_id,
            seq_num=seq,
            metadata={"segment_id": remote_seg_id, "offset": remote_offset},
            payload=payload
        )
        resp = self.context.device.send_sync(pkt)
        if not resp or resp.opcode != OP_RESP_OK:
            err = resp.metadata.get("error", "Unknown error") if resp else "No response"
            raise RuntimeError(f"URMA Write failed: {err}")
        return resp.metadata.get("sim_latency_ns", 0.0)

    def read(self, local_seg: URMASegment, local_offset: int, remote_seg_id: int, remote_offset: int, length: int) -> float:
        """
        Executes synchronous RDMA Read from remote segment into local segment.
        Returns simulated transfer latency in nanoseconds.
        """
        seq = self.context.device._get_seq()
        pkt = UBPacket(
            opcode=OP_URMA_READ,
            src_node=self.context.node_id,
            dst_node=self.remote_node,
            token_id=self.token_id,
            seq_num=seq,
            metadata={"segment_id": remote_seg_id, "offset": remote_offset, "length": length}
        )
        resp = self.context.device.send_sync(pkt)
        if not resp or resp.opcode != OP_URMA_READ_RESP:
            err = resp.metadata.get("error", "Unknown error") if resp else "No response"
            raise RuntimeError(f"URMA Read failed: {err}")
        
        # Copy data into local segment buffer
        local_seg.buffer[local_offset:local_offset + length] = resp.payload
        return resp.metadata.get("sim_latency_ns", 0.0)

    def send(self, payload: bytes):
        seq = self.context.device._get_seq()
        pkt = UBPacket(
            opcode=OP_URMA_SEND,
            src_node=self.context.node_id,
            dst_node=self.remote_node,
            token_id=self.token_id,
            seq_num=seq,
            payload=payload
        )
        resp = self.context.device.send_sync(pkt)
        if not resp or resp.opcode != OP_RESP_OK:
            raise RuntimeError("URMA Send failed")


class URMAContext:
    def __init__(self, node_id: int, device: Optional[UBDevice] = None, socket_path: str = "/tmp/ub-fabric/fabric.sock"):
        self.node_id = node_id
        self.device = device or UBDevice(node_id=node_id, socket_path=socket_path)
        self._next_seg_id = 1
        self._next_jetty_id = 1
        self.segments: Dict[int, URMASegment] = {}
        self.jetties: Dict[int, URMAJetty] = {}

    def register_segment(self, size_or_buf: Union[int, bytearray, bytes], token_id: int = 0, permissions: str = "RW") -> URMASegment:
        if isinstance(size_or_buf, int):
            size = size_or_buf
            buf = bytearray(size)
        else:
            size = len(size_or_buf)
            buf = bytearray(size_or_buf)

        seg_id = self._next_seg_id
        self._next_seg_id += 1
        
        seq = self.device._get_seq()
        pkt = UBPacket(
            opcode=OP_REG_SEG,
            src_node=self.node_id,
            dst_node=0,
            token_id=token_id,
            seq_num=seq,
            metadata={"segment_id": seg_id, "size": size, "permissions": permissions}
        )
        resp = self.device.send_sync(pkt)
        if not resp or resp.opcode != OP_RESP_OK:
            raise RuntimeError("Failed to register segment with UB fabric")

        seg = URMASegment(seg_id, base_addr=0, size=size, token_id=token_id, permissions=permissions, buffer=buf)
        self.segments[seg_id] = seg
        return seg

    def create_jetty(self, remote_node: int, remote_jetty_id: int, token_id: int = 0) -> URMAJetty:
        local_jetty_id = self._next_jetty_id
        self._next_jetty_id += 1

        seq = self.device._get_seq()
        pkt = UBPacket(
            opcode=OP_CREATE_JETTY,
            src_node=self.node_id,
            dst_node=0,
            token_id=token_id,
            seq_num=seq,
            metadata={
                "local_jetty_id": local_jetty_id,
                "remote_node": remote_node,
                "remote_jetty_id": remote_jetty_id
            }
        )
        resp = self.device.send_sync(pkt)
        if not resp or resp.opcode != OP_RESP_OK:
            raise RuntimeError("Failed to create Jetty with UB fabric")

        jetty = URMAJetty(self, local_jetty_id, remote_node, remote_jetty_id, token_id)
        self.jetties[local_jetty_id] = jetty
        return jetty

    def close(self):
        self.device.close()
