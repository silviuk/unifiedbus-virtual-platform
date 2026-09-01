"""
sysSentry Emergency Event Monitor for UnifiedBus
Handles OOM, panic isolation, and emergency notification over the UB fabric.
"""

from .device import UBDevice
from daemon.port import (
    UBPacket, OP_SENTRY_OOM_BLOCK, OP_SENTRY_PANIC_BLOCK,
    OP_SENTRY_REBOOT_NOTIFY, OP_RESP_OK
)


class SysSentryClient:
    def __init__(self, node_id: int, socket_path: str = "/tmp/ub-fabric/fabric.sock"):
        self.node_id = node_id
        self.device = UBDevice(node_id=node_id, socket_path=socket_path)

    def trigger_oom_freeze(self, memory_usage_mb: int) -> bool:
        seq = self.device._get_seq()
        pkt = UBPacket(
            opcode=OP_SENTRY_OOM_BLOCK,
            src_node=self.node_id,
            dst_node=0,
            seq_num=seq,
            metadata={"reason": f"OOM threshold exceeded ({memory_usage_mb} MB)", "action": "FREEZE_LOCAL_PAGING"}
        )
        resp = self.device.send_sync(pkt)
        return resp is not None and resp.opcode == OP_RESP_OK

    def trigger_panic_alert(self, panic_message: str) -> bool:
        seq = self.device._get_seq()
        pkt = UBPacket(
            opcode=OP_SENTRY_PANIC_BLOCK,
            src_node=self.node_id,
            dst_node=0,
            seq_num=seq,
            metadata={"reason": f"Kernel Panic: {panic_message}", "action": "ISOLATE_LINK"}
        )
        resp = self.device.send_sync(pkt)
        return resp is not None and resp.opcode == OP_RESP_OK

    def close(self):
        self.device.close()
