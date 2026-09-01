#!/bin/bash
# ==============================================================================
# UnifiedBus (UB) Silicon & Linux Kernel Platform - Complete Verification Suite
# ==============================================================================

set -e
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE_DIR"

echo "======================================================================="
echo "   UnifiedBus (UB / 灵衢) Silicon & Linux Kernel Platform Demonstrator"
echo "======================================================================="
echo ""

echo "[1/5] Running Demonstrator 1: Native C URMA P2P Transfer..."
./demonstrators/demo_urma_p2p
echo ""

echo "[2/5] Running Demonstrator 2: Native C CDMA Asynchronous DMA Batch..."
./demonstrators/demo_cdma_async
echo ""

echo "[3/5] Running Demonstrator 3: Native C OBMM Disaggregated Memory Pooling..."
./demonstrators/demo_obmm_memory_pool
echo ""

echo "[4/5] Running Demonstrator 4: Native C HCCL Ring-AllReduce on 4 Ascend NPUs..."
./demonstrators/demo_hccl_ring
echo ""

echo "[5/5] Running Demonstrator 5: Native C CIP Hardware AES-256-GCM Encryption..."
./demonstrators/demo_cip_security
echo ""

echo "======================================================================="
echo " Inspecting Hardware & Telemetry using native C 'ubctl'..."
echo "======================================================================="
./ubctl/ubctl info 1
echo ""
./ubctl/ubctl stats 1
echo ""
echo "======================================================================="
echo " [SUCCESS] All 5 Demonstrators & ubctl Verified with Zero Errors!"
echo "======================================================================="
