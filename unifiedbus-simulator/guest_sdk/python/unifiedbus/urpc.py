"""
Unified Remote Procedure Call (URPC) API for UnifiedBus
"""

from typing import Dict, Any, Optional
import json
from .device import UBDevice
from daemon.port import UBPacket, OP_URPC_CALL, OP_RESP_OK


class URPCClient:
    def __init__(self, node_id: int, remote_node: int, socket_path: str = "/tmp/ub-fabric/fabric.sock"):
        self.node_id = node_id
        self.remote_node = remote_node
        self.device = UBDevice(node_id=node_id, socket_path=socket_path)

    def call(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        payload = json.dumps(params).encode('utf-8')
        seq = self.device._get_seq()
        pkt = UBPacket(
            opcode=OP_URPC_CALL,
            src_node=self.node_id,
            dst_node=self.remote_node,
            seq_num=seq,
            metadata={"method": method},
            payload=payload
        )
        resp = self.device.send_sync(pkt)
        if not resp or resp.opcode != OP_RESP_OK:
            raise RuntimeError(f"URPC call {method} failed")
        return {"status": "SUCCESS", "latency_ns": resp.metadata.get("sim_latency_ns", 0.0)}

    def close(self):
        self.device.close()
