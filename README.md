# UnifiedBus (UB / 灵衢) Virtual Platform & Silicon Co-Emulation Suite

An open virtual platform and hardware co-emulation environment for **UnifiedBus (UB / 灵衢) 2.0**, designed for building, debugging, and benchmarking distributed AI, collective communication, and disaggregated memory systems across **Kunpeng CPUs**, **Ascend NPUs**, and **Pooled Memory Appliances**.

---

## 📂 Repository Contents

This repository contains two complementary virtual platforms:

### 1. [`unifiedbus-simulator/`](./unifiedbus-simulator/) — High-Speed Discrete-Event Interconnect & AI Workload Simulator
* **Central Switch Fabric (`daemon/fabric.py`)**: Nanosecond PDES discrete-event timing engine modeling 800 Gbps to 1.6 Tbps line rates, 64-byte flit slicing, credit-based flow control, and HBM3 vs DDR5 memory controllers.
* **Complete Protocol Message Suite**: Full coverage of physical, link (LTSSM), transport (CNP/ACK), memory semantics, remote atomics (CAS/Add/Bitwise), cache coherence snooping (MESI), UMS (Socket-over-UB), URPC, and sysSentry emergency containment.
* **CIP Security Subsystem (`daemon/cip.py`)**: Line-rate Authenticated Encryption (AES-256-GCM / SM4-GCM), TokenID key binding, and 64-bit anti-replay sliding window.
* **Real-Time Interactive Web Visualizer (`visualizer/`)**: Dynamic SuperPoD topology diagrams, link traffic heatmaps, active memory pool tables, and transaction logs on `http://localhost:8088`.
* **Guest SDKs & BenchLib (`guest_sdk/`, `examples/`)**: `liburma`, `libcdma`, `libobmm`, `HCCL` (Ring-AllReduce), and LLM-70B multi-layer AI training traces.

### 2. [`unifiedbus-qemu-silicon/`](./unifiedbus-qemu-silicon/) — Low-Level QEMU PCIe Silicon & Linux Kernel Emulation
* **QEMU PCIe Silicon Model (`silicon/`)**: Hardware device model for the Huawei UBPU Controller (`Vendor 0x19E5, Device 0xA880`) exposing BAR0 (64KB CSR), BAR1 (1MB UMMU), BAR2 (256KB Doorbell/Rings), and BAR3 (64MB Shared Memory Aperture).
* **Linux Kernel Driver Layer (`kernel/`)**: Character device (`/dev/ub0`), standard IOCTL dispatch, and sysfs hierarchy (`/sys/class/ubus/ub0/`).
* **Official Open-Source C Libraries (`open_source_libs/`)**: Native C shared libraries (`liburma.so`, `libcdma.so`, `libobmm.so`) conforming strictly to the openEuler 24.03 ABI.
* **Official `ubctl` CLI (`ubctl/`)**: Native C diagnostic and management utility.
* **Multi-QEMU Cluster Orchestrator (`qemu_environment/`)**: Spawns and manages separate, isolated `qemu-system-x86_64` VM instances for each UBPU connected over the silicon fabric.
* **Native C Demonstrator Binaries (`demonstrators/`)**: Standalone compiled C applications for URMA P2P RDMA, CDMA async batches, 16GB OBMM memory pooling, 4-NPU HCCL Ring-AllReduce, and CIP encryption.

---

## 🚀 Quick Start

### Running the High-Speed Simulator
```bash
cd unifiedbus-simulator

# Run all 14 unit tests
python3 run_tests.py

# Run 4-NPU HCCL Ring-AllReduce Collective
python3 -m qemu.launcher --config configs/superpod_kunpeng_ascend.yaml --run-example examples/04_hccl_allreduce.py

# Run CIP AES-256-GCM Encrypted Memory & Attack Simulation
python3 -m qemu.launcher --config configs/superpod_kunpeng_ascend.yaml --run-example examples/06_cip_encrypted_memory.py

# Launch the Web Visualizer Dashboard
python3 -m visualizer.dashboard --port 8088
```

### Running the QEMU Silicon & Linux Kernel Platform
```bash
cd unifiedbus-qemu-silicon

# Compile all C libraries and binaries
make all

# Run the complete demonstrator verification suite
./run_all_demonstrators.sh

# Run Multi-QEMU isolated VM instances
python3 qemu_environment/qemu_multi_vm_runner.py --run-demo ./demonstrators/demo_hccl_ring
```
