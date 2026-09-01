"""
Unified Socket (UMS / Socket over UB) API
Enables socket streaming applications to run over UnifiedBus fabric.
"""

from typing import Optional
from .device import UBDevice
from daemon.port import UBPacket, OP_UMS_SYN, OP_UMS_DATA, OP_UMS_FIN, OP_RESP_OK


class UMSSocket:
    def __init__(self, node_id: int, remote_node: int, port: int, socket_path: str = "/tmp/ub-fabric/fabric.sock"):
        self.node_id = node_id
        self.remote_node = remote_node
        self.port = port
        self.device = UBDevice(node_id=node_id, socket_path=socket_path)
        self.connected = False

    def connect(self):
        seq = self.device._get_seq()
        pkt = UBPacket(
            opcode=OP_UMS_SYN,
            src_node=self.node_id,
            dst_node=self.remote_node,
            seq_num=seq,
            metadata={"port": self.port}
        )
        resp = self.device.send_sync(pkt)
        if not resp or resp.opcode != OP_RESP_OK:
            raise ConnectionError(f"Failed to connect UMS socket to Node {self.remote_node}:{self.port}")
        self.connected = True

    def send(self, data: bytes) -> float:
        if not self.connected:
            raise ConnectionError("Socket not connected")
        seq = self.device._get_seq()
        pkt = UBPacket(
            opcode=OP_UMS_DATA,
            src_node=self.node_id,
            dst_node=self.remote_node,
            seq_num=seq,
            metadata={"port": self.port},
            payload=data
        )
        resp = self.device.send_sync(pkt)
        if not resp or resp.opcode != OP_RESP_OK:
            raise RuntimeError("UMS Data send failed")
        return resp.metadata.get("sim_latency_ns", 0.0)

    def close(self):
        if self.connected:
            seq = self.device._get_seq()
            pkt = UBPacket(
                opcode=OP_UMS_FIN,
                src_node=self.node_id,
                dst_node=self.remote_node,
                seq_num=seq,
                metadata={"port": self.port}
            )
            try:
                self.device.send_sync(pkt, timeout=1.0)
            except Exception:
                pass
            self.connected = False
        self.device.close()
