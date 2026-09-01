"""
UnifiedBus Virtual Device Driver Abstraction (guest-side)
Connects to the virtual UB Fabric or QEMU MMIO BARs.
"""

import socket
import threading
import time
from typing import Optional, Dict, Any, Tuple
from daemon.port import (
    UBPacket, OP_REG_NODE, OP_REG_SEG, OP_UNREG_SEG, OP_CREATE_JETTY,
    OP_URMA_WRITE, OP_URMA_READ, OP_URMA_READ_RESP, OP_URMA_ATOMIC_CAS,
    OP_URMA_ATOMIC_ADD, OP_URMA_ATOMIC_RESP, OP_URMA_SEND, OP_URMA_RECV,
    OP_CDMA_SUBMIT, OP_CDMA_COMPLETE, OP_OBMM_EXPORT, OP_OBMM_IMPORT,
    OP_QUERY_TOPOLOGY, OP_QUERY_STATS, OP_RESP_OK, OP_RESP_ERR,
    OP_LINK_TRAIN_ACK, OP_TRANS_PONG, OP_MEM_READ_RESP, OP_MEM_WRITE_RESP,
    OP_MEM_ATOMIC_RESP, OP_SNOOP_RESP, OP_UMS_SYN_ACK, OP_UMS_ACK,
    OP_URPC_RETURN, OP_UMQ_ACK
)

RESPONSE_OPCODES = {
    OP_RESP_OK, OP_RESP_ERR,
    OP_LINK_TRAIN_ACK, OP_TRANS_PONG,
    OP_MEM_READ_RESP, OP_MEM_WRITE_RESP, OP_MEM_ATOMIC_RESP,
    OP_SNOOP_RESP,
    OP_URMA_READ_RESP, OP_URMA_ATOMIC_RESP,
    OP_CDMA_COMPLETE,
    OP_UMS_SYN_ACK, OP_UMS_ACK,
    OP_URPC_RETURN, OP_UMQ_ACK
}


class UBDevice:
    """
    Virtual UB device instance inside the guest (or virtual node process).
    """
    def __init__(self, node_id: int, node_type: str = "ASCEND_NPU", socket_path: str = "/tmp/ub-fabric/fabric.sock"):
        self.node_id = node_id
        self.node_type = node_type
        self.socket_path = socket_path
        self._sock: Optional[socket.socket] = None
        self._lock = threading.RLock()
        self._seq = 1
        self._pending_replies: Dict[int, Any] = {}
        self._reply_cv = threading.Condition(self._lock)
        self._rx_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Local simulated memory address space
        self.local_memory = bytearray(64 * 1024 * 1024) # 64MB buffer
        self._connect_and_register()

    def _get_seq(self) -> int:
        with self._lock:
            s = self._seq
            self._seq += 1
            return s

    def _connect_and_register(self):
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connected = False
        last_err = None
        for _ in range(20):
            try:
                self._sock.connect(self.socket_path)
                connected = True
                break
            except Exception as e:
                last_err = e
                time.sleep(0.05)

        if not connected:
            raise ConnectionError(f"Failed to connect to UnifiedBus Fabric at {self.socket_path}: {last_err}. Ensure ub-fabric-daemon is running.")

        self._running = True
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._rx_thread.start()

        # Register node with fabric
        seq = self._get_seq()
        pkt = UBPacket(
            opcode=OP_REG_NODE,
            src_node=self.node_id,
            dst_node=0,
            seq_num=seq,
            metadata={"node_type": self.node_type}
        )
        resp = self.send_sync(pkt)
        if not resp or resp.opcode != OP_RESP_OK:
            raise RuntimeError(f"Failed to register Node {self.node_id} on UB Fabric")

    def _rx_loop(self):
        buf = bytearray()
        while self._running:
            try:
                data = self._sock.recv(65536)
                if not data:
                    break
                buf.extend(data)
                
                while True:
                    pkt, consumed = UBPacket.deserialize_from_buffer(bytes(buf))
                    if pkt is None:
                        break
                    del buf[:consumed]

                    with self._lock:
                        # Only match responses intended for this node's pending requests
                        is_response = pkt.opcode in RESPONSE_OPCODES
                        if is_response and pkt.seq_num in self._pending_replies:
                            self._pending_replies[pkt.seq_num] = pkt
                            self._reply_cv.notify_all()
                        else:
                            # Handle incoming asynchronous writes / sends
                            if pkt.opcode in (OP_URMA_WRITE, OP_CDMA_SUBMIT):
                                offset = pkt.metadata.get("offset", 0)
                                if offset + len(pkt.payload) <= len(self.local_memory):
                                    self.local_memory[offset:offset+len(pkt.payload)] = pkt.payload
            except Exception:
                break

    def send_sync(self, pkt: UBPacket, timeout: float = 5.0) -> Optional[UBPacket]:
        with self._lock:
            self._pending_replies[pkt.seq_num] = None
            try:
                self._sock.sendall(pkt.serialize())
            except Exception as e:
                del self._pending_replies[pkt.seq_num]
                raise e

            start_t = time.time()
            while self._pending_replies.get(pkt.seq_num) is None:
                rem = timeout - (time.time() - start_t)
                if rem <= 0:
                    del self._pending_replies[pkt.seq_num]
                    raise TimeoutError(f"Timeout waiting for UB response (seq={pkt.seq_num}, op=0x{pkt.opcode:02X})")
                self._reply_cv.wait(timeout=rem)

            resp = self._pending_replies.pop(pkt.seq_num, None)
            return resp

    def close(self):
        self._running = False
        if self._sock:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
                self._sock.close()
            except Exception:
                pass
        if self._rx_thread and self._rx_thread.is_alive():
            self._rx_thread.join(timeout=1.0)
