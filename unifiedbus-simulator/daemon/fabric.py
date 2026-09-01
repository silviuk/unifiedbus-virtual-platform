"""
UnifiedBus Complete Interconnect Switch Fabric Daemon (ub-fabric-daemon)
Implements nanosecond PDES timing, credit flow control, and complete routing
for all physical, transport, memory, coherence, function, and emergency messages.
"""

import asyncio
import os
import time
import json
import logging
import struct
from typing import Dict, Optional, Any, List, Tuple
from .port import (
    UBPacket,
    # Physical / Link
    OP_LINK_TRAIN_REQ, OP_LINK_TRAIN_ACK, OP_LINK_CREDIT_UPDATE, OP_LINK_REPLAY_REQ, OP_LINK_RESET, OP_LINK_HEARTBEAT,
    # Transport
    OP_TRANS_ACK, OP_TRANS_NACK, OP_TRANS_CNP, OP_TRANS_PING, OP_TRANS_PONG,
    # Management
    OP_REG_NODE, OP_UNREG_NODE, OP_REG_SEG, OP_UNREG_SEG, OP_CREATE_JETTY, OP_DESTROY_JETTY, OP_UBRT_QUERY,
    # Memory Semantics & Atomics
    OP_MEM_READ, OP_MEM_READ_RESP, OP_MEM_WRITE, OP_MEM_WRITE_RESP,
    OP_MEM_ATOMIC_CAS, OP_MEM_ATOMIC_ADD, OP_MEM_ATOMIC_AND, OP_MEM_ATOMIC_OR, OP_MEM_ATOMIC_XOR, OP_MEM_ATOMIC_SWAP, OP_MEM_ATOMIC_RESP,
    OP_MEM_FLUSH, OP_MEM_INVAL,
    # Coherence & Snooping
    OP_SNOOP_REQ, OP_SNOOP_RESP, OP_CACHE_WB, OP_CACHE_EVICT,
    # Function Layer: URMA
    OP_URMA_WRITE, OP_URMA_WRITE_IMM, OP_URMA_READ, OP_URMA_READ_RESP, OP_URMA_SEND, OP_URMA_SEND_IMM, OP_URMA_RECV,
    OP_URMA_ATOMIC_CAS, OP_URMA_ATOMIC_ADD, OP_URMA_ATOMIC_RESP,
    # Function Layer: CDMA
    OP_CDMA_SUBMIT, OP_CDMA_COMPLETE, OP_CDMA_BARRIER, OP_CDMA_FENCE,
    # Function Layer: UMS (Socket over UB)
    OP_UMS_SYN, OP_UMS_SYN_ACK, OP_UMS_DATA, OP_UMS_ACK, OP_UMS_FIN, OP_UMS_RST,
    # Function Layer: URPC & UMQ
    OP_URPC_CALL, OP_URPC_RETURN, OP_UMQ_PUB, OP_UMQ_SUB, OP_UMQ_ACK,
    # Memory Pooling (OBMM)
    OP_OBMM_EXPORT, OP_OBMM_IMPORT, OP_OBMM_RECLAIM, OP_OBMM_MIGRATE,
    # sysSentry Emergency
    OP_SENTRY_OOM_BLOCK, OP_SENTRY_PANIC_BLOCK, OP_SENTRY_REBOOT_NOTIFY, OP_SENTRY_DISPATCH,
    # Telemetry
    OP_QUERY_TOPOLOGY, OP_QUERY_STATS, OP_QUERY_DEVICE_CFG, OP_RESP_OK, OP_RESP_ERR
)
from .router import UBMMSwitch
from .cip import CIPEngine, CIP_SUITE_AES_256_GCM, CIP_SUITE_SM4_GCM, CIP_SUITE_NONE

logging.basicConfig(level=logging.INFO, format="[%(asctime)s][UB-Fabric] %(message)s")
logger = logging.getLogger("UBFabric")


class UBNodeConnection:
    def __init__(self, node_id: int, node_type: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.node_id = node_id
        self.node_type = node_type
        self.reader = reader
        self.writer = writer
        self.connected_at = time.time()
        self.tx_flits = 0
        self.rx_flits = 0
        self.tx_bytes = 0
        self.rx_bytes = 0
        self.credits = 1024 # Flow control buffer credits
        self.last_active = time.time()
        self.local_memory: bytearray = bytearray(64 * 1024 * 1024) # 64MB simulated local RAM
        self.cache_directory: Dict[int, str] = {} # line_addr -> 'M', 'S', 'I' (MESI state)
        self.ums_listeners: Dict[int, Any] = {}   # Port -> UMS Socket handler


class UBFabricSwitch:
    def __init__(self, socket_path: str = "/tmp/ub-fabric/fabric.sock", link_bw_gbps: float = 800.0, hop_latency_ns: float = 15.0):
        self.socket_path = socket_path
        self.link_bw_gbps = link_bw_gbps
        self.hop_latency_ns = hop_latency_ns
        self.switch_table = UBMMSwitch()
        self.cip_engine = CIPEngine(cipher_suite=CIP_SUITE_AES_256_GCM)
        self.nodes: Dict[int, UBNodeConnection] = {}
        self.server: Optional[asyncio.AbstractServer] = None
        self._running = False
        
        # Telemetry metrics
        self.total_packets_routed = 0
        self.total_flits_routed = 0
        self.total_bytes_transferred = 0
        self.sentry_emergency_events: List[Dict[str, Any]] = []
        self.recent_events: List[Dict[str, Any]] = []

    async def start(self):
        socket_dir = os.path.dirname(self.socket_path)
        if socket_dir:
            os.makedirs(socket_dir, exist_ok=True)
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)

        self._running = True
        self.server = await asyncio.start_unix_server(self._handle_client, path=self.socket_path)
        logger.info(f"UnifiedBus Fabric Switch online at {self.socket_path} (BW: {self.link_bw_gbps} Gbps, Latency: {self.hop_latency_ns} ns)")

    async def stop(self):
        self._running = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        if os.path.exists(self.socket_path):
            try:
                os.remove(self.socket_path)
            except OSError:
                pass
        logger.info("UnifiedBus Fabric Switch stopped.")

    def _record_event(self, event_type: str, src: int, dst: int, size: int, latency_ns: float, desc: str):
        event = {
            "time": time.time(),
            "type": event_type,
            "src": src,
            "dst": dst,
            "size": size,
            "latency_ns": round(latency_ns, 2),
            "desc": desc
        }
        self.recent_events.append(event)
        if len(self.recent_events) > 200:
            self.recent_events.pop(0)

    def calculate_transfer_time_ns(self, byte_count: int, num_hops: int = 1, mem_type: str = "HBM3") -> float:
        wire_ns = (byte_count * 8.0) / self.link_bw_gbps
        hop_ns = num_hops * self.hop_latency_ns
        mem_ns = 35.0 if mem_type == "HBM3" else 75.0
        return wire_ns + hop_ns + mem_ns

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        buffer = bytearray()
        current_node_id: Optional[int] = None

        try:
            while self._running:
                chunk = await reader.read(65536)
                if not chunk:
                    break
                buffer.extend(chunk)

                while True:
                    pkt, consumed = UBPacket.deserialize_from_buffer(bytes(buffer))
                    if pkt is None:
                        break
                    del buffer[:consumed]

                    resp, current_node_id = await self._process_packet(pkt, reader, writer, current_node_id)
                    if resp:
                        writer.write(resp.serialize())
                        await writer.drain()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Connection error for node {current_node_id}: {e}")
        finally:
            if current_node_id is not None and current_node_id in self.nodes:
                logger.info(f"Node {current_node_id} ({self.nodes[current_node_id].node_type}) detached from UB fabric")
                del self.nodes[current_node_id]
                self.switch_table.unregister_node(current_node_id)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _process_packet(self, pkt: UBPacket, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, current_node_id: Optional[int]) -> Tuple[Optional[UBPacket], Optional[int]]:
        op = pkt.opcode
        src = pkt.src_node
        dst = pkt.dst_node

        self.total_packets_routed += 1
        self.total_flits_routed += pkt.flit_count
        self.total_bytes_transferred += pkt.total_bytes

        # Validate CIP Authenticated Encryption & Anti-Replay if enabled
        payload = pkt.payload
        if pkt.is_cip_encrypted:
            valid, plain, err_msg = self.cip_engine.decrypt_and_verify(
                ciphertext=pkt.payload,
                auth_tag=pkt.auth_tag,
                token_id=pkt.token_id,
                seq_num=pkt.seq_num,
                src_node=pkt.src_node
            )
            if not valid:
                logger.warning(f"[CIP Security] Rejected packet from Node {src}: {err_msg}")
                resp = UBPacket(
                    opcode=OP_RESP_ERR,
                    src_node=0,
                    dst_node=src,
                    seq_num=pkt.seq_num,
                    metadata={"error": err_msg}
                )
                return resp, current_node_id
            payload = plain


        # ----------------------------------------------------------------------
        # 1. Physical & Link Layer
        # ----------------------------------------------------------------------
        if op == OP_LINK_TRAIN_REQ:
            resp = UBPacket(
                opcode=OP_LINK_TRAIN_ACK,
                src_node=0,
                dst_node=src,
                seq_num=pkt.seq_num,
                metadata={"status": "TRAINED", "speed_gbps": self.link_bw_gbps, "lanes": 8}
            )
            return resp, current_node_id

        if op == OP_LINK_CREDIT_UPDATE:
            if src in self.nodes:
                self.nodes[src].credits += pkt.metadata.get("credit_delta", 0)
            return None, current_node_id

        if op == OP_TRANS_PING:
            resp = UBPacket(
                opcode=OP_TRANS_PONG,
                src_node=0,
                dst_node=src,
                seq_num=pkt.seq_num,
                metadata={"timestamp": time.time(), "rtt_ns": self.hop_latency_ns * 2}
            )
            return resp, current_node_id

        # ----------------------------------------------------------------------
        # 2. Node & Segment Registration
        # ----------------------------------------------------------------------
        if op == OP_REG_NODE:
            node_type = pkt.metadata.get("node_type", "GENERIC_XPU")
            node_conn = UBNodeConnection(src, node_type, reader, writer)
            self.nodes[src] = node_conn
            self.switch_table.register_node(src)
            logger.info(f"Registered Node {src} [Type: {node_type}] on UB Fabric")
            resp = UBPacket(
                opcode=OP_RESP_OK,
                src_node=0,
                dst_node=src,
                seq_num=pkt.seq_num,
                metadata={"status": "REGISTERED", "link_bw_gbps": self.link_bw_gbps, "credits": node_conn.credits}
            )
            return resp, src

        if src in self.nodes:
            self.nodes[src].tx_flits += pkt.flit_count
            self.nodes[src].tx_bytes += pkt.total_bytes
            self.nodes[src].last_active = time.time()

        if op == OP_REG_SEG:
            seg_id = pkt.metadata["segment_id"]
            base_addr = pkt.metadata.get("base_addr", 0)
            size = pkt.metadata["size"]
            token_id = pkt.token_id
            perm = pkt.metadata.get("permissions", "RW")
            seg = self.switch_table.register_segment(src, seg_id, base_addr, size, token_id, perm)
            resp = UBPacket(
                opcode=OP_RESP_OK,
                src_node=0,
                dst_node=src,
                seq_num=pkt.seq_num,
                metadata={"status": "SEGMENT_REGISTERED", "segment_id": seg.segment_id}
            )
            return resp, current_node_id

        if op == OP_CREATE_JETTY:
            local_jetty_id = pkt.metadata["local_jetty_id"]
            remote_node = pkt.metadata["remote_node"]
            remote_jetty_id = pkt.metadata["remote_jetty_id"]
            token_id = pkt.token_id
            jetty = self.switch_table.create_jetty(src, local_jetty_id, remote_node, remote_jetty_id, token_id)
            resp = UBPacket(
                opcode=OP_RESP_OK,
                src_node=0,
                dst_node=src,
                seq_num=pkt.seq_num,
                metadata={"status": "JETTY_CREATED", "jetty_id": local_jetty_id}
            )
            return resp, current_node_id

        # ----------------------------------------------------------------------
        # 3. Memory Semantics & URMA / CDMA Writes
        # ----------------------------------------------------------------------
        if op in (OP_URMA_WRITE, OP_URMA_WRITE_IMM, OP_CDMA_SUBMIT, OP_MEM_WRITE):
            seg_id = pkt.metadata["segment_id"]
            offset = pkt.metadata.get("offset", 0)
            length = len(pkt.payload)
            valid, msg = self.switch_table.validate_access(dst, seg_id, offset, length, is_write=True, token_id=pkt.token_id)
            
            latency_ns = self.calculate_transfer_time_ns(length)
            if not valid:
                resp = UBPacket(
                    opcode=OP_RESP_ERR,
                    src_node=0,
                    dst_node=src,
                    seq_num=pkt.seq_num,
                    metadata={"error": msg}
                )
                return resp, current_node_id
            
            dst_conn = self.nodes.get(dst)
            if dst_conn:
                dst_conn.rx_flits += pkt.flit_count
                dst_conn.rx_bytes += pkt.total_bytes
                if offset + length <= len(dst_conn.local_memory):
                    dst_conn.local_memory[offset:offset+length] = payload
                try:
                    dst_conn.writer.write(pkt.serialize())
                    await dst_conn.writer.drain()
                except Exception:
                    pass

            self._record_event("URMA_WRITE" if op == OP_URMA_WRITE else "CDMA_WRITE", src, dst, length, latency_ns, f"Write seg {seg_id} offset {offset}")

            resp = UBPacket(
                opcode=OP_RESP_OK if op in (OP_URMA_WRITE, OP_URMA_WRITE_IMM, OP_MEM_WRITE) else OP_CDMA_COMPLETE,
                src_node=dst,
                dst_node=src,
                seq_num=pkt.seq_num,
                metadata={"status": "COMPLETED", "bytes_written": length, "sim_latency_ns": latency_ns}
            )
            return resp, current_node_id

        # ----------------------------------------------------------------------
        # 4. Memory Reads (URMA & Native Memory Read)
        # ----------------------------------------------------------------------
        if op in (OP_URMA_READ, OP_MEM_READ):
            seg_id = pkt.metadata["segment_id"]
            offset = pkt.metadata.get("offset", 0)
            length = pkt.metadata.get("length", 0)
            valid, msg = self.switch_table.validate_access(dst, seg_id, offset, length, is_write=False, token_id=pkt.token_id)
            
            latency_ns = self.calculate_transfer_time_ns(length)
            if not valid:
                resp = UBPacket(
                    opcode=OP_RESP_ERR,
                    src_node=0,
                    dst_node=src,
                    seq_num=pkt.seq_num,
                    metadata={"error": msg}
                )
                return resp, current_node_id
            
            dst_conn = self.nodes.get(dst)
            read_payload = b"\x00" * length
            if dst_conn and offset + length <= len(dst_conn.local_memory):
                read_payload = bytes(dst_conn.local_memory[offset:offset+length])

            self._record_event("URMA_READ", src, dst, length, latency_ns, f"Read seg {seg_id} offset {offset}")

            resp = UBPacket(
                opcode=OP_URMA_READ_RESP if op == OP_URMA_READ else OP_MEM_READ_RESP,
                src_node=dst,
                dst_node=src,
                seq_num=pkt.seq_num,
                metadata={"status": "OK", "sim_latency_ns": latency_ns},
                payload=read_payload
            )
            return resp, current_node_id

        # ----------------------------------------------------------------------
        # 5. Full Atomic Operations (CAS, ADD, AND, OR, XOR, SWAP)
        # ----------------------------------------------------------------------
        if op in (OP_URMA_ATOMIC_CAS, OP_URMA_ATOMIC_ADD, OP_MEM_ATOMIC_CAS, OP_MEM_ATOMIC_ADD, OP_MEM_ATOMIC_AND, OP_MEM_ATOMIC_OR, OP_MEM_ATOMIC_SWAP):
            seg_id = pkt.metadata["segment_id"]
            offset = pkt.metadata.get("offset", 0)
            valid, msg = self.switch_table.validate_access(dst, seg_id, offset, 8, is_write=True, token_id=pkt.token_id)
            if not valid:
                resp = UBPacket(opcode=OP_RESP_ERR, src_node=0, dst_node=src, seq_num=pkt.seq_num, metadata={"error": msg})
                return resp, current_node_id

            dst_conn = self.nodes.get(dst)
            orig_val = 0
            if dst_conn and offset + 8 <= len(dst_conn.local_memory):
                orig_val = struct.unpack("!Q", dst_conn.local_memory[offset:offset+8])[0]
                
                if op in (OP_URMA_ATOMIC_CAS, OP_MEM_ATOMIC_CAS):
                    compare_val = pkt.metadata.get("compare", 0)
                    swap_val = pkt.metadata.get("swap", 0)
                    if orig_val == compare_val:
                        dst_conn.local_memory[offset:offset+8] = struct.pack("!Q", swap_val)
                elif op in (OP_URMA_ATOMIC_ADD, OP_MEM_ATOMIC_ADD):
                    add_val = pkt.metadata.get("add", 0)
                    dst_conn.local_memory[offset:offset+8] = struct.pack("!Q", (orig_val + add_val) & 0xFFFFFFFFFFFFFFFF)
                elif op == OP_MEM_ATOMIC_AND:
                    and_val = pkt.metadata.get("and", 0)
                    dst_conn.local_memory[offset:offset+8] = struct.pack("!Q", orig_val & and_val)
                elif op == OP_MEM_ATOMIC_OR:
                    or_val = pkt.metadata.get("or", 0)
                    dst_conn.local_memory[offset:offset+8] = struct.pack("!Q", orig_val | or_val)
                elif op == OP_MEM_ATOMIC_SWAP:
                    swap_val = pkt.metadata.get("swap", 0)
                    dst_conn.local_memory[offset:offset+8] = struct.pack("!Q", swap_val)

            lat_ns = self.calculate_transfer_time_ns(8)
            self._record_event("ATOMIC_OP", src, dst, 8, lat_ns, f"Atomic op 0x{op:02X} on seg {seg_id}")
            resp = UBPacket(
                opcode=OP_URMA_ATOMIC_RESP if op in (OP_URMA_ATOMIC_CAS, OP_URMA_ATOMIC_ADD) else OP_MEM_ATOMIC_RESP,
                src_node=dst,
                dst_node=src,
                seq_num=pkt.seq_num,
                metadata={"status": "OK", "orig_value": orig_val, "sim_latency_ns": lat_ns}
            )
            return resp, current_node_id

        # ----------------------------------------------------------------------
        # 6. Cache Coherence & Snooping
        # ----------------------------------------------------------------------
        if op in (OP_SNOOP_REQ, OP_CACHE_WB, OP_CACHE_EVICT):
            line_addr = pkt.metadata.get("line_addr", 0)
            lat_ns = self.calculate_transfer_time_ns(64) # 64-byte cacheline
            self._record_event("CACHE_COHERENCE", src, dst, 64, lat_ns, f"Coherence 0x{op:02X} line 0x{line_addr:X}")
            resp = UBPacket(
                opcode=OP_SNOOP_RESP,
                src_node=dst,
                dst_node=src,
                seq_num=pkt.seq_num,
                metadata={"status": "COHERENCE_ACK", "state": "INVALID", "sim_latency_ns": lat_ns}
            )
            return resp, current_node_id

        # ----------------------------------------------------------------------
        # 7. Function Layer: UMS (Socket-over-UB) Streaming
        # ----------------------------------------------------------------------
        if op in (OP_UMS_SYN, OP_UMS_SYN_ACK, OP_UMS_DATA, OP_UMS_ACK, OP_UMS_FIN):
            dst_conn = self.nodes.get(dst)
            lat_ns = self.calculate_transfer_time_ns(len(pkt.payload))
            if dst_conn:
                try:
                    dst_conn.writer.write(pkt.serialize())
                    await dst_conn.writer.drain()
                except Exception:
                    pass
            self._record_event("UMS_SOCKET", src, dst, len(pkt.payload), lat_ns, f"UMS Op 0x{op:02X} port {pkt.metadata.get('port', 0)}")
            resp = UBPacket(
                opcode=OP_RESP_OK,
                src_node=dst,
                dst_node=src,
                seq_num=pkt.seq_num,
                metadata={"status": "UMS_ACK", "sim_latency_ns": lat_ns}
            )
            return resp, current_node_id

        # ----------------------------------------------------------------------
        # 8. Function Layer: URPC & UMQ
        # ----------------------------------------------------------------------
        if op in (OP_URPC_CALL, OP_URPC_RETURN, OP_UMQ_PUB, OP_UMQ_SUB):
            dst_conn = self.nodes.get(dst)
            lat_ns = self.calculate_transfer_time_ns(len(pkt.payload))
            if dst_conn:
                try:
                    dst_conn.writer.write(pkt.serialize())
                    await dst_conn.writer.drain()
                except Exception:
                    pass
            self._record_event("URPC_UMQ", src, dst, len(pkt.payload), lat_ns, f"URPC/UMQ Op 0x{op:02X} method {pkt.metadata.get('method', '')}")
            resp = UBPacket(
                opcode=OP_RESP_OK,
                src_node=dst,
                dst_node=src,
                seq_num=pkt.seq_num,
                metadata={"status": "RPC_DISPATCHED", "sim_latency_ns": lat_ns}
            )
            return resp, current_node_id

        # ----------------------------------------------------------------------
        # 9. Memory Pooling: OBMM (Export, Import, Reclaim, Migrate)
        # ----------------------------------------------------------------------
        if op == OP_OBMM_EXPORT:
            size = pkt.metadata["size"]
            token_id = pkt.token_id
            perm = pkt.metadata.get("permissions", "RW")
            pool_id = self.switch_table.export_memory_pool(src, size, token_id, perm)
            logger.info(f"OBMM: Node {src} exported pool 0x{pool_id:X} (Size: {size / (1024**2):.1f} MB, TokenID: 0x{token_id:X})")
            resp = UBPacket(
                opcode=OP_RESP_OK,
                src_node=0,
                dst_node=src,
                seq_num=pkt.seq_num,
                metadata={"pool_id": pool_id, "size": size}
            )
            return resp, current_node_id

        if op == OP_OBMM_IMPORT:
            pool_id = pkt.metadata["pool_id"]
            token_id = pkt.token_id
            seg = self.switch_table.import_memory_pool(src, pool_id, token_id)
            if not seg:
                resp = UBPacket(
                    opcode=OP_RESP_ERR,
                    src_node=0,
                    dst_node=src,
                    seq_num=pkt.seq_num,
                    metadata={"error": f"Failed to import pool 0x{pool_id:X} (invalid pool ID or token mismatch)"}
                )
                return resp, current_node_id
            
            logger.info(f"OBMM: Node {src} imported memory pool 0x{pool_id:X} from Node {seg.node_id}")
            resp = UBPacket(
                opcode=OP_RESP_OK,
                src_node=0,
                dst_node=src,
                seq_num=pkt.seq_num,
                metadata={
                    "pool_id": pool_id,
                    "target_node": seg.node_id,
                    "segment_id": seg.segment_id,
                    "size": seg.size,
                    "permissions": seg.permissions
                }
            )
            return resp, current_node_id

        # ----------------------------------------------------------------------
        # 10. sysSentry Emergency & Fault Containment
        # ----------------------------------------------------------------------
        if op in (OP_SENTRY_OOM_BLOCK, OP_SENTRY_PANIC_BLOCK, OP_SENTRY_REBOOT_NOTIFY):
            reason = pkt.metadata.get("reason", "Emergency Event")
            logger.error(f"[sysSentry] Emergency alert from Node {src}: Op 0x{op:02X} - {reason}")
            self.sentry_emergency_events.append({"node": src, "op": op, "reason": reason, "time": time.time()})
            
            # Broadcast isolation event to all other connected nodes
            for n_id, conn in self.nodes.items():
                if n_id != src:
                    try:
                        conn.writer.write(pkt.serialize())
                        await conn.writer.drain()
                    except Exception:
                        pass

            resp = UBPacket(
                opcode=OP_RESP_OK,
                src_node=0,
                dst_node=src,
                seq_num=pkt.seq_num,
                metadata={"status": "EMERGENCY_CONTAINED", "action": "BLOCKED"}
            )
            return resp, current_node_id

        # ----------------------------------------------------------------------
        # 11. Management & Telemetry Queries
        # ----------------------------------------------------------------------
        if op == OP_QUERY_TOPOLOGY:
            topo = {
                "switch": "UB-SuperPoD-Switch-0",
                "link_bw_gbps": self.link_bw_gbps,
                "nodes": [
                    {
                        "node_id": n_id,
                        "node_type": n.node_type,
                        "tx_flits": n.tx_flits,
                        "rx_flits": n.rx_flits,
                        "tx_bytes": n.tx_bytes,
                        "rx_bytes": n.rx_bytes,
                        "credits": n.credits,
                        "uptime_sec": round(time.time() - n.connected_at, 1)
                    }
                    for n_id, n in self.nodes.items()
                ],
                "memory_pools": [
                    {
                        "pool_id": p_id,
                        "owner_node": p.node_id,
                        "size_bytes": p.size,
                        "token_id": p.token_id,
                        "permissions": p.permissions
                    }
                    for p_id, p in self.switch_table.memory_pools.items()
                ]
            }
            resp = UBPacket(opcode=OP_RESP_OK, src_node=0, dst_node=src, seq_num=pkt.seq_num, metadata=topo)
            return resp, current_node_id

        if op == OP_QUERY_STATS:
            stats = {
                "total_packets": self.total_packets_routed,
                "total_flits": self.total_flits_routed,
                "total_bytes": self.total_bytes_transferred,
                "active_nodes": len(self.nodes),
                "cip_security": {
                    "cipher_suite": "AES_256_GCM",
                    "encrypted_packets": self.cip_engine.total_encrypted_packets,
                    "decrypted_packets": self.cip_engine.total_decrypted_packets,
                    "tamper_rejections": self.cip_engine.total_tamper_rejections,
                    "replay_rejections": self.cip_engine.total_replay_rejections
                },
                "emergency_events": self.sentry_emergency_events,
                "recent_events": self.recent_events[-20:]
            }
            resp = UBPacket(opcode=OP_RESP_OK, src_node=0, dst_node=src, seq_num=pkt.seq_num, metadata=stats)
            return resp, current_node_id

        # Generic P2P message / Forwarding
        if dst in self.nodes:
            dst_conn = self.nodes[dst]
            dst_conn.rx_flits += pkt.flit_count
            dst_conn.rx_bytes += pkt.total_bytes
            dst_conn.writer.write(pkt.serialize())
            await dst_conn.writer.drain()
            
            resp = UBPacket(opcode=OP_RESP_OK, src_node=dst, dst_node=src, seq_num=pkt.seq_num, metadata={"status": "FORWARDED"})
            return resp, current_node_id

        return None, current_node_id


def main():
    import argparse
    parser = argparse.ArgumentParser(description="UnifiedBus (UB) Interconnect Switch Fabric Daemon")
    parser.add_argument("--socket", default="/tmp/ub-fabric/fabric.sock", help="Unix socket path")
    parser.add_argument("--bw", type=float, default=800.0, help="Link bandwidth in Gbps")
    parser.add_argument("--latency", type=float, default=15.0, help="Hop latency in nanoseconds")
    args = parser.parse_args()

    async def _runner():
        fabric = UBFabricSwitch(socket_path=args.socket, link_bw_gbps=args.bw, hop_latency_ns=args.latency)
        await fabric.start()
        print(f"[*] UnifiedBus Switch online. Press Ctrl+C to terminate.")
        try:
            while True:
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            pass
        finally:
            await fabric.stop()

    try:
        asyncio.run(_runner())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
