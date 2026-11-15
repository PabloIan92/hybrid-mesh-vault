#!/usr/bin/env python3
"""
Example: Automated System Backup & Offload
Dumps important directories into an in-memory compressed tarball and offloads to Edge Vault.
"""

import tarfile
import time
from pathlib import Path
from mesh_vault.offload import offload_file


def backup_and_offload():
    backup_name = f"backup_cloud_configs_{int(time.time())}.tar.gz"
    backup_ram_path = Path("/dev/shm") / backup_name

    print(f"📦 Creating compressed backup in RAM: {backup_ram_path}...")
    source_dir = Path.home() / ".config"

    if not source_dir.exists():
        print("Source directory does not exist, using current directory.")
        source_dir = Path(__file__).parent

    with tarfile.open(backup_ram_path, "w:gz") as tar:
        tar.add(source_dir, arcname=source_dir.name)

    size_kb = round(backup_ram_path.stat().st_size / 1024, 2)
    print(f"Backup created ({size_kb} KB). Offloading to Edge Vault...")

    receipt = offload_file(
        local_path=str(backup_ram_path),
        target_subdir="backups/cloud_nodes",
        purge_local=True
    )

    print("✅ Backup safely stored in Edge Vault!")
    print(f"Destination: {receipt['remote_path']}")
    print(f"SHA-256: {receipt['sha256']}")


if __name__ == "__main__":
    backup_and_offload()
