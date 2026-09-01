# UnifiedBus (UB / 灵衢) QEMU Co-Emulation & SuperPoD Simulator

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Protocol](https://img.shields.io/badge/UnifiedBus-Spec%202.0-brightgreen.svg)](https://unifiedbus.com)
[![openEuler](https://img.shields.io/badge/openEuler-UB%20OS%20SIG-orange.svg)](https://openeuler.org)

A high-fidelity **QEMU Co-Emulation & SuperPoD Interconnect Simulator** for developing, testing, and benchmarking distributed AI and disaggregated memory applications built on the **UnifiedBus (灵衢 / UB)** protocol as specified on [unifiedbus.com](https://unifiedbus.com).

---

## 🌟 Key Features

1. **QEMU Virtual Machine & Node Emulation**:
   - Each VM or node process represents a **UBPU** (Kunpeng ARM Host CPU, Ascend DaVinci NPU, or Pooled Memory Appliance).
   - Equips VMs with virtual UB PCI/MMIO device controllers (`ub-pci-dev`), BAR0 config registers, UMMU TLB registers, and Doorbell queues.

2. **Central UnifiedBus Switch Fabric (`ub-fabric-daemon`)**:
   - Discrete-event simulation (PDES) timing engine with nanosecond accuracy.
   - Flit framing (64-byte flits), CRC32 verification, and link credit backpressure flow control.
   - UMMU Global Physical Address (GPA) routing, Segment directory, and TokenID capability authorization.
   - Configurable link bandwidth (800 Gbps, 1.6 Tbps, 3.2 Tbps) and hop latencies.

3. **Standard openEuler-Compliant Guest SDK & APIs**:
   - **`liburma`**: Unified Remote Memory Access (Endpoints/Jetties, registered Segments, RDMA Write/Read/Atomic).
   - **`libcdma`**: Crystal Direct Memory Access (asynchronous multi-descriptor DMA batching and non-blocking wait).
   - **`libobmm` / `UBs Mem`**: Open Borrowed Memory Management (`EXPORT` and `IMPORT` memory pooling across VMs).
   - **`HCCL`**: Huawei Collective Communication Library (`AllReduce`, `AllGather`, `ReduceScatter`, `Broadcast`).
   - **`ubctl`**: In-guest management CLI for topology queries, configuration space inspection, and telemetry.

4. **Real-Time Interactive Visualizer & Telemetry Dashboard**:
   - Modern browser UI (`http://localhost:8088`) displaying live SuperPoD topology, link bandwidth heatmaps, active memory pool tables, and transaction event streams.

---

## 🚀 Quick Start

### 1. Run Automated Unit Tests
```bash
pytest tests/ -v
```

### 2. Start the UnifiedBus Fabric Daemon
```bash
python3 -m daemon.fabric --socket /tmp/ub-fabric/fabric.sock --bw 800 --latency 15
```

### 3. Launch an Example Application
In another terminal (or using the launcher):

```bash
# Example 1: URMA Peer-to-Peer RDMA between Kunpeng CPU and Ascend NPU
python3 examples/01_urma_p2p_transfer.py

# Example 2: High-throughput asynchronous DMA with CDMA
python3 examples/02_cdma_async_dma.py

# Example 3: Disaggregated memory pooling with OBMM
python3 examples/03_obmm_memory_pooling.py

# Example 4: Distributed AI Ring-AllReduce across 4 Ascend NPUs
python3 examples/04_hccl_allreduce.py --world-size 4 --size-mb 16

# Example 5: BenchLib LLM-70B Training Trace replay
python3 examples/05_benchlib_synthetic_trace.py --layers 8

# Example 6: CIP-Encrypted Memory Transfer & Active Attack Simulation
python3 examples/06_cip_encrypted_memory.py

```

### 4. Inspect Topology and Performance with `ubctl`
```bash
# Query active cluster topology
python3 -m guest_sdk.python.unifiedbus.ubctl topology

# Query fabric performance counters
python3 -m guest_sdk.python.unifiedbus.ubctl stats
```

### 5. Launch the Web Visualizer
```bash
python3 -m visualizer.dashboard --port 8088
# Open http://localhost:8088 in your web browser
```

---

## 📚 Application Developer Guide

### A. URMA RDMA Transfer Example
```python
from unifiedbus.urma import URMAContext

# Initialize local node
ctx = URMAContext(node_id=1)

# Register 64KB memory segment
token = 0xCAFE0001
seg = ctx.register_segment(64 * 1024, token_id=token, permissions="RW")

# Establish Jetty connection to target node 3
jetty = ctx.create_jetty(remote_node=3, remote_jetty_id=1, token_id=token)

# Execute RDMA Write
seg.buffer[0:5] = b"HELLO"
lat_ns = jetty.write(local_seg=seg, local_offset=0, remote_seg_id=1, remote_offset=0, length=5)
```

### B. Memory Pooling with OBMM
```python
from unifiedbus.obmm import OBMMClient

# Node 7 exports 16 GB memory pool
exporter = OBMMClient(node_id=7)
pool_id = exporter.export_memory(size_bytes=16 * 1024**3, token_id=0xABCD)

# Node 1 imports the memory pool
borrower = OBMMClient(node_id=1)
pool = borrower.import_memory(pool_id=pool_id, token_id=0xABCD)

# Transparent remote read and write
pool.write(offset=0, data=b"Disaggregated Memory Block")
data = pool.read(offset=0, length=26)
```

---

## 📁 Repository Structure

```
unifiedbus-simulator/
├── configs/               # Declarative SuperPoD YAML cluster topologies
├── daemon/                # UB Fabric Switch Daemon & UMMU router
├── guest_sdk/
│   ├── include/           # C headers (ubus.h, urma.h, cdma.h, obmm.h)
│   └── python/unifiedbus/ # Python SDK (urma, cdma, obmm, hccl, ubctl, device)
├── examples/              # Ready-to-run developer applications
├── qemu/                  # QEMU virtual UB PCI device model & cluster launcher
├── visualizer/            # Real-time Web dashboard & static assets
└── tests/                 # Comprehensive test suite
```
