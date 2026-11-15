#!/usr/bin/env python3
"""
hybrid-mesh-vault: Fetch Engine
Retrieves artifacts from Edge Vault storage back into Cloud RAM or disk on-demand.
"""

import os
import time
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

from mesh_vault.core import load_config
from mesh_vault.offload import calculate_sha256


def fetch_file(
    remote_filename: str,
    target_dir: str = "/dev/shm",
    target_subdir: str = "",
    custom_vault_host: Optional[str] = None,
    custom_vault_user: Optional[str] = None,
    custom_vault_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Fetch a file from Edge Vault to Cloud RAM (/dev/shm) or local directory.
    Verifies SHA-256 upon arrival.
    """
    cfg = load_config()
    vault = cfg.get("vault_peer", {})

    vault_host = custom_vault_host or vault.get("host", "100.64.0.2")
    vault_user = custom_vault_user or vault.get("user", "vault-user")
    base_vault_dir = custom_vault_dir or vault.get("storage_dir", "/mnt/mesh_vault_storage")

    if target_subdir:
        remote_src_dir = f"{base_vault_dir}/{target_subdir}".rstrip("/")
    else:
        remote_src_dir = base_vault_dir.rstrip("/")

    remote_file_path = f"{remote_src_dir}/{remote_filename}"
    dest_path = Path(target_dir).resolve()
    dest_path.mkdir(parents=True, exist_ok=True)
    local_file_path = dest_path / remote_filename

    # 1. Check remote hash first
    start_time = time.time()
    chk_cmd = [
        "ssh", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=accept-new",
        f"{vault_user}@{vault_host}",
        f"sha256sum '{remote_file_path}'"
    ]
    res_chk = subprocess.run(chk_cmd, capture_output=True, text=True)
    if res_chk.returncode != 0:
        raise FileNotFoundError(f"Remote file '{remote_file_path}' not found on Edge Vault: {res_chk.stderr}")

    remote_hash = res_chk.stdout.strip().split()[0]

    # 2. Transfer from Vault to Local Cloud Target
    rsync_cmd = [
        "rsync",
        "-avz",
        "--partial",
        "--timeout=30",
        "-e", "ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new",
        f"{vault_user}@{vault_host}:{remote_file_path}",
        str(local_file_path)
    ]

    transfer_start = time.time()
    res_rsync = subprocess.run(rsync_cmd, capture_output=True, text=True)
    if res_rsync.returncode != 0:
        raise RuntimeError(f"Fetch failed: {res_rsync.stderr}")
    transfer_duration = round(time.time() - transfer_start, 3)

    # 3. Verify Local Checksum
    local_hash = calculate_sha256(local_file_path)
    if local_hash != remote_hash:
        local_file_path.unlink(missing_ok=True)
        raise ValueError(f"Integrity check failed on fetch: Local {local_hash} != Remote {remote_hash}")

    file_size_bytes = local_file_path.stat().st_size
    file_size_mb = round(file_size_bytes / (1024**2), 2)
    speed_mb_s = round(file_size_mb / max(transfer_duration, 0.001), 2)
    total_duration = round(time.time() - start_time, 3)

    return {
        "status": "success",
        "file_name": remote_filename,
        "size_bytes": file_size_bytes,
        "size_mb": file_size_mb,
        "sha256": local_hash,
        "local_path": str(local_file_path),
        "source_vault": f"{vault_user}@{vault_host}:{remote_file_path}",
        "in_ram_disk": "/dev/shm" in str(local_file_path),
        "transfer_seconds": transfer_duration,
        "total_seconds": total_duration,
        "speed_mb_s": speed_mb_s
    }
