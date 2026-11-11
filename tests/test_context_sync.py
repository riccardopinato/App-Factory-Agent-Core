import json
import unittest
from pathlib import Path
from scripts.sync_context import report_text, stable_json, ROOT

class ContextSnapshotTests(unittest.TestCase):
    def test_deterministic_md(self):
        payload = {"schema": 1, "sources": [{"repository": "x/y", "purpose": "reference", "branch": "main", "sha": "a" * 40, "commit_date": "2026-01-01T00:00:00Z"}]}
        self.assertEqual(report_text(payload), report_text(payload))
        self.assertIn("NON certifica", report_text(payload))
    def test_bootstrap_does_not_claim_verified(self):
        text = report_text({"schema": 1, "sources": []})
        self.assertIn("prima esecuzione", text)
    def test_repo_does_not_track_self(self):
        cfg = json.loads((ROOT / "automation" / "SOURCES.json").read_text(encoding="utf-8"))
        own = Path.cwd().name
        self.assertNotIn("riccardopinato/" + own, [r["full_name"] for r in cfg["repositories"]])
    def test_json_stable(self):
        self.assertEqual(stable_json({"b":2, "a":1}), '{\n  "a": 1,\n  "b": 2\n}\n')

if __name__ == "__main__":
    unittest.main()
