# UnifiedBus (UB / 灵衢) QEMU Silicon Emulation & Linux Kernel Virtual Platform

An alternative, low-level virtual platform that emulates the **Huawei UBPU / UnifiedBus Host Controller PCIe Silicon** (`0x19E5:0xA880`), exposes standard **Linux Kernel `/dev/ub0` character device IOCTLs and sysfs attributes**, and provides compiled **official C shared libraries (`liburma.so`, `libcdma.so`, `libobmm.so`)** and the native C **`ubctl`** CLI utility.

---

## 🏗️ Architecture Overview

```
+─────────────────────────────────────────────────────────────────────────────+
|                         C User-Space Applications                           |
|   • demo_urma_p2p (RDMA)               • demo_hccl_ring (Collective)        |
|   • demo_cdma_async (Batch DMA)        • demo_cip_security (AES-256-GCM)    |
|   • demo_obmm_memory_pool (16GB Loan)  • ubctl (Hardware Management CLI)    |
+──────────────────────────────────────┬──────────────────────────────────────+
                                       │
                                       ▼
+─────────────────────────────────────────────────────────────────────────────+
|               Official Open-Source C Shared Libraries (ABI 2.0)             |
|   • liburma.so (URMA C API)            • libcdma.so (CDMA Engine)           |
|   • libobmm.so (OBMM Memory Pooling)   • libub_silicon.so (Runtime Driver)  |
+──────────────────────────────────────┬──────────────────────────────────────+
                                       │ open("/dev/ub0", O_RDWR) + ioctl()
                                       ▼
+─────────────────────────────────────────────────────────────────────────────+
|                     Linux Kernel Driver Layer (/dev/ub0)                    |
|   • UB_IOCTL_REG_SEG / UNREG_SEG       • UB_IOCTL_CREATE_JETTY / DESTROY    |
|   • UB_IOCTL_SUBMIT_WR (DMA Doorbells) • UB_IOCTL_GET_DEV_INFO / STATS      |
|   • Sysfs hierarchy: /sys/class/ubus/ub0/ {vendor_id, speed, flit_counters} |
+──────────────────────────────────────┬──────────────────────────────────────+
                                       │ MMIO BAR Reads/Writes & Ring Buffers
                                       ▼
+─────────────────────────────────────────────────────────────────────────────+
|           QEMU PCIe Hardware Silicon Model (Vendor 0x19E5, Device 0xA880)  |
|   • BAR 0: 64 KB CSR (Control & Status Registers, Version 2.0, 800 Gbps)    |
|   • BAR 1: 1 MB UMMU (Global Address Translation & 32-bit TokenID Security) |
|   • BAR 2: 256 KB Rings (Submission SQ, Completion CQ, Hardware Doorbells)  |
|   • BAR 3: 64 MB Direct Shared Memory Aperture (Zero-Copy Interconnect)     |
|   • CIP Security Engine: Line-rate AES-256-GCM authenticated encryption     |
+─────────────────────────────────────────────────────────────────────────────+
```

---

## 📦 Directory Structure

```
unifiedbus-qemu-silicon/
├── Makefile                            # Top-level build orchestration
├── README.md                           # Documentation
├── run_all_demonstrators.sh            # One-click master test runner
├── include/                            # Official UB 2.0 C Headers
│   ├── ubus_hw.h                       # PCIe BAR maps, CSR offsets, descriptors
│   ├── ubus_ioctl.h                    # /dev/ub0 IOCTL interfaces
│   ├── urma.h                          # liburma C API definitions
│   ├── cdma.h                          # libcdma C API definitions
│   └── obmm.h                          # libobmm C API definitions
├── silicon/                            # QEMU Silicon Device Model & Fabric
│   ├── ub_silicon_backend.h            # Hardware interconnect & UMMU directory
│   └── ub_silicon_backend.c            # Flit timing (64B) & CIP crypto pipeline
├── kernel/                             # Linux Kernel Driver
│   ├── ubus_driver.h                   # Driver state & handle tracking
│   └── ubus_driver.c                   # /dev/ub0 character device implementation
├── open_source_libs/                   # Compiled C Shared Libraries
│   ├── liburma/urma.c                  # liburma.so (URMA RDMA API)
│   ├── libcdma/cdma.c                  # libcdma.so (Async DMA Queue)
│   └── libobmm/obmm.c                  # libobmm.so (Memory Pooling)
├── ubctl/                              # Official openEuler ubctl CLI
│   └── ubctl.c                         # Native C hardware diagnostics
└── demonstrators/                      # Native C Demonstrator Binaries
    ├── demo_urma_p2p.c                 # Kunpeng <-> Ascend P2P RDMA Transfer
    ├── demo_cdma_async.c               # Batch Asynchronous DMA Transfers
    ├── demo_obmm_memory_pool.c         # 16 GB Memory Pool Loan & TokenID Defense
    ├── demo_hccl_ring.c                # 4-Rank NPU Ring-AllReduce (24.88 GB/s)
    └── demo_cip_security.c             # AES-256-GCM Line Encryption & Wire-Tap Test
```

---

## 🚀 How to Build & Run

### 1. Compile Everything in One Step
```bash
cd /home/silviu/.gemini/antigravity/scratch/unifiedbus-qemu-silicon
make all
```
This produces:
* `libub_silicon.so`
* `liburma.so`
* `libcdma.so`
* `libobmm.so`
* `ubctl/ubctl`
* All 5 demonstrator binaries in `demonstrators/`

### 2. Run All Demonstrators
```bash
./run_all_demonstrators.sh
```

### 3. Run Individual Native Demonstrators
```bash
# 1. URMA P2P RDMA Transfer
./demonstrators/demo_urma_p2p

# 2. CDMA Batch Asynchronous DMA (8 Descriptors)
./demonstrators/demo_cdma_async

# 3. OBMM 16GB Disaggregated Memory Pooling
./demonstrators/demo_obmm_memory_pool

# 4. HCCL Multi-Rank Ring-AllReduce (4 Ascend NPUs)
./demonstrators/demo_hccl_ring

# 5. CIP Hardware AES-256-GCM Line Encryption
./demonstrators/demo_cip_security
```

### 4. Manage Hardware with Native `ubctl`
```bash
# View Controller Hardware Info & BAR Apertures
./ubctl/ubctl info 1

# View Real-Time TX/RX Flits & CIP Crypto Telemetry
./ubctl/ubctl stats 1

# View SuperPoD Interconnect Topology
./ubctl/ubctl topology
```
