"""Negative/positive offline fixtures for the optional AI efficiency pilot."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.agent_efficiency import (
    EfficiencyDenied, EphemeralExactCache, build_pybreaker,
    compare_output, compress_document_candidate, convert_local_document,
    exact_cache_key, guarded_idempotent_call, model_route,
    plan_rtk_oss, read_scoped_memory,
)

SHA = "a" * 40
SHA_B = "b" * 40
DIGEST = hashlib.sha256(b"unchanged document").hexdigest()


class FakeConverter:
    def __init__(self, output="safe markdown"):
        self.output = output
        self.calls = []

    def convert(self, path):
        self.calls.append(path)
        return type("Result", (), {"text_content": self.output})()


class FakeBreaker:
    def __init__(self, fail_max=3, reset_timeout=60):
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self.calls = 0

    def call(self, fn, *args, **kwargs):
        self.calls += 1
        return fn(*args, **kwargs)


class FakeMemory:
    def __init__(self, results):
        self.results = results
        self.received = None

    def search(self, **kwargs):
        self.received = kwargs
        return {"results": self.results}


class AgentEfficiencyTests(unittest.TestCase):

    def test_rtk_requires_opt_in_and_oss_edition(self):
        with self.assertRaises(EfficiencyDenied):
            plan_rtk_oss("git_status")
        with self.assertRaises(EfficiencyDenied):
            plan_rtk_oss("git_status", allowed=True, edition="full")
        with self.assertRaises(EfficiencyDenied):
            plan_rtk_oss("git_push", allowed=True)
        x = plan_rtk_oss("git_status", allowed=True)
        self.assertEqual(x["argv"], ("rtk", "git", "status", "--short"))
        self.assertFalse(x["executes"])
        self.assertTrue(x["must_preserve_raw_log"])

    def test_output_reduction_not_a_cost_or_semantic_claim(self):
        x = compare_output("A\n" * 100, "A\n", raw_exit=0, filtered_exit=0)
        self.assertEqual(x["status"], "BYTE_REDUCTION_CANDIDATE")
        self.assertEqual(x["reduction_percent"], 99.0)
        self.assertFalse(x["token_cost_verified"])
        self.assertFalse(x["semantic_equivalence_verified"])

    def test_rtk_error_or_truncation_fails_closed(self):
        for status in (1, 137):
            x = compare_output("stack traceback\n", "failed\n",
                               raw_exit=status, filtered_exit=status)
            self.assertEqual(x["status"], "RAW_REQUIRED")
            self.assertFalse(x["publish_filtered"])
        self.assertEqual(compare_output("short", "longer", raw_exit=0,
                                        filtered_exit=0)["status"], "RAW_REQUIRED")
        self.assertEqual(compare_output("a", "b", raw_exit=0,
                                        filtered_exit=1)["status"], "RAW_REQUIRED")

    def test_document_needs_isolated_approval(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / "note.pdf"
            p.write_bytes(b"synthetic PDF fixture")
            with self.assertRaises(EfficiencyDenied):
                convert_local_document(p, root=root, converter=FakeConverter())
            with self.assertRaises(EfficiencyDenied):
                convert_local_document(p, root=root, approved=True, converter=FakeConverter())

    def test_document_converts_with_injected_converter_and_content_hash(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / "note.pdf"
            p.write_bytes(b"synthetic PDF fixture")
            f = FakeConverter("# Extracted content")
            result = convert_local_document(p, root=root, approved=True,
                                            network_isolated=True, converter=f)
            self.assertEqual(result["text"], "# Extracted content")
            self.assertEqual(result["source_sha256"], hashlib.sha256(p.read_bytes()).hexdigest())
            self.assertFalse(result["conversion_verified"])
            self.assertEqual(len(f.calls), 1)

    def test_document_rejects_path_escape_and_unsupported_format(self):
        with tempfile.TemporaryDirectory() as root:
            basedir = Path(root) / "approved"
            basedir.mkdir()
            external = Path(root) / "outside.pdf"
            external.write_text("x")
            (basedir / "data.exe").write_text("x")
            for p in (external, basedir / "data.exe"):
                with self.assertRaises(EfficiencyDenied):
                    convert_local_document(p, root=basedir, approved=True,
                                           network_isolated=True, converter=FakeConverter())
            pointer = basedir / "alias.pdf"
            try:
                pointer.symlink_to(external)
            except OSError:
                return
            with self.assertRaises(EfficiencyDenied):
                convert_local_document(pointer, root=basedir, approved=True,
                                       network_isolated=True, converter=FakeConverter())

    def test_document_limits_prevent_oversized_inputs_and_outputs(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / "report.html"
            p.write_text("some body")
            with self.assertRaises(EfficiencyDenied):
                convert_local_document(p, root=root, approved=True,
                                       network_isolated=True, converter=FakeConverter(),
                                       max_file_bytes=2)
            with self.assertRaises(EfficiencyDenied):
                convert_local_document(p, root=root, approved=True,
                                       network_isolated=True, converter=FakeConverter("too long"),
                                       max_output_bytes=3)

    def test_pybreaker_builder_opt_in_and_budgets(self):
        with self.assertRaises(EfficiencyDenied):
            build_pybreaker(factory=FakeBreaker)
        with self.assertRaises(EfficiencyDenied):
            build_pybreaker(enabled=True, fail_max=0, factory=FakeBreaker)
        with self.assertRaises(EfficiencyDenied):
            build_pybreaker(enabled=True, reset_timeout=1, factory=FakeBreaker)
        b = build_pybreaker(enabled=True, fail_max=2, reset_timeout=90, factory=FakeBreaker)
        self.assertEqual((b.fail_max, b.reset_timeout), (2, 90))

    def test_circuit_braker_cannot_execute_unapproved_or_nonidempotent(self):
        b = FakeBreaker()
        with self.assertRaises(EfficiencyDenied):
            guarded_idempotent_call(b, lambda: 1, idempotent=True)
        with self.assertRaises(EfficiencyDenied):
            guarded_idempotent_call(b, lambda: 1, approved=True)
        self.assertEqual(b.calls, 0)
        self.assertEqual(guarded_idempotent_call(b, lambda x: x + 1, 2,
                                                approved=True, idempotent=True), 3)
        self.assertEqual(b.calls, 1)

    def key(self, **overrides):
        opts = dict(tenant="research", repository="owner/repo", source_sha=SHA,
                    task_type="static_document_extract", model="local-v1",
                    prompt_revision="prompt-1", input_sha256=DIGEST)
        opts.update(overrides)
        return exact_cache_key(**opts)

    def test_cache_is_exact_keyed_source_and_tenant_scoped(self):
        base = self.key()
        self.assertEqual(len(base), 64)
        for k in (self.key(tenant="other"), self.key(repository="owner/other"),
                  self.key(source_sha=SHA_B), self.key(prompt_revision="p2"),
                  self.key(model="local-v2")):
            self.assertNotEqual(base, k)

    def test_cache_denies_dynamic_and_security_outputs(self):
        for t in ("security_review", "release", "source_certification", "live_github_state"):
            with self.assertRaises(EfficiencyDenied):
                self.key(task_type=t)
        with self.assertRaises(EfficiencyDenied):
            self.key(input_sha256="broken")
        with self.assertRaises(EfficiencyDenied):
            self.key(source_sha="branch-main")

    def test_cache_ttl_and_eviction(self):
        now = [0.0]
        c = EphemeralExactCache(max_entries=2, ttl_seconds=10, clock=lambda: now[0])
        a, b, d = self.key(), self.key(model="other"), self.key(model="third")
        c.put(a, "one")
        self.assertEqual(c.get(a), "one")
        c.put(b, "two")
        c.put(d, "three")
        self.assertIsNone(c.get(a))
        self.assertEqual(c.get(d), "three")
        now[0] = 11
        self.assertIsNone(c.get(b))
        self.assertIsNone(c.get(d))

    def test_scoped_memory_filters_cross_tenant_source_and_unproven(self):
        correct = {"memory": "Existing helper", "metadata": {
            "tenant": "t", "repository": "owner/repo", "source_sha": SHA,
            "source_url": "https://github.com/owner/repo/blob/" + SHA + "/README.md"}}
        incorrect = [
            {"memory": "malicious", "metadata": dict(correct["metadata"], tenant="other")},
            {"memory": "stale", "metadata": dict(correct["metadata"], source_sha=SHA_B)},
            {"memory": "wrong repo", "metadata": dict(correct["metadata"], repository="other/repo")},
            {"memory": "no provenance", "metadata": {"tenant": "t", "repository": "owner/repo", "source_sha": SHA}},
            {"memory": "bad link", "metadata": dict(correct["metadata"], source_url="https://example.com")},
        ]
        client = FakeMemory(incorrect + [correct])
        result = read_scoped_memory(client, query="notes", tenant="t",
                                    repository="owner/repo", source_sha=SHA,
                                    max_results=10)
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0]["authoritative"])
        self.assertFalse(result[0]["write_permitted"])
        self.assertEqual(client.received["user_id"], "t")

    def test_scoped_memory_does_not_write_or_trust_blank_provenance(self):
        client = FakeMemory([{"memory": "uncited", "metadata": {}}])
        self.assertEqual(read_scoped_memory(client, query="x", tenant="t",
                                           repository="owner/repo", source_sha=SHA), [])
        with self.assertRaises(EfficiencyDenied):
            read_scoped_memory(client, query="", tenant="t",
                               repository="owner/repo", source_sha=SHA)

    def test_model_routes_are_local_first_and_critical_human(self):
        self.assertEqual(model_route("log_summary")["route"], "LOCAL")
        self.assertEqual(model_route("code_draft")["route"], "LOCAL")
        self.assertEqual(model_route("security_review", remote_approved=True,
                                     remote_budget_eur=100)["route"], "HUMAN_REVIEW")
        self.assertEqual(model_route("new_scope")["route"], "HUMAN_REVIEW")
        self.assertEqual(model_route("log_summary", local_available=False)["route"], "BLOCKED")
        self.assertEqual(model_route("log_summary", local_available=False,
                                     remote_approved=True, remote_budget_eur=0)["route"], "BLOCKED")
        self.assertEqual(model_route("log_summary", local_available=False,
                                     remote_approved=True, remote_budget_eur=2)["route"], "REMOTE_APPROVED")

    def test_semantic_compression_is_never_source_of_truth(self):
        with self.assertRaises(EfficiencyDenied):
            compress_document_candidate("the data", kind="public_document",
                                        approved=False, compressor=lambda x: "data")
        with self.assertRaises(EfficiencyDenied):
            compress_document_candidate("CURRENT.yaml is normative",
                                        kind="public_document", approved=True,
                                        compressor=lambda x: "normative")
        with self.assertRaises(EfficiencyDenied):
            compress_document_candidate("stuff", kind="program_code", approved=True,
                                        compressor=lambda x: "x")
        result = compress_document_candidate("A long public explanation.",
                                              kind="public_research", approved=True,
                                              compressor=lambda _: "A short summary")
        self.assertFalse(result["may_replace_source"])
        self.assertFalse(result["validated_facts"])
        self.assertTrue(result["requires_semantic_eval"])

    def test_compressor_rejects_empty_or_longer_outputs(self):
        for invalid in ("", "Too long " * 10):
            with self.assertRaises(EfficiencyDenied):
                compress_document_candidate("original", kind="public_research",
                                            approved=True, compressor=lambda _: invalid)


if __name__ == "__main__":
    unittest.main()
