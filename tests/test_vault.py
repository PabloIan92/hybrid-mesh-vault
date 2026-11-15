#!/usr/bin/env python3
"""
Unit and integration tests for hybrid-mesh-vault.
"""

import unittest
import tempfile
import hashlib
from pathlib import Path

from mesh_vault.core import get_system_metrics, classify_role, NodeRole, load_config
from mesh_vault.offload import calculate_sha256


class TestHybridMeshVault(unittest.TestCase):

    def test_system_metrics(self):
        metrics = get_system_metrics()
        self.assertIn("hostname", metrics)
        self.assertIn("ram", metrics)
        self.assertIn("disk", metrics)
        self.assertGreater(metrics["ram"]["total_gb"], 0)
        self.assertGreater(metrics["disk"]["total_gb"], 0)

    def test_classify_role_compute(self):
        mock_metrics = {
            "ram": {"total_gb": 16.0},
            "disk": {"free_gb": 30.0}
        }
        role = classify_role(mock_metrics)
        self.assertEqual(role, NodeRole.COMPUTE_PRIMARY)

    def test_classify_role_vault(self):
        mock_metrics = {
            "ram": {"total_gb": 4.0},
            "disk": {"free_gb": 450.0}
        }
        role = classify_role(mock_metrics)
        self.assertEqual(role, NodeRole.STORAGE_VAULT)

    def test_classify_role_hybrid(self):
        mock_metrics = {
            "ram": {"total_gb": 8.0},
            "disk": {"free_gb": 100.0}
        }
        role = classify_role(mock_metrics)
        self.assertEqual(role, NodeRole.HYBRID)

    def test_sha256_calculation(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            payload = b"Hello Hybrid Mesh Vault! Deterministic Checksum Test."
            f.write(payload)
            temp_path = Path(f.name)

        try:
            expected_hash = hashlib.sha256(payload).hexdigest()
            computed_hash = calculate_sha256(temp_path)
            self.assertEqual(expected_hash, computed_hash)
        finally:
            temp_path.unlink(missing_ok=True)

    def test_load_config(self):
        cfg = load_config()
        self.assertIn("vault_peer", cfg)
        self.assertIn("safety", cfg)
        self.assertTrue(cfg["safety"]["verify_sha256"])


if __name__ == "__main__":
    unittest.main()
