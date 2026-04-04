import json
import re
import unittest
from pathlib import Path


class ContractConsistencyTests(unittest.TestCase):
    def test_all_schema_files_are_valid_json(self):
        schema_dir = Path("contracts/schemas")
        schema_files = list(schema_dir.glob("*.json"))
        self.assertGreater(len(schema_files), 0, "No schema files found")
        for schema_file in schema_files:
            with schema_file.open("r", encoding="utf-8") as f:
                json.load(f)

    def test_openapi_refs_exist(self):
        openapi_path = Path("contracts/openapi.yaml")
        content = openapi_path.read_text(encoding="utf-8")
        refs = re.findall(r"\$ref:\s*'\./schemas/([^']+)'", content)
        self.assertGreater(len(refs), 0, "No schema refs found in OpenAPI")
        for ref in refs:
            self.assertTrue((Path("contracts/schemas") / ref).is_file(), f"Missing schema referenced by OpenAPI: {ref}")


if __name__ == "__main__":
    unittest.main()
