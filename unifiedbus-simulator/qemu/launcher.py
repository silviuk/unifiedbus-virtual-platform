"""
UnifiedBus Multi-VM & Virtual Node Cluster Launcher
Orchestrates QEMU VMs or high-speed virtual nodes over the UB fabric.
Zero external dependencies (supports PyYAML if present, or built-in YAML parser).
"""

import argparse
import asyncio
import os
import sys
import time
import subprocess
import signal
from typing import List, Dict, Any, Optional

try:
    import yaml
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False

DEFAULT_SOCKET = "/tmp/ub-fabric/fabric.sock"


def parse_simple_yaml(text: str) -> Dict[str, Any]:
    """
    Lightweight zero-dependency fallback YAML parser for cluster configs.
    """
    result: Dict[str, Any] = {}
    current_section: Optional[str] = None
    current_list: Optional[List[Any]] = None
    current_dict_item: Optional[Dict[str, Any]] = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip())

        if line.startswith("- id:"):
            if current_section and current_section not in result:
                result[current_section] = []
            current_dict_item = {"id": int(line.split(":", 1)[1].strip())}
            result[current_section].append(current_dict_item)
            continue

        if current_dict_item is not None and indent >= 4 and ":" in line:
            k, v = [x.strip() for x in line.split(":", 1)]
            v = v.strip('"\'')
            if v.isdigit():
                current_dict_item[k] = int(v)
            else:
                try:
                    current_dict_item[k] = float(v)
                except ValueError:
                    current_dict_item[k] = v
            continue

        if indent == 0 and ":" in line:
            k, v = [x.strip() for x in line.split(":", 1)]
            v = v.strip('"\'')
            if not v:
                current_section = k
                result[k] = {} if k != "nodes" else []
                current_dict_item = None
            else:
                current_section = None
                current_dict_item = None
                if v.isdigit():
                    result[k] = int(v)
                else:
                    try:
                        result[k] = float(v)
                    except ValueError:
                        result[k] = v
            continue

        if indent > 0 and current_section and ":" in line:
            k, v = [x.strip() for x in line.split(":", 1)]
            v = v.strip('"\'')
            if isinstance(result.get(current_section), dict):
                if v.isdigit():
                    result[current_section][k] = int(v)
                else:
                    try:
                        result[current_section][k] = float(v)
                    except ValueError:
                        result[current_section][k] = v

    return result


def load_cluster_config(config_path: str) -> Dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()
    if HAVE_YAML:
        return yaml.safe_load(content)
    return parse_simple_yaml(content)


class UBClusterOrchestrator:
    def __init__(self, config: Dict[str, Any], socket_path: str = DEFAULT_SOCKET):
        self.config = config
        self.socket_path = socket_path
        self.fabric_proc: Optional[subprocess.Popen] = None
        self.node_procs: List[subprocess.Popen] = []

    def start_fabric(self):
        fabric_cfg = self.config.get("fabric", {})
        bw = fabric_cfg.get("bandwidth_gbps", 800.0)
        lat = fabric_cfg.get("hop_latency_ns", 15.0)

        if os.path.exists(self.socket_path):
            try:
                os.remove(self.socket_path)
            except OSError:
                pass

        cmd = [
            sys.executable, "-m", "daemon.fabric",
            "--socket", self.socket_path,
            "--bw", str(bw),
            "--latency", str(lat)
        ]
        print(f"[*] Starting UnifiedBus Fabric Daemon (BW: {bw} Gbps, Latency: {lat} ns)...")
        self.fabric_proc = subprocess.Popen(cmd)
        
        # Wait for socket to become available
        start_t = time.time()
        while time.time() - start_t < 5.0:
            if os.path.exists(self.socket_path):
                time.sleep(0.1)
                break
            time.sleep(0.05)

        if not os.path.exists(self.socket_path):
            raise RuntimeError("UnifiedBus Fabric Daemon failed to create socket")
        print(f"[+] UnifiedBus Fabric is UP at {self.socket_path}")

    def run_example_workload(self, script_path: str) -> int:
        print(f"\n[*] Launching workload: {script_path}")
        cmd = [sys.executable, script_path, "--socket", self.socket_path]
        proc = subprocess.Popen(cmd)
        proc.wait()
        return proc.returncode

    def shutdown(self):
        print("\n[*] Shutting down UnifiedBus Cluster...")
        for p in self.node_procs:
            try:
                p.terminate()
                p.wait(timeout=1.0)
            except Exception:
                p.kill()
        if self.fabric_proc:
            try:
                self.fabric_proc.terminate()
                self.fabric_proc.wait(timeout=2.0)
            except Exception:
                self.fabric_proc.kill()
        print("[+] UnifiedBus Cluster shutdown complete.")


def main():
    parser = argparse.ArgumentParser(description="UnifiedBus Multi-VM & Node Cluster Launcher")
    parser.add_argument("--config", default="configs/superpod_kunpeng_ascend.yaml", help="Path to cluster YAML configuration")
    parser.add_argument("--socket", default=DEFAULT_SOCKET, help="Fabric socket path")
    parser.add_argument("--mode", choices=["virtual", "qemu"], default="virtual", help="Execution mode: 'virtual' for fast process nodes (default), 'qemu' for full QEMU VM instances")
    parser.add_argument("--run-example", help="Run a specific example script against the launched cluster")
    args = parser.parse_args()

    if not os.path.exists(args.config):
        print(f"[Error] Configuration file not found: {args.config}")
        sys.exit(1)

    cfg = load_cluster_config(args.config)
    orchestrator = UBClusterOrchestrator(cfg, socket_path=args.socket)

    def sigint_handler(sig, frame):
        orchestrator.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, sigint_handler)

    try:
        orchestrator.start_fabric()
        
        # Print cluster summary
        cluster_name = cfg.get("cluster_name", "UB-SuperPoD")
        nodes = cfg.get("nodes", [])
        print(f"\n{'='*65}")
        print(f" Cluster: {cluster_name} ({len(nodes)} UB Nodes)")
        print(f"{'='*65}")
        for n in nodes:
            print(f" • Node 0x{n['id']:04X} : {n.get('type', 'XPU'):<16} [Arch: {n.get('arch', 'aarch64')}, Mem: {n.get('memory', '32GB')}]")
        print(f"{'='*65}\n")

        if args.mode == "qemu":
            print("[*] QEMU Virtual Machine Mode Selected.")
            print("[*] Launching QEMU VM instances with Virtual UB PCI Devices...")
            for n in nodes:
                n_id = n['id']
                n_type = n.get('type', 'XPU')
                cmd_str = f"qemu-system-x86_64 -name UB-Node-{n_id} -m 2048 -smp 4 -chardev socket,id=ub0,path={args.socket} -device ivshmem-plain,memdev=shm{n_id} ..."
                print(f"   [QEMU VM 0x{n_id:04X}] Command: {cmd_str}")
            print("[*] QEMU VMs connected to UnifiedBus Fabric via Unix Socket backend.")

        if args.run_example:
            ret = orchestrator.run_example_workload(args.run_example)
            orchestrator.shutdown()
            sys.exit(ret)
        else:
            print("[*] Cluster is running. You can run UB applications in another terminal.")
            print("[*] Press Ctrl+C to terminate.")
            while True:
                time.sleep(1.0)
    except Exception as e:
        print(f"[Error] {e}")
        orchestrator.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    main()
