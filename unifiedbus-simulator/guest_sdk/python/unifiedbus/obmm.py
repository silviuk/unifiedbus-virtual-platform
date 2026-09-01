"""
Open Borrowed Memory Management (libobmm / UBs Mem)
Provides memory pooling, disaggregated memory borrowing (EXPORT / IMPORT),
and UMMU global address window management.
"""

from typing import Optional, Dict, Any, Union
from .device import UBDevice
from daemon.port import (
    UBPacket, OP_OBMM_EXPORT, OP_OBMM_IMPORT, OP_URMA_WRITE, OP_URMA_READ,
    OP_URMA_READ_RESP, OP_RESP_OK, OP_RESP_ERR
)


class UBMMPoolHandle:
    def __init__(self, client: 'OBMMClient', pool_id: int, owner_node: int, segment_id: int, size: int, token_id: int, permissions: str):
        self.client = client
        self.pool_id = pool_id
        self.owner_node = owner_node
        self.segment_id = segment_id
        self.size = size
        self.token_id = token_id
        self.permissions = permissions

    def write(self, offset: int, data: Union[bytes, bytearray]) -> float:
        """
        Writes data to the borrowed remote memory pool.
        Returns simulated transfer latency in nanoseconds.
        """
        payload = bytes(data)
        length = len(payload)
        if offset + length > self.size:
            raise ValueError(f"Write exceeds pool size: offset={offset}, length={length}, size={self.size}")

        seq = self.client.device._get_seq()
        pkt = UBPacket(
            opcode=OP_URMA_WRITE,
            src_node=self.client.node_id,
            dst_node=self.owner_node,
            token_id=self.token_id,
            seq_num=seq,
            metadata={"segment_id": self.segment_id, "offset": offset},
            payload=payload
        )
        resp = self.client.device.send_sync(pkt)
        if not resp or resp.opcode != OP_RESP_OK:
            err = resp.metadata.get("error", "Write failed") if resp else "No response"
            raise RuntimeError(f"OBMM Pool Write failed: {err}")
        return resp.metadata.get("sim_latency_ns", 0.0)

    def read(self, offset: int, length: int) -> bytes:
        """
        Reads data from the borrowed remote memory pool.
        """
        if offset + length > self.size:
            raise ValueError(f"Read exceeds pool size: offset={offset}, length={length}, size={self.size}")

        seq = self.client.device._get_seq()
        pkt = UBPacket(
            opcode=OP_URMA_READ,
            src_node=self.client.node_id,
            dst_node=self.owner_node,
            token_id=self.token_id,
            seq_num=seq,
            metadata={"segment_id": self.segment_id, "offset": offset, "length": length}
        )
        resp = self.client.device.send_sync(pkt)
        if not resp or resp.opcode != OP_URMA_READ_RESP:
            err = resp.metadata.get("error", "Read failed") if resp else "No response"
            raise RuntimeError(f"OBMM Pool Read failed: {err}")
        return resp.payload


class OBMMClient:
    """
    Client for Open Borrowed Memory Management (OBMM).
    """
    def __init__(self, node_id: int, device: Optional[UBDevice] = None, socket_path: str = "/tmp/ub-fabric/fabric.sock"):
        self.node_id = node_id
        self.device = device or UBDevice(node_id=node_id, socket_path=socket_path)
        self.exported_pools: Dict[int, int] = {} # pool_id -> size

    def export_memory(self, size_bytes: int, token_id: int = 0, permissions: str = "RW") -> int:
        """
        Exports a chunk of local memory as a global pool for other nodes to borrow.
        Returns pool_id.
        """
        seq = self.device._get_seq()
        pkt = UBPacket(
            opcode=OP_OBMM_EXPORT,
            src_node=self.node_id,
            dst_node=0,
            token_id=token_id,
            seq_num=seq,
            metadata={"size": size_bytes, "permissions": permissions}
        )
        resp = self.device.send_sync(pkt)
        if not resp or resp.opcode != OP_RESP_OK:
            raise RuntimeError("Failed to export memory pool")
        
        pool_id = resp.metadata["pool_id"]
        self.exported_pools[pool_id] = size_bytes
        return pool_id

    def import_memory(self, pool_id: int, token_id: int = 0) -> UBMMPoolHandle:
        """
        Imports a borrowed memory pool using its pool_id and TokenID authorization.
        """
        seq = self.device._get_seq()
        pkt = UBPacket(
            opcode=OP_OBMM_IMPORT,
            src_node=self.node_id,
            dst_node=0,
            token_id=token_id,
            seq_num=seq,
            metadata={"pool_id": pool_id}
        )
        resp = self.device.send_sync(pkt)
        if not resp or resp.opcode != OP_RESP_OK:
            err = resp.metadata.get("error", "Import failed") if resp else "No response"
            raise RuntimeError(f"Failed to import pool 0x{pool_id:X}: {err}")

        meta = resp.metadata
        return UBMMPoolHandle(
            client=self,
            pool_id=pool_id,
            owner_node=meta["target_node"],
            segment_id=meta["segment_id"],
            size=meta["size"],
            token_id=token_id,
            permissions=meta["permissions"]
        )

    def close(self):
        self.device.close()
