#!/usr/bin/env python3
"""
hybrid-mesh-vault: Core Node & Cluster Engine
Handles resource introspection, role auto-classification, and peer discovery over Tailscale.
"""

import os
import sys
import json
import socket
import shutil
import subprocess
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "hybrid-mesh-vault"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"


class NodeRole(str, Enum):
    COMPUTE_PRIMARY = "compute_primary"  # High RAM / Low Disk (e.g. Cloud VPS)
    STORAGE_VAULT = "storage_vault"      # High Disk / Modest RAM (e.g. Mini PC, Homelab NAS)
    HYBRID = "hybrid"                    # Balanced resources


def get_tailscale_ip() -> Optional[str]:
    """Retrieve the primary Tailscale IPv4 address of the local node."""
    try:
        res = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True,
            text=True,
            timeout=3
        )
        if res.returncode == 0:
            ips = res.stdout.strip().split()
            if ips:
                return ips[0]
    except Exception:
        pass

    # Fallback: check 100.* interfaces
    try:
        import psutil
        for iface, addrs in psutil.net_if_addrs().items():
            if "tailscale" in iface.lower() or "utun" in iface.lower() or "wg" in iface.lower():
                for addr in addrs:
                    if addr.family == socket.AF_INET and addr.address.startswith("100."):
                        return addr.address
    except Exception:
        pass
    return None


def get_system_metrics() -> Dict[str, Any]:
    """Inspect local memory, disk, and CPU capacity."""
    # Memory metrics via /proc/meminfo or sysconf
    mem_total_bytes = 0
    mem_avail_bytes = 0
    swap_total_bytes = 0
    swap_free_bytes = 0

    try:
        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()
        data = {}
        for line in lines:
            parts = line.split(":")
            if len(parts) == 2:
                key = parts[0].strip()
                val_kb = int(parts[1].strip().split()[0])
                data[key] = val_kb * 1024
        mem_total_bytes = data.get("MemTotal", 0)
        mem_avail_bytes = data.get("MemAvailable", mem_total_bytes)
        swap_total_bytes = data.get("SwapTotal", 0)
        swap_free_bytes = data.get("SwapFree", 0)
    except Exception:
        pass

    # Disk metrics
    root_stat = shutil.disk_usage("/")
    disk_total_bytes = root_stat.total
    disk_free_bytes = root_stat.free
    disk_used_bytes = root_stat.used

    # RAM-disk (/dev/shm) availability for zero-copy memory buffers
    shm_free_bytes = 0
    if os.path.exists("/dev/shm"):
        try:
            shm_stat = shutil.disk_usage("/dev/shm")
            shm_free_bytes = shm_stat.free
        except Exception:
            shm_free_bytes = 0

    return {
        "hostname": socket.gethostname(),
        "tailscale_ip": get_tailscale_ip(),
        "ram": {
            "total_gb": round(mem_total_bytes / (1024**3), 2),
            "available_gb": round(mem_avail_bytes / (1024**3), 2),
            "total_bytes": mem_total_bytes,
            "available_bytes": mem_avail_bytes,
            "shm_free_gb": round(shm_free_bytes / (1024**3), 2)
        },
        "swap": {
            "total_gb": round(swap_total_bytes / (1024**3), 2),
            "free_gb": round(swap_free_bytes / (1024**3), 2)
        },
        "disk": {
            "total_gb": round(disk_total_bytes / (1024**3), 2),
            "free_gb": round(disk_free_bytes / (1024**3), 2),
            "used_gb": round(disk_used_bytes / (1024**3), 2),
            "used_pct": round((disk_used_bytes / disk_total_bytes) * 100, 1) if disk_total_bytes else 0
        }
    }


def classify_role(metrics: Dict[str, Any]) -> NodeRole:
    """Auto-detect if this node is Compute-Heavy or Storage-Heavy."""
    ram_gb = metrics["ram"]["total_gb"]
    disk_free_gb = metrics["disk"]["free_gb"]

    if ram_gb >= 12 and disk_free_gb < 80:
        return NodeRole.COMPUTE_PRIMARY
    elif disk_free_gb >= 200 and ram_gb <= 8:
        return NodeRole.STORAGE_VAULT
    else:
        return NodeRole.HYBRID


def load_config() -> Dict[str, Any]:
    """Load or initialize default configuration."""
    if DEFAULT_CONFIG_FILE.exists():
        try:
            with open(DEFAULT_CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass

    metrics = get_system_metrics()
    role = classify_role(metrics)
    
    cfg = {
        "node_name": metrics["hostname"],
        "role": role.value,
        "tailscale_ip": metrics["tailscale_ip"],
        "vault_peer": {
            "host": os.environ.get("MESH_VAULT_PEER_HOST", "100.64.0.2"),
            "user": os.environ.get("MESH_VAULT_PEER_USER", "vault-user"),
            "storage_dir": os.environ.get("MESH_VAULT_PEER_DIR", "/mnt/mesh_vault_storage"),
            "port": 22
        },
        "compute_peer": {
            "host": os.environ.get("MESH_COMPUTE_PEER_HOST", "100.64.0.1"),
            "user": os.environ.get("MESH_COMPUTE_PEER_USER", "cloud-user"),
            "port": 22
        },
        "safety": {
            "verify_sha256": True,
            "atomic_write": True,
            "auto_purge_cloud_after_offload": True,
            "cloud_min_free_disk_gb": 5.0
        }
    }
    return cfg


def save_config(cfg: Dict[str, Any]) -> None:
    """Save configuration to disk."""
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(DEFAULT_CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
