"""Real upstream AppLab durable-store integration: hermetic, pinned, no network.

Only runs when APPLAB_CHECKOUT is supplied by the dedicated read-only CI job.
No user Windows device or real AppLab operation is modified.
"""
from pathlib import Path
import os
import sys
import tempfile
import unittest

from scripts.factory_readonly_gateway import FactoryReadOnlyGateway, StatusGatewayError

APPLAB_CHECKOUT = os.environ.get("APPLAB_CHECKOUT")
REPO = "riccardopinato/AppLab"
SHA = "b" * 40


@unittest.skipUnless(APPLAB_CHECKOUT, "Pinned AppLab checkout not provided")
class ActualAppLabStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not APPLAB_CHECKOUT:
            return
        root = Path(APPLAB_CHECKOUT).resolve()
        if not (root / "scripts" / "durable_store_v54b.py").is_file():
            raise AssertionError("Pinned AppLab durable store missing")
        sys.path.insert(0, str(root / "scripts"))
        from durable_store_v54b import SQLiteShadowStore
        from durable_brain_v54a import operation_queue_key, operation_idempotency_key
        cls.store_cls = SQLiteShadowStore
        cls.queue_key = staticmethod(operation_queue_key)
        cls.idempotency_key = staticmethod(operation_idempotency_key)

    def test_persisted_real_operation_read_and_scope_refusal(self):
        with tempfile.TemporaryDirectory() as path:
            with self.store_cls(Path(path) / "gateway-test.sqlite3") as store:
                data = {
                    "schema_version": 1, "record_type": "APPLAB_OPERATION",
                    "operation_id": "op_factorygateway", "correlation_id": "cor_factorygateway",
                    "operation_class": "VERIFICATION", "analysis_mode": "fast",
                    "repository": REPO, "source_ref": "main",
                    "resolved_sha": SHA, "applab_sha": "a" * 40,
                    "priority": 100, "state": "QUEUED",
                    "authority": "ORCHESTRATION_ONLY",
                    "request_text": "DO NOT LEAK",
                }
                data["queue_key"] = self.queue_key(data)
                data["idempotency_key"] = self.idempotency_key(data)
                self.assertEqual(store.put_operation(data)["status"], "INSERTED")

                def never_read_github(repo):
                    raise AssertionError("Gateway operation reader must not call Github")
                gateway = FactoryReadOnlyGateway(
                    allowed_repositories=[REPO], github_head_reader=never_read_github,
                    applab_store=store)
                actual = gateway.operation_status(
                    "op_factorygateway", repository=REPO, source_sha=SHA)
                self.assertEqual(actual["applab_state"], "QUEUED")
                self.assertEqual(actual["operation_id"], "op_factorygateway")
                self.assertFalse(actual["runtime_verified"])
                self.assertFalse(actual["ci_verified"])
                self.assertNotIn("DO NOT LEAK", str(actual))
                with self.assertRaisesRegex(StatusGatewayError, "SOURCE_MISMATCH"):
                    gateway.operation_status(
                        "op_factorygateway", repository=REPO, source_sha="c" * 40)
                with self.assertRaisesRegex(StatusGatewayError, "APPLAB_READ_FAILED"):
                    gateway.operation_status(
                        "op_nonexistent", repository=REPO, source_sha=SHA)


if __name__ == "__main__":
    unittest.main()
