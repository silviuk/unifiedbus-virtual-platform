#!/bin/bash
# ==============================================================================
# UnifiedBus (UB) QEMU Virtual Machine Launcher
# Boots a QEMU VM representing a Kunpeng CPU or Ascend NPU node with UB device.
# ==============================================================================

NODE_ID=${1:-1}
NODE_TYPE=${2:-"KUNPENG_CPU"}
SOCKET_PATH=${3:-"/tmp/ub-fabric/fabric.sock"}

echo "======================================================================="
echo " Starting QEMU Virtual Machine for UB Node 0x$(printf '%04X' $NODE_ID) ($NODE_TYPE)"
echo " Connecting to UnifiedBus Fabric at $SOCKET_PATH"
echo "======================================================================="

# Check QEMU binary
if command -v qemu-system-x86_64 &> /dev/null; then
    QEMU_BIN="qemu-system-x86_64"
elif command -v qemu-system-aarch64 &> /dev/null; then
    QEMU_BIN="qemu-system-aarch64"
else
    echo "[Error] QEMU binary not found. Please install qemu-system-x86_64 or qemu-system-aarch64."
    exit 1
fi

# QEMU parameters configuring the virtual UB device over socket backend:
# -chardev socket: Connects to the central ub-fabric-daemon switch
# -device ivshmem/pci or custom ub-device: Exposes BAR0/BAR1 registers to guest OS
QEMU_CMD=(
    $QEMU_BIN
    -name "UB-Node-$NODE_ID"
    -m 2048
    -smp 4
    -nographic
    -chardev "socket,id=ub_sock0,path=$SOCKET_PATH"
    -device "ivshmem-plain,memdev=shm0,id=ub_dev0"
    -object "memory-backend-file,id=shm0,mem-path=/dev/shm/ub_node_${NODE_ID}_shm,size=64M,share=on"
    -serial mon:stdio
)

echo "[*] Generated QEMU Invocation Command:"
echo "${QEMU_CMD[@]}"
echo "======================================================================="
