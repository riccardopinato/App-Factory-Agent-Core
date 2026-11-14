#!/usr/bin/env python3
"""X10-008: admission review of a *reported* Windows source manifest.

Never reads owner files, archives, models, SQLite, environment, or credentials.
Never uploads code or enables Windows Autopilot / AppLab queue. Outputs only
whether reported hashes match the documented v0.6.0 source package lineage.
Independent private manual review remains mandatory.
"""
from __future__ import annotations

import re
from typing import Any

SHA256 = re.compile(r"^[0-9a-f]{64}$")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
EXPECTED = {
    "app_factory_autopilot.py": {
        "sha256": "035421b5dd8e05ebfd7b2d1297b941782a21601d31fe6bc945854e68bb2988a2",
        "bytes": 58338,
    },
    "test_autopilot.py": {
        "sha256": "e0221f3465d7603945f8330108b6f1a608cc9aad6bf6001c8a75a7b814497b80",
        "bytes": 24934,
    },
    "upgrade_autopilot_v060.ps1": {
        "sha256": "a41f20e3ef79d51f62d8ff1a239b84fc27d556b8c5bb7b41b49acfb2e3e28b28",
        "bytes": 4892,
    },
}
MANDATORY = frozenset({"app_factory_autopilot.py", "test_autopilot.py"})
MAX_RECEIPT_FILES = 3
REPORT_TYPE = "X10_WINDOWS_AUTOPILOT_OBSERVATION"


def evaluate_private_source_candidate(
    receipt: dict[str, Any], *, current_factory_sha: str,
) -> dict[str, Any]:
    """Compare owner-report hashes against a **trusted** pinned package manifest.

    No operation receives higher authority than REPORT_ONLY. A match is not
    proof of current Windows installation, safety, license, provenance or
    independent scan. This function is fit for a private-review checklist only.
    """
    problems: list[str] = []
    if not isinstance(current_factory_sha, str) or SHA40.fullmatch(current_factory_sha) is None:
        raise ValueError("TRUSTED_FACTORY_SHA_REQUIRED")
    if not isinstance(receipt, dict) or type(receipt.get("schema_version")) is not int or receipt["schema_version"] != 1 or receipt.get("record_type") != REPORT_TYPE:
        raise ValueError("SOURCE_RECEIPT_SCHEMA_INVALID")
    if receipt.get("authority") != "OWNER_PC_REPORT_ONLY":
        problems.append("SOURCE_RECEIPT_AUTHORITY_INVALID")
    files = receipt.get("source_files")
    if not isinstance(files, dict) or len(files) > MAX_RECEIPT_FILES:
        raise ValueError("SOURCE_FILE_SET_INVALID")
    if not MANDATORY.issubset(files):
        problems.append("REQUIRED_SOURCE_FILES_MISSING")
    for name, metadata in files.items():
        if name not in EXPECTED or not isinstance(metadata, dict) or set(metadata) != {"sha256", "bytes"}:
            problems.append("UNEXPECTED_OR_INVALID_SOURCE_FILE")
            continue
        expected = EXPECTED[name]
        if (not isinstance(metadata.get("sha256"), str)
                or SHA256.fullmatch(metadata["sha256"]) is None
                or type(metadata.get("bytes")) is not int
                or metadata["bytes"] < 0
                or metadata != expected):
            problems.append("SOURCE_LINEAGE_HASH_MISMATCH")
    reported_problems = receipt.get("source_problems")
    if not isinstance(reported_problems, list) or len(reported_problems) > 32:
        problems.append("SOURCE_SCAN_REPORT_MALFORMED")
    elif reported_problems:
        problems.append("SOURCE_SCAN_REPORTED_PROBLEMS")
    if receipt.get("secret_scan_scope") != "LIMITED_REGEX_ONLY_MANUAL_REVIEW_REQUIRED":
        problems.append("SOURCE_SCAN_SCOPE_UNTRUSTED")
    if receipt.get("source_scope") != "X10-008_LOCAL_SOURCE_INVENTORY_NOT_CANONICAL_IMPORT":
        problems.append("SOURCE_SCOPE_INVALID")
    if receipt.get("no_main_or_queue_changes_performed") is not True:
        problems.append("SOURCE_MUTATION_STATUS_UNTRUSTED")
    if any(receipt.get(flag) is not False for flag in (
        "app_lab_backend_connected", "signed_control_plane_approval_verified",
        "crash_recovery_observed", "second_repository_pilot_verified",
        "x10_008_complete", "x10_015_complete",
    )):
        problems.append("PREMATURE_RUNTIME_ATTESTATION")
    reported_factory = receipt.get("factory_baseline_sha")
    if not isinstance(reported_factory, str) or SHA40.fullmatch(reported_factory) is None:
        problems.append("SOURCE_FACTORY_SHA_UNVERIFIED")
    elif reported_factory != current_factory_sha:
        # Expected for 2026-11-13 receipt: old Factory hash is not a blocker
        # for *manifest review*, but must not be treated as current authority.
        problems.append("SOURCE_FACTORY_BASELINE_DRIFT")
    hard_blockers = [p for p in problems if p != "SOURCE_FACTORY_BASELINE_DRIFT"]
    return {
        "schema_version": 1,
        "record_type": "X10_WINDOWS_PRIVATE_IMPORT_PRECHECK",
        "authority": "REPORT_ONLY",
        "source_lineage": "V060_MATCHES_DECLARED_PACKAGE" if not hard_blockers else "NOT_ADMITTED",
        "state": "OWNER_PRIVATE_REVIEW_REQUIRED" if not hard_blockers else "BLOCKED",
        "blockers": sorted(set(problems)),
        "source_files_seen": sorted(files),
        "source_files_bytes_verified_against_local_machine": False,
        "independent_secret_scan_verified": False,
        "license_verified": False,
        "private_source_imported": False,
        "windows_runner_verified": False,
        "applab_job_admitted": False,
        "runtime_verified": False,
        "next_action_authorized": False,
    }
