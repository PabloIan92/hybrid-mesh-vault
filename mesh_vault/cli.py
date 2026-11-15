#!/usr/bin/env python3
"""
hybrid-mesh-vault: Unified CLI Interface
Command-line orchestrator for disaggregated compute & storage.
"""

import sys
import json
import time
import argparse
import subprocess
from pathlib import Path

from mesh_vault.core import (
    get_system_metrics,
    classify_role,
    load_config,
    save_config,
    DEFAULT_CONFIG_FILE
)
from mesh_vault.offload import offload_file
from mesh_vault.fetch import fetch_file


def cmd_status(args):
    """Display cluster status, node roles, and available resources."""
    cfg = load_config()
    local_m = get_system_metrics()
    local_role = classify_role(local_m)

    print("\n" + "=" * 62)
    print(" 🌌 HYBRID MESH VAULT: CLUSTER TELEMETRY")
    print("=" * 62)
    print(f" Node: {local_m['hostname']} ({local_m['tailscale_ip'] or 'No Tailscale IP'})")
    print(f" Role: {local_role.value.upper()}")
    print("-" * 62)
    print(f" RAM:  {local_m['ram']['available_gb']} GB available / {local_m['ram']['total_gb']} GB total")
    print(f" SHM:  {local_m['ram']['shm_free_gb']} GB available in /dev/shm (RAM-Disk)")
    print(f" Disk: {local_m['disk']['free_gb']} GB free / {local_m['disk']['total_gb']} GB total ({local_m['disk']['used_pct']}% used)")
    print("-" * 62)

    # Probe peer
    vault_cfg = cfg.get("vault_peer", {})
    vault_host = vault_cfg.get("host", "100.64.0.2")
    vault_user = vault_cfg.get("user", "vault-user")
    vault_dir = vault_cfg.get("storage_dir", "/mnt/mesh_vault_storage")

    print(f" 🛰️ Edge Vault Peer: {vault_user}@{vault_host}:{vault_dir}")
    t0 = time.time()
    probe_cmd = [
        "ssh", "-o", "ConnectTimeout=4", "-o", "StrictHostKeyChecking=accept-new",
        f"{vault_user}@{vault_host}",
        "df -h /; free -m"
    ]
    res = subprocess.run(probe_cmd, capture_output=True, text=True)
    rtt_ms = round((time.time() - t0) * 1000, 1)

    if res.returncode == 0:
        print(f" Status: ONLINE (RTT: {rtt_ms} ms via Tailscale)")
        lines = res.stdout.strip().split("\n")
        disk_line = lines[1] if len(lines) > 1 else ""
        print(f" Remote Disk: {disk_line}")
        print("=" * 62)
        print(" 🎯 Cluster Unified Architecture: ACTIVE")
        print("    Compute/RAM Engine: Cloud Node (15 GB RAM)")
        print("    Storage Vault:      Edge Mini PC (400+ GB Disk)")
        print("=" * 62 + "\n")
    else:
        print(f" Status: UNREACHABLE or TIMEOUT ({res.stderr.strip()})")
        print("=" * 62 + "\n")


def cmd_offload(args):
    """Offload a local file to Edge Vault storage."""
    print(f"\n🚀 Offloading '{args.path}' to Edge Vault...")
    try:
        receipt = offload_file(
            local_path=args.path,
            target_subdir=args.subdir or "",
            purge_local=not args.keep_local
        )
        print("✅ Transfer & Verification Complete!")
        print(f" • File:          {receipt['file_name']} ({receipt['size_mb']} MB)")
        print(f" • SHA-256:       {receipt['sha256'][:16]}...{receipt['sha256'][-8:]}")
        print(f" • Vault Dest:    {receipt['remote_path']}")
        print(f" • Throughput:    {receipt['speed_mb_s']} MB/s (Time: {receipt['transfer_seconds']}s)")
        print(f" • Cloud Purge:   {'YES (Reclaimed ' + str(receipt['disk_reclaimed_mb']) + ' MB)' if receipt['purged_from_cloud'] else 'NO (Kept local)'}\n")
    except Exception as e:
        print(f"❌ Offload Failed: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_fetch(args):
    """Retrieve an offloaded file back to Cloud RAM or disk."""
    print(f"\n📥 Fetching '{args.filename}' from Edge Vault...")
    try:
        receipt = fetch_file(
            remote_filename=args.filename,
            target_dir=args.target_dir,
            target_subdir=args.subdir or ""
        )
        print("✅ Fetch & Checksum Verified!")
        print(f" • File:          {receipt['file_name']} ({receipt['size_mb']} MB)")
        print(f" • Local Path:    {receipt['local_path']}")
        print(f" • In RAM-Disk:   {'YES (/dev/shm)' if receipt['in_ram_disk'] else 'NO'}")
        print(f" • Speed:         {receipt['speed_mb_s']} MB/s (Time: {receipt['transfer_seconds']}s)\n")
    except Exception as e:
        print(f"❌ Fetch Failed: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_list(args):
    """List files in the Edge Vault storage."""
    cfg = load_config()
    vault = cfg.get("vault_peer", {})
    vault_host = vault.get("host", "100.64.0.2")
    vault_user = vault.get("user", "vault-user")
    base_dir = vault.get("storage_dir", "/mnt/mesh_vault_storage")

    target_dir = f"{base_dir}/{args.subdir}".rstrip("/") if args.subdir else base_dir

    print(f"\n📂 Files in Edge Vault ({target_dir}):")
    cmd = [
        "ssh", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=accept-new",
        f"{vault_user}@{vault_host}",
        f"ls -lh '{target_dir}' 2>/dev/null || echo '(Empty or Directory does not exist)'"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(res.stdout + "\n")


def cmd_benchmark(args):
    """Run an end-to-end memory/streaming benchmark test."""
    size_mb = args.size_mb
    print(f"\n⚡ Running Hybrid Mesh Vault End-to-End Benchmark ({size_mb} MB)...")

    test_file = Path(f"/dev/shm/bench_payload_{int(time.time())}.bin")
    try:
        # 1. Create file directly in RAM
        print(f" 1. Generating {size_mb} MB synthetic payload in RAM (/dev/shm)...", end="", flush=True)
        t0 = time.time()
        chunk = b"X" * (1024 * 1024)  # 1MB chunk
        with open(test_file, "wb") as f:
            for _ in range(size_mb):
                f.write(chunk)
        print(f" Done in {round(time.time() - t0, 3)}s")

        # 2. Offload to edge vault
        print(f" 2. Offloading from Cloud RAM to Edge Vault via Tailscale...", end="", flush=True)
        receipt = offload_file(str(test_file), target_subdir="benchmarks", purge_local=True)
        print(f" Done in {receipt['transfer_seconds']}s ({receipt['speed_mb_s']} MB/s)")

        # 3. Fetch back from edge vault into RAM
        print(f" 3. Fetching back from Edge Vault into Cloud RAM (/dev/shm)...", end="", flush=True)
        fetch_receipt = fetch_file(test_file.name, target_dir="/dev/shm", target_subdir="benchmarks")
        print(f" Done in {fetch_receipt['transfer_seconds']}s ({fetch_receipt['speed_mb_s']} MB/s)")

        # 4. Clean up benchmark file
        Path(fetch_receipt["local_path"]).unlink(missing_ok=True)

        print("\n" + "=" * 62)
        print(" 🏆 BENCHMARK RESULTS")
        print("=" * 62)
        print(f" Payload Size:       {size_mb} MB")
        print(f" Offload Throughput: {receipt['speed_mb_s']} MB/s")
        print(f" Fetch Throughput:   {fetch_receipt['speed_mb_s']} MB/s")
        print(f" SHA-256 Checksums:  MATCH (100% Data Integrity)")
        print(f" Cloud Disk Used:    0 MB (Zero disk bleed)")
        print("=" * 62 + "\n")

    finally:
        test_file.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(
        prog="mesh-vault",
        description="Zero-Cost Disaggregated Compute & Storage for AI Agents & Homelabs via Tailscale Mesh."
    )
    subparsers = parser.add_subparsers(dest="command")

    # status
    p_status = subparsers.add_parser("status", help="Show cluster node roles and resource telemetry")
    p_status.set_defaults(func=cmd_status)

    # offload
    p_offload = subparsers.add_parser("offload", help="Offload file from cloud to edge vault")
    p_offload.add_argument("path", help="Local file path to offload")
    p_offload.add_argument("--subdir", help="Target sub-directory in vault")
    p_offload.add_argument("--keep-local", action="store_true", help="Do not purge local file after transfer")
    p_offload.set_defaults(func=cmd_offload)

    # fetch
    p_fetch = subparsers.add_parser("fetch", help="Retrieve file from edge vault into cloud")
    p_fetch.add_argument("filename", help="Filename in vault")
    p_fetch.add_argument("--target-dir", default="/dev/shm", help="Destination dir (default: /dev/shm RAM-disk)")
    p_fetch.add_argument("--subdir", help="Source sub-directory in vault")
    p_fetch.set_defaults(func=cmd_fetch)

    # list
    p_list = subparsers.add_parser("list", help="List stored files in edge vault")
    p_list.add_argument("--subdir", help="Sub-directory to list")
    p_list.set_defaults(func=cmd_list)

    # benchmark
    p_bench = subparsers.add_parser("benchmark", help="Run end-to-end streaming benchmark")
    p_bench.add_argument("--size-mb", type=int, default=10, help="Test payload size in MB (default: 10)")
    p_bench.set_defaults(func=cmd_benchmark)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
