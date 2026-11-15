#!/usr/bin/env python3
"""
Example: AI Dataset Generation Pipeline with Hybrid Mesh Vault
Simulates high-RAM processing in cloud memory and offloading to Edge Vault.
"""

import time
from pathlib import Path
from mesh_vault.offload import offload_file


def run_pipeline():
    print("=" * 60)
    print(" 🤖 AI DATASET GENERATION PIPELINE (Cloud RAM -> Edge Vault)")
    print("=" * 60)

    # 1. Generate directly in RAM-disk to avoid wearing NVMe / filling root partition
    output_path = Path("/dev/shm/synthetic_embeddings.jsonl")
    print(f"\n1. Ingesting & processing in RAM-disk ({output_path})...")

    sample_record = '{"id": %d, "embedding": [0.123, -0.456, 0.789], "tag": "agent_memory"}\n'
    t0 = time.time()
    with open(output_path, "w") as f:
        for i in range(50000):
            f.write(sample_record % i)

    size_mb = round(output_path.stat().st_size / (1024**2), 2)
    print(f"   Generated {size_mb} MB in {round(time.time() - t0, 3)}s.")

    # 2. Offload to Edge Vault
    print("\n2. Offloading to Edge Vault via Tailscale...")
    receipt = offload_file(
        local_path=str(output_path),
        target_subdir="ai_pipelines/datasets",
        purge_local=True
    )

    print("   ✅ Offload successful!")
    print(f"   • Remote Destination: {receipt['remote_path']}")
    print(f"   • SHA-256 Hash:       {receipt['sha256']}")
    print(f"   • Speed:              {receipt['speed_mb_s']} MB/s")
    print(f"   • Cloud Disk Left:    Clean (Purged local file: {receipt['purged_from_cloud']})")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    run_pipeline()
