"""
UnifiedBus Global Router & UMMU Translation Arbiter
Handles UMMU Global Physical Address (GPA) translation, TokenID capability checks,
and Jetty/Segment resource tracking across the UB SuperPoD fabric.
"""

from typing import Dict, Optional, Tuple
import threading
import time


class UBSegment:
    def __init__(self, segment_id: int, node_id: int, base_addr: int, size: int, token_id: int, permissions: str = "RW"):
        self.segment_id = segment_id
        self.node_id = node_id
        self.base_addr = base_addr
        self.size = size
        self.token_id = token_id
        self.permissions = permissions.upper()  # 'RO', 'RW', 'WO'
        self.created_at = time.time()

    def contains(self, offset: int, length: int) -> bool:
        return 0 <= offset and (offset + length) <= self.size

    def check_permission(self, is_write: bool, token_id: int) -> bool:
        if self.token_id != 0 and self.token_id != token_id:
            return False
        if is_write and "W" not in self.permissions:
            return False
        if not is_write and "R" not in self.permissions:
            return False
        return True


class UBJetty:
    def __init__(self, local_node: int, local_jetty_id: int, remote_node: int, remote_jetty_id: int, token_id: int):
        self.local_node = local_node
        self.local_jetty_id = local_jetty_id
        self.remote_node = remote_node
        self.remote_jetty_id = remote_jetty_id
        self.token_id = token_id
        self.state = "CONNECTED"  # INIT, CONNECTED, ERROR, CLOSED
        self.tx_bytes = 0
        self.rx_bytes = 0
        self.tx_packets = 0
        self.rx_packets = 0


class UBMMSwitch:
    """
    UnifiedBus UMMU & Switch Routing Engine.
    Maintains the global address map (GPA), registered segments, and active Jetties.
    """
    def __init__(self):
        self._lock = threading.RLock()
        # Node ID -> Dict[segment_id, UBSegment]
        self.segments: Dict[int, Dict[int, UBSegment]] = {}
        # (local_node, local_jetty_id) -> UBJetty
        self.jetties: Dict[Tuple[int, int], UBJetty] = {}
        # Global Memory Pools (pool_id -> UBSegment)
        self.memory_pools: Dict[int, UBSegment] = {}
        self._next_pool_id = 1

    def register_node(self, node_id: int):
        with self._lock:
            if node_id not in self.segments:
                self.segments[node_id] = {}

    def unregister_node(self, node_id: int):
        with self._lock:
            if node_id in self.segments:
                del self.segments[node_id]
            # Remove jetties involving this node
            to_del = [k for k in self.jetties if k[0] == node_id or self.jetties[k].remote_node == node_id]
            for k in to_del:
                del self.jetties[k]

    def register_segment(self, node_id: int, segment_id: int, base_addr: int, size: int, token_id: int, permissions: str = "RW") -> UBSegment:
        with self._lock:
            self.register_node(node_id)
            seg = UBSegment(segment_id, node_id, base_addr, size, token_id, permissions)
            self.segments[node_id][segment_id] = seg
            return seg

    def unregister_segment(self, node_id: int, segment_id: int):
        with self._lock:
            if node_id in self.segments and segment_id in self.segments[node_id]:
                del self.segments[node_id][segment_id]

    def create_jetty(self, local_node: int, local_jetty_id: int, remote_node: int, remote_jetty_id: int, token_id: int) -> UBJetty:
        with self._lock:
            jetty = UBJetty(local_node, local_jetty_id, remote_node, remote_jetty_id, token_id)
            self.jetties[(local_node, local_jetty_id)] = jetty
            return jetty

    def get_jetty(self, local_node: int, local_jetty_id: int) -> Optional[UBJetty]:
        with self._lock:
            return self.jetties.get((local_node, local_jetty_id))

    def export_memory_pool(self, node_id: int, size: int, token_id: int, permissions: str = "RW") -> int:
        """OBMM memory pooling export."""
        with self._lock:
            pool_id = self._next_pool_id
            self._next_pool_id += 1
            seg = self.register_segment(node_id, pool_id, 0, size, token_id, permissions)
            self.memory_pools[pool_id] = seg
            return pool_id

    def import_memory_pool(self, borrower_node: int, pool_id: int, token_id: int) -> Optional[UBSegment]:
        """OBMM memory pooling import."""
        with self._lock:
            seg = self.memory_pools.get(pool_id)
            if not seg:
                return None
            if seg.token_id != 0 and seg.token_id != token_id:
                return None  # Permission denied
            return seg

    def validate_access(self, target_node: int, segment_id: int, offset: int, length: int, is_write: bool, token_id: int) -> Tuple[bool, str]:
        with self._lock:
            node_segs = self.segments.get(target_node)
            if node_segs is None:
                return False, f"Target node {target_node} not found on UB fabric"
            
            seg = node_segs.get(segment_id)
            if seg is None:
                return False, f"Segment {segment_id} not registered on node {target_node}"
            
            if not seg.contains(offset, length):
                return False, f"Address out of bounds: offset={offset}, length={length}, segment_size={seg.size}"
            
            if not seg.check_permission(is_write, token_id):
                return False, f"Permission denied for TokenID=0x{token_id:X}, Write={is_write}, Permissions={seg.permissions}"
            
            return True, "OK"
