import unittest
from pathlib import Path


class StructureIntegrityTests(unittest.TestCase):
    def test_phase0_directories_exist(self):
        expected = [
            "agent",
            "server",
            "contracts",
            "infra",
            "docs",
            "web-console",
            "realtime_agent",
        ]
        for item in expected:
            self.assertTrue(Path(item).exists(), f"Missing required path: {item}")

    def test_required_files_exist(self):
        files = [
            "contracts/openapi.yaml",
            "infra/sql/001_initial_schema.sql",
            "docs/CONTRATO_PLATAFORMA_V1.md",
            "docs/TRANSICAO_REALTIME_AGENT_PARA_AGENT.md",
            "server/main.py",
            "server/app/app.py",
            "agent/README.md",
            "web-console/README.md",
        ]
        for f in files:
            self.assertTrue(Path(f).is_file(), f"Missing required file: {f}")


if __name__ == "__main__":
    unittest.main()
