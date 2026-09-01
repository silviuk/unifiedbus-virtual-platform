"""
UnifiedBus Complete Protocol Message Specification & Opcode Definitions
With full CIP (Confidentiality and Integrity Protection) header and flag support.
"""

import json
import struct
import zlib
from typing import Optional, Dict, Any, Tuple

# ==============================================================================
# Protocol Flags
# ==============================================================================
FLAG_NONE              = 0x00
FLAG_CIP_ENCRYPTED     = 0x80  # CIP Authenticated Encryption active
FLAG_URGENT            = 0x40  # Priority Virtual Lane
FLAG_COMPRESSED        = 0x20  # Flit compression active

# ==============================================================================
# 1. Physical & Link Layer Control Messages (0x01 - 0x0F)
# ==============================================================================
OP_LINK_TRAIN_REQ      = 0x01  # Link Training State Machine (LTSSM) handshake
OP_LINK_TRAIN_ACK      = 0x02  # Link speed/width negotiation acknowledgement
OP_LINK_CREDIT_UPDATE  = 0x03  # Link-layer flow control buffer credit update
OP_LINK_REPLAY_REQ     = 0x04  # Link replay buffer retransmission request on CRC fail
OP_LINK_RESET          = 0x05  # Physical lane reset / retrain signal
OP_LINK_HEARTBEAT      = 0x06  # Link keepalive and signal integrity probe

# ==============================================================================
# 2. Transport & Congestion Control Messages (0x10 - 0x1F)
# ==============================================================================
OP_TRANS_ACK           = 0x10  # End-to-end transport acknowledgment
OP_TRANS_NACK          = 0x11  # Negative acknowledgment (packet drop/corrupt)
OP_TRANS_CNP           = 0x12  # Congestion Notification Packet (ECN marking trigger)
OP_TRANS_PING          = 0x13  # End-to-end fabric RTT probe
OP_TRANS_PONG          = 0x14  # End-to-end fabric RTT response

# ==============================================================================
# 3. Device & Resource Management (0x20 - 0x2F)
# ==============================================================================
OP_REG_NODE            = 0x20  # Node attachment and capabilities registration
OP_UNREG_NODE          = 0x21  # Node graceful detachment
OP_REG_SEG             = 0x22  # Memory Segment registration (base, size, TokenID)
OP_UNREG_SEG           = 0x23  # Memory Segment deregistration
OP_CREATE_JETTY        = 0x24  # Create Jetty connection pair
OP_DESTROY_JETTY       = 0x25  # Teardown Jetty connection
OP_UBRT_QUERY          = 0x26  # BIOS UB Root Table query

# ==============================================================================
# 4. Memory Semantic & Atomic Transactions (0x30 - 0x4F)
# ==============================================================================
OP_MEM_READ            = 0x30  # Low-level memory read request
OP_MEM_READ_RESP       = 0x31  # Low-level memory read response
OP_MEM_WRITE           = 0x32  # Low-level memory posted write
OP_MEM_WRITE_RESP      = 0x33  # Memory write acknowledgment
OP_MEM_ATOMIC_CAS      = 0x34  # Atomic Compare-and-Swap
OP_MEM_ATOMIC_ADD      = 0x35  # Atomic Fetch-and-Add
OP_MEM_ATOMIC_AND      = 0x36  # Atomic Bitwise AND
OP_MEM_ATOMIC_OR       = 0x37  # Atomic Bitwise OR
OP_MEM_ATOMIC_XOR      = 0x38  # Atomic Bitwise XOR
OP_MEM_ATOMIC_SWAP     = 0x39  # Atomic Swap
OP_MEM_ATOMIC_RESP     = 0x3A  # Atomic completion response
OP_MEM_FLUSH           = 0x3B  # Cache line / memory controller flush
OP_MEM_INVAL           = 0x3C  # UMMU TLB & cache invalidation

# ==============================================================================
# 5. Cache Coherence & Directory Snooping (0x50 - 0x5F)
# ==============================================================================
OP_SNOOP_REQ           = 0x50  # Directory snoop request (Invalidate, Shared, Exclusive)
OP_SNOOP_RESP          = 0x51  # Snoop response (Clean, Dirty, Hit, Miss)
OP_CACHE_WB            = 0x52  # Cache line writeback to pooled home agent
OP_CACHE_EVICT         = 0x53  # Cache eviction notification

# ==============================================================================
# 6. Function Layer: URMA (Unified Remote Memory Access) (0x60 - 0x6F)
# ==============================================================================
OP_URMA_WRITE          = 0x60  # URMA RDMA Write
OP_URMA_WRITE_IMM      = 0x61  # URMA RDMA Write with Immediate Data
OP_URMA_READ           = 0x62  # URMA RDMA Read
OP_URMA_READ_RESP      = 0x63  # URMA RDMA Read Response
OP_URMA_SEND           = 0x64  # URMA Message Send
OP_URMA_SEND_IMM       = 0x65  # URMA Message Send with Immediate Data
OP_URMA_RECV           = 0x66  # URMA Receive Post / Match
OP_URMA_ATOMIC_CAS     = 0x67  # URMA CAS
OP_URMA_ATOMIC_ADD     = 0x68  # URMA Add
OP_URMA_ATOMIC_RESP    = 0x69  # URMA Atomic Response

# ==============================================================================
# 7. Function Layer: CDMA (Crystal Direct Memory Access) (0x70 - 0x7F)
# ==============================================================================
OP_CDMA_SUBMIT         = 0x70  # Asynchronous DMA descriptor submission
OP_CDMA_COMPLETE       = 0x71  # Hardware DMA completion interrupt/event
OP_CDMA_BARRIER        = 0x72  # DMA execution barrier
OP_CDMA_FENCE          = 0x73  # DMA memory ordering fence

# ==============================================================================
# 8. Function Layer: UMS (Socket over UB) (0x80 - 0x8F)
# ==============================================================================
OP_UMS_SYN             = 0x80  # UMS Connection handshake SYN
OP_UMS_SYN_ACK         = 0x81  # UMS Connection handshake SYN-ACK
OP_UMS_DATA            = 0x82  # UMS Byte-stream data frame
OP_UMS_ACK             = 0x83  # UMS Window flow control ACK
OP_UMS_FIN             = 0x84  # UMS Connection teardown FIN
OP_UMS_RST             = 0x85  # UMS Connection reset

# ==============================================================================
# 9. Function Layer: URPC & UMQ (0x90 - 0x9F)
# ==============================================================================
OP_URPC_CALL           = 0x90  # Remote Procedure Call invocation
OP_URPC_RETURN         = 0x91  # Remote Procedure Call return result
OP_UMQ_PUB             = 0x92  # Message Queue Publish
OP_UMQ_SUB             = 0x93  # Message Queue Subscribe
OP_UMQ_ACK             = 0x94  # Message Queue Delivery Acknowledgment

# ==============================================================================
# 10. Memory Pooling: OBMM / UBs Mem (0xA0 - 0xAF)
# ==============================================================================
OP_OBMM_EXPORT         = 0xA0  # Export memory pool with TokenID capability
OP_OBMM_IMPORT         = 0xA1  # Import memory pool into local address window
OP_OBMM_RECLAIM        = 0xA2  # Reclaim / revoke loaned memory
OP_OBMM_MIGRATE        = 0xA3  # Hot/Cold data page migration (HAM/UB Turbo)

# ==============================================================================
# 11. sysSentry Emergency & Fault Containment (0xB0 - 0xBF)
# ==============================================================================
OP_SENTRY_OOM_BLOCK    = 0xB0  # OOM emergency freeze and notify
OP_SENTRY_PANIC_BLOCK  = 0xB1  # Kernel panic isolation and telemetry dump
OP_SENTRY_REBOOT_NOTIFY= 0xB2  # Clean shutdown/reboot coordination
OP_SENTRY_DISPATCH     = 0xB3  # UBPRM emergency event dispatch

# ==============================================================================
# 12. Management, Telemetry & Generic Responses (0xC0 - 0xFF)
# ==============================================================================
OP_QUERY_TOPOLOGY      = 0xC0  # Topology discovery query (ubctl)
OP_QUERY_STATS         = 0xC1  # Performance counters query
OP_QUERY_DEVICE_CFG    = 0xC2  # Device BAR/UMMU configuration query
OP_SET_CIP_CONFIG      = 0xC3  # Configure CIP encryption parameters
OP_RESP_OK             = 0xF0  # Command succeeded
OP_RESP_ERR            = 0xF1  # Command failed with error

# Packet Framing Constants
# Header: Magic(2B) | Opcode(1B) | Flags(1B) | Seq(4B) | Src(2B) | Dst(2B) | Token(4B) | MetaLen(4B) | PayloadLen(4B) | CRC32(4B) | AuthTag(16B)
FRAME_HEADER_FMT = "!2sBBIHHIIII16s" # 44 bytes header (including 16B CIP AuthTag)
FRAME_MAGIC = b"UB"
FLIT_SIZE = 64 # 64 bytes standard flit


class UBPacket:
    def __init__(self,
                 opcode: int,
                 src_node: int,
                 dst_node: int,
                 token_id: int = 0,
                 virtual_lane: int = 0,
                 flags: int = FLAG_NONE,
                 seq_num: int = 0,
                 auth_tag: bytes = b"\x00" * 16,
                 metadata: Optional[Dict[str, Any]] = None,
                 payload: bytes = b""):
        self.opcode = opcode
        self.src_node = src_node
        self.dst_node = dst_node
        self.token_id = token_id
        self.virtual_lane = virtual_lane & 0x0F
        self.flags = flags
        self.seq_num = seq_num
        self.auth_tag = auth_tag if len(auth_tag) == 16 else (auth_tag + b"\x00"*16)[:16]
        self.metadata = metadata or {}
        self.payload = payload or b""

    @property
    def is_cip_encrypted(self) -> bool:
        return bool(self.flags & FLAG_CIP_ENCRYPTED)

    @property
    def total_bytes(self) -> int:
        return 44 + len(json.dumps(self.metadata).encode('utf-8')) + len(self.payload)

    @property
    def flit_count(self) -> int:
        size = self.total_bytes
        return (size + FLIT_SIZE - 1) // FLIT_SIZE

    def serialize(self) -> bytes:
        meta_bytes = json.dumps(self.metadata).encode('utf-8')
        meta_len = len(meta_bytes)
        payload_len = len(self.payload)
        
        # Flags combined with virtual lane in single byte: [Flags 4-bit | VL 4-bit]
        flags_vl = (self.flags & 0xF0) | (self.virtual_lane & 0x0F)
        
        crc_data = meta_bytes + self.payload
        crc = zlib.crc32(crc_data) & 0xFFFFFFFF
        
        header = struct.pack(
            FRAME_HEADER_FMT,
            FRAME_MAGIC,
            self.opcode,
            flags_vl,
            self.seq_num,
            self.src_node,
            self.dst_node,
            self.token_id,
            meta_len,
            payload_len,
            crc,
            self.auth_tag
        )
        return header + meta_bytes + self.payload

    @classmethod
    def deserialize_from_buffer(cls, buf: bytes) -> Tuple[Optional['UBPacket'], int]:
        if len(buf) < 44:
            return None, 0
        
        magic, opcode, flags_vl, seq, src, dst, token, meta_len, payload_len, crc, auth_tag = struct.unpack(
            FRAME_HEADER_FMT, buf[:44]
        )
        
        if magic != FRAME_MAGIC:
            raise ValueError(f"Invalid UnifiedBus magic: {magic}")
        
        total_len = 44 + meta_len + payload_len
        if len(buf) < total_len:
            return None, 0
        
        meta_bytes = buf[44:44 + meta_len]
        payload = buf[44 + meta_len:total_len]
        
        calc_crc = zlib.crc32(meta_bytes + payload) & 0xFFFFFFFF
        if calc_crc != crc:
            raise ValueError(f"UnifiedBus CRC error: expected 0x{crc:08X}, got 0x{calc_crc:08X}")
        
        meta = json.loads(meta_bytes.decode('utf-8')) if meta_len > 0 else {}
        flags = flags_vl & 0xF0
        vl = flags_vl & 0x0F

        pkt = cls(
            opcode=opcode,
            src_node=src,
            dst_node=dst,
            token_id=token,
            virtual_lane=vl,
            flags=flags,
            seq_num=seq,
            auth_tag=auth_tag,
            metadata=meta,
            payload=payload
        )
        return pkt, total_len
