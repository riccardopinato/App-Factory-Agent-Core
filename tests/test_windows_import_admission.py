"""X10-008 source lineage review negative tests; no owner PC access."""
import copy
import unittest

from scripts.windows_import_admission import (
    evaluate_private_source_candidate, EXPECTED,
)

CURRENT = "c5adc147046beb7024629466d10eeb799c3c2619"
OLD = "ee72dbb1b0de2cd71bc4aac42c350853c6915159"


def report():
    return {
        "schema_version": 1,
        "record_type": "X10_WINDOWS_AUTOPILOT_OBSERVATION",
        "authority": "OWNER_PC_REPORT_ONLY",
        "source_scope": "X10-008_LOCAL_SOURCE_INVENTORY_NOT_CANONICAL_IMPORT",
        "source_files": {name: copy.deepcopy(EXPECTED[name])
                         for name in ("app_factory_autopilot.py", "test_autopilot.py")},
        "source_problems": [],
        "secret_scan_scope": "LIMITED_REGEX_ONLY_MANUAL_REVIEW_REQUIRED",
        "factory_baseline_sha": OLD,
        "no_main_or_queue_changes_performed": True,
        "app_lab_backend_connected": False,
        "signed_control_plane_approval_verified": False,
        "crash_recovery_observed": False,
        "second_repository_pilot_verified": False,
        "x10_008_complete": False,
        "x10_015_complete": False,
        "local_queue": {"state": "READ_ONLY_LOCAL_UNVERIFIED",
                        "jobs": [{"repo": "private", "secret": "DO_NOT_PRINT"}]},
    }


class PrivateSourcePrecheckTests(unittest.TestCase):
    def test_declared_known_package_is_only_review_candidate(self):
        out = evaluate_private_source_candidate(report(), current_factory_sha=CURRENT)
        self.assertEqual(out["state"], "OWNER_PRIVATE_REVIEW_REQUIRED")
        self.assertEqual(out["source_lineage"], "V060_MATCHES_DECLARED_PACKAGE")
        self.assertIn("SOURCE_FACTORY_BASELINE_DRIFT", out["blockers"])
        for key in ("private_source_imported", "runtime_verified",
                    "independent_secret_scan_verified", "license_verified",
                    "source_files_bytes_verified_against_local_machine",
                    "next_action_authorized"):
            self.assertFalse(out[key])
        self.assertNotIn("DO_NOT_PRINT", str(out))

    def test_matching_current_factory_clears_only_drift(self):
        r = report()
        r["factory_baseline_sha"] = CURRENT
        out = evaluate_private_source_candidate(r, current_factory_sha=CURRENT)
        self.assertEqual(out["blockers"], [])
        self.assertEqual(out["state"], "OWNER_PRIVATE_REVIEW_REQUIRED")

    def test_mismatched_hash_or_size_blocks(self):
        for field, replacement in [("sha256", "0" * 64), ("bytes", 0),
                                    ("bytes", True)]:
            r = report()
            r["source_files"]["app_factory_autopilot.py"][field] = replacement
            got = evaluate_private_source_candidate(r, current_factory_sha=CURRENT)
            self.assertEqual(got["state"], "BLOCKED")
            self.assertIn("SOURCE_LINEAGE_HASH_MISMATCH", got["blockers"])

    def test_reject_extra_sources_and_missing_source(self):
        r = report()
        r["source_files"]["secrets.json"] = {"sha256": "f" * 64, "bytes": 1}
        self.assertEqual(evaluate_private_source_candidate(r, current_factory_sha=CURRENT)["state"], "BLOCKED")
        del r["source_files"]["secrets.json"]
        del r["source_files"]["test_autopilot.py"]
        out = evaluate_private_source_candidate(r, current_factory_sha=CURRENT)
        self.assertIn("REQUIRED_SOURCE_FILES_MISSING", out["blockers"])

    def test_rejected_local_windows_paths_are_never_echoed(self):
        r = report()
        sensitive = r"C:\\Users\\Owner\\private-client\\credentials.env"
        r["source_files"][sensitive] = {"sha256": "f" * 64, "bytes": 3}
        out = evaluate_private_source_candidate(r, current_factory_sha=CURRENT)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertEqual(out["unrecognized_file_count"], 1)
        self.assertNotIn(sensitive, str(out))
        self.assertNotIn("credentials.env", str(out))
        self.assertEqual(set(out["source_files_seen"]), set(r["source_files"]) - {sensitive})

    def test_source_scan_and_premature_claims_are_refused(self):
        r = report()
        r["source_problems"] = ["SOURCE_REQUIRES_PRIVATE_REVIEW"]
        r["x10_008_complete"] = True
        r["signed_control_plane_approval_verified"] = True
        r["no_main_or_queue_changes_performed"] = False
        out = evaluate_private_source_candidate(r, current_factory_sha=CURRENT)
        self.assertEqual(out["state"], "BLOCKED")
        self.assertIn("SOURCE_SCAN_REPORTED_PROBLEMS", out["blockers"])
        self.assertIn("PREMATURE_RUNTIME_ATTESTATION", out["blockers"])

    def test_no_source_or_bad_factory_authority(self):
        with self.assertRaisesRegex(ValueError, "SCHEMA_INVALID"):
            evaluate_private_source_candidate({}, current_factory_sha=CURRENT)
        with self.assertRaisesRegex(ValueError, "TRUSTED_FACTORY_SHA_REQUIRED"):
            evaluate_private_source_candidate(report(), current_factory_sha="latest")

    def test_optional_upgrader_can_match_if_reported(self):
        r = report()
        r["source_files"]["upgrade_autopilot_v060.ps1"] = dict(EXPECTED["upgrade_autopilot_v060.ps1"])
        out = evaluate_private_source_candidate(r, current_factory_sha=CURRENT)
        self.assertEqual(out["state"], "OWNER_PRIVATE_REVIEW_REQUIRED")
        self.assertFalse(out["private_source_imported"])


if __name__ == "__main__":
    unittest.main()
