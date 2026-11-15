---
name: hybrid-mesh-vault
description: >-
  Zero-cost disaggregated compute and storage for AI agents across Cloud and Edge.
  Allows agents to process heavy datasets in Cloud RAM (e.g. 15-24GB) and safely
  offload or fetch artifacts to/from high-capacity Edge Vault storage (400GB-2TB)
  over Tailscale Mesh with SHA-256 verification and zero disk footprint in the cloud.
license: MIT
metadata:
  author: Pablo Ian (PabloIan92)
  version: "1.0.0"
---

# 🌌 Hybrid Mesh Vault: Agent Skill

The **Hybrid Mesh Vault** skill provides AI agents (Antigravity, Claude Code, OpenCode) with tools to offload large generated artifacts (video outputs, model weights, database dumps, datasets, build caches) from disk-constrained Cloud VPS instances to high-capacity Edge Homelab storage over an encrypted Tailscale Mesh.

---

## 🎯 When to Use This Skill

Use this skill when:
- Generating large files (>50MB) on cloud servers with limited disk space (<20GB free).
- Building multi-stage data pipelines that require high RAM (15GB+) but cold-storage persistence.
- Archiving daily agent memory dumps, logs, and transcripts to a private sovereign edge NAS.
- Preserving cloud disk space to avoid `No space left on device` crashes.

---

## ⚡ Agent CLI Tooling

The skill exposes the `mesh-vault` CLI:

### 1. Check Cluster Telemetry & Storage Capacity
```bash
mesh-vault status
```
Returns:
- Local node role (`COMPUTE_PRIMARY` vs `STORAGE_VAULT`)
- Available Cloud RAM and `/dev/shm` capacity
- Edge Vault online status, RTT latency, and free storage on disk

### 2. Offload File to Edge Vault (Auto-Purge Cloud)
```bash
mesh-vault offload /path/to/heavy_output.mp4 --subdir videos
```
- Computes SHA-256 checksum in memory chunks.
- Transfers via encrypted WireGuard/Tailscale tunnel.
- Verifies remote SHA-256 checksum.
- Automatically purges cloud copy upon verified delivery (0 bytes wasted on cloud disk).

### 3. Fetch File On-Demand to Cloud RAM
```bash
mesh-vault fetch model_weights.pt --target-dir /dev/shm --subdir checkpoints
```
- Fetches remote file directly into `/dev/shm` (Linux RAM-disk).
- Computes and verifies SHA-256.
- Grants microsecond read latencies without disk I/O.

---

## 🐍 Python Agent SDK

```python
from mesh_vault.offload import offload_file
from mesh_vault.fetch import fetch_file

# Offload after processing
receipt = offload_file(
    local_path="/dev/shm/generated_dataset.parquet",
    target_subdir="datasets/2026-11",
    purge_local=True
)
print(f"Offloaded to {receipt['remote_path']} at {receipt['speed_mb_s']} MB/s")

# Fetch when needed
file_info = fetch_file(
    remote_filename="generated_dataset.parquet",
    target_dir="/dev/shm",
    target_subdir="datasets/2026-11"
)
print(f"Fetched into {file_info['local_path']}")
```
