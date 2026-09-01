"""
Crystal Direct Memory Access (libcdma) High-Level Python API
Provides asynchronous, high-throughput memory copy engines between hosts & devices.
"""

from typing import Optional, List, Dict, Any, Union
import time
import threading
from .device import UBDevice
from daemon.port import UBPacket, OP_CDMA_SUBMIT, OP_CDMA_COMPLETE, OP_RESP_OK


class CDMADescriptor:
    def __init__(self,
                 desc_id: int,
                 src_node: int,
                 dst_node: int,
                 src_offset: int,
                 dst_seg_id: int,
                 dst_offset: int,
                 length: int,
                 token_id: int = 0,
                 payload: Optional[bytes] = None):
        self.desc_id = desc_id
        self.src_node = src_node
        self.dst_node = dst_node
        self.src_offset = src_offset
        self.dst_seg_id = dst_seg_id
        self.dst_offset = dst_offset
        self.length = length
        self.token_id = token_id
        self.payload = payload or b""
        self.completed = False
        self.sim_latency_ns = 0.0
        self.error: Optional[str] = None


class CDMATask:
    def __init__(self, engine: 'CDMAEngine', descriptors: List[CDMADescriptor]):
        self.engine = engine
        self.descriptors = descriptors
        self._event = threading.Event()
        self.total_bytes = sum(d.length for d in descriptors)
        self.elapsed_sim_latency_ns = 0.0

    def mark_done(self, sim_latency_ns: float, error: Optional[str] = None):
        self.elapsed_sim_latency_ns = sim_latency_ns
        for d in self.descriptors:
            d.completed = True
            d.sim_latency_ns = sim_latency_ns
            d.error = error
        self._event.set()

    def wait(self, timeout: Optional[float] = 10.0) -> bool:
        return self._event.wait(timeout=timeout)


class CDMAEngine:
    """
    Crystal DMA Engine for asynchronous host-to-device and host-to-host transfers.
    """
    def __init__(self, node_id: int, device: Optional[UBDevice] = None, socket_path: str = "/tmp/ub-fabric/fabric.sock"):
        self.node_id = node_id
        self.device = device or UBDevice(node_id=node_id, socket_path=socket_path)
        self._next_desc_id = 1
        self._lock = threading.Lock()

    def submit_dma_write(self, dst_node: int, dst_seg_id: int, dst_offset: int, data: Union[bytes, bytearray], token_id: int = 0) -> CDMATask:
        """
        Asynchronously submits a DMA write task.
        """
        payload = bytes(data)
        length = len(payload)
        with self._lock:
            desc_id = self._next_desc_id
            self._next_desc_id += 1

        desc = CDMADescriptor(
            desc_id=desc_id,
            src_node=self.node_id,
            dst_node=dst_node,
            src_offset=0,
            dst_seg_id=dst_seg_id,
            dst_offset=dst_offset,
            length=length,
            token_id=token_id,
            payload=payload
        )
        task = CDMATask(self, [desc])

        # Submit via UB Fabric packet
        seq = self.device._get_seq()
        pkt = UBPacket(
            opcode=OP_CDMA_SUBMIT,
            src_node=self.node_id,
            dst_node=dst_node,
            token_id=token_id,
            seq_num=seq,
            metadata={"segment_id": dst_seg_id, "offset": dst_offset, "desc_id": desc_id},
            payload=payload
        )

        def _async_exec():
            try:
                resp = self.device.send_sync(pkt)
                if resp and resp.opcode in (OP_CDMA_COMPLETE, OP_RESP_OK):
                    lat = resp.metadata.get("sim_latency_ns", 0.0)
                    task.mark_done(lat)
                else:
                    err = resp.metadata.get("error", "DMA Failed") if resp else "No response"
                    task.mark_done(0.0, error=err)
            except Exception as e:
                task.mark_done(0.0, error=str(e))

        t = threading.Thread(target=_async_exec, daemon=True)
        t.start()
        return task

    def close(self):
        self.device.close()
