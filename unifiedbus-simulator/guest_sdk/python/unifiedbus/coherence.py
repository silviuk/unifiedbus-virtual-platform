"""
Cache Coherence & Directory Snooping Simulator (MESI Protocol over UB)
"""

from typing import Dict, Optional
from .device import UBDevice
from daemon.port import (
    UBPacket, OP_SNOOP_REQ, OP_SNOOP_RESP, OP_CACHE_WB, OP_CACHE_EVICT, OP_RESP_OK
)


class UBCacheAgent:
    def __init__(self, node_id: int, socket_path: str = "/tmp/ub-fabric/fabric.sock"):
        self.node_id = node_id
        self.device = UBDevice(node_id=node_id, socket_path=socket_path)
        self.lines: Dict[int, str] = {} # line_addr -> MESI State ('M', 'E', 'S', 'I')

    def request_snoop_invalidation(self, target_node: int, line_addr: int) -> str:
        seq = self.device._get_seq()
        pkt = UBPacket(
            opcode=OP_SNOOP_REQ,
            src_node=self.node_id,
            dst_node=target_node,
            seq_num=seq,
            metadata={"line_addr": line_addr, "type": "INVALIDATE"}
        )
        resp = self.device.send_sync(pkt)
        if not resp or resp.opcode != OP_SNOOP_RESP:
            raise RuntimeError(f"Snoop request failed for line 0x{line_addr:X}")
        return resp.metadata.get("state", "INVALID")

    def writeback_cacheline(self, home_node: int, line_addr: int, data: bytes) -> float:
        seq = self.device._get_seq()
        pkt = UBPacket(
            opcode=OP_CACHE_WB,
            src_node=self.node_id,
            dst_node=home_node,
            seq_num=seq,
            metadata={"line_addr": line_addr},
            payload=data
        )
        resp = self.device.send_sync(pkt)
        if not resp or resp.opcode != OP_SNOOP_RESP:
            raise RuntimeError(f"Cache writeback failed for line 0x{line_addr:X}")
        return resp.metadata.get("sim_latency_ns", 0.0)

    def close(self):
        self.device.close()
