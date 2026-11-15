#!/usr/bin/env python3
"""
hybrid-mesh-vault: Offload Engine
Safely offloads computed artifacts from Cloud RAM/disk to Edge Vault storage with SHA-256 verification and atomic purge.
"""

import os
import sys
import time
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

from mesh_vault.core import load_config, get_system_metrics


def calculate_sha256(file_path: Path, chunk_size: int = 4 * 1024 * 1024) -> str:
    """Compute SHA-256 hash in 4MB chunks for minimal RAM footprint."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def offload_file(
    local_path: str,
    target_subdir: str = "",
    purge_local: Optional[bool] = None,
    custom_vault_host: Optional[str] = None,
    custom_vault_user: Optional[str] = None,
    custom_vault_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Stream a file from Cloud Compute to Edge Storage Vault.
    1. Validates local file.
    2. Calculates local SHA-256.
    3. Transfers via rsync/ssh over Tailscale.
    4. Verifies remote SHA-256.
    5. Purges local cloud copy if verification passes.
    """
    path = Path(local_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Source path '{local_path}' does not exist.")

    cfg = load_config()
    vault = cfg.get("vault_peer", {})
    safety = cfg.get("safety", {})

    vault_host = custom_vault_host or vault.get("host", "100.64.0.2")
    vault_user = custom_vault_user or vault.get("user", "vault-user")
    base_vault_dir = custom_vault_dir or vault.get("storage_dir", "/mnt/mesh_vault_storage")
    
    if target_subdir:
        remote_dest_dir = f"{base_vault_dir}/{target_subdir}".rstrip("/")
    else:
        remote_dest_dir = base_vault_dir.rstrip("/")

    should_purge = safety.get("auto_purge_cloud_after_offload", True) if purge_local is None else purge_local

    file_size_bytes = path.stat().st_size
    file_size_mb = round(file_size_bytes / (1024**2), 2)
    filename = path.name

    # 1. Local checksum
    start_time = time.time()
    local_hash = calculate_sha256(path)

    # 2. Ensure remote directory exists on Edge Vault
    mkdir_cmd = [
        "ssh", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=accept-new",
        f"{vault_user}@{vault_host}",
        f"mkdir -p '{remote_dest_dir}'"
    ]
    res_mkdir = subprocess.run(mkdir_cmd, capture_output=True, text=True)
    if res_mkdir.returncode != 0:
        raise RuntimeError(f"Failed to create remote directory on Edge Vault: {res_mkdir.stderr}")

    # 3. Secure rsync transfer over Tailscale
    remote_target = f"{vault_user}@{vault_host}:{remote_dest_dir}/"
    rsync_cmd = [
        "rsync",
        "-avz",
        "--partial",
        "--timeout=30",
        "-e", "ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new",
        str(path),
        remote_target
    ]
    
    transfer_start = time.time()
    res_rsync = subprocess.run(rsync_cmd, capture_output=True, text=True)
    if res_rsync.returncode != 0:
        raise RuntimeError(f"Rsync transfer failed: {res_rsync.stderr}")
    transfer_duration = round(time.time() - transfer_start, 3)

    # 4. Remote SHA-256 verification
    remote_file_path = f"{remote_dest_dir}/{filename}"
    verify_cmd = [
        "ssh", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=accept-new",
        f"{vault_user}@{vault_host}",
        f"sha256sum '{remote_file_path}'"
    ]
    res_verify = subprocess.run(verify_cmd, capture_output=True, text=True)
    if res_verify.returncode != 0:
        raise RuntimeError(f"Remote SHA256 checksum check failed: {res_verify.stderr}")

    remote_hash = res_verify.stdout.strip().split()[0]
    if local_hash != remote_hash:
        raise ValueError(
            f"Integrity Mismatch! Local: {local_hash} != Remote: {remote_hash}. File not purged."
        )

    # 5. Local Cloud Purge
    reclaimed_bytes = 0
    if should_purge:
        if path.is_file():
            path.unlink()
            reclaimed_bytes = file_size_bytes

    total_duration = round(time.time() - start_time, 3)
    speed_mb_s = round(file_size_mb / max(transfer_duration, 0.001), 2)

    return {
        "status": "success",
        "file_name": filename,
        "size_bytes": file_size_bytes,
        "size_mb": file_size_mb,
        "sha256": local_hash,
        "source_node": cfg.get("node_name", "cloud-worker"),
        "vault_node": f"{vault_user}@{vault_host}",
        "remote_path": remote_file_path,
        "transfer_seconds": transfer_duration,
        "total_seconds": total_duration,
        "speed_mb_s": speed_mb_s,
        "purged_from_cloud": should_purge,
        "disk_reclaimed_mb": round(reclaimed_bytes / (1024**2), 2)
    }
