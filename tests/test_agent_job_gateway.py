import copy
import hashlib
import hmac
import json
import pathlib
import unittest
from datetime import datetime, timedelta, timezone

from scripts.agent_job_gateway import canonical, evaluate, job_digest, safe_path

ROOT=pathlib.Path(__file__).resolve().parents[1]
A="a"*40
KEY=b"trusted-review-key-from-external-control-plane-v1"

def job(mode="analyze", paths=None):
    return {
        "schema_version":1,"job_id":"job-00001","idempotency_key":"scope-000000001",
        "target":{"repository":"riccardopinato/World-Days","source_sha":A,
                  "allowed_paths":paths if paths is not None else ["lib"]},
        "mode":mode,"request":{"summary":"Inspect a bounded Dart path, no source modification"},
        "limits":{"timeout_seconds":180,"max_attempts":2},
    }

def policy():
    return {"repositories":["riccardopinato/World-Days"],
            "modes":["analyze","run_tests","propose_diff","prepare_pr"],
            "allowed_paths":["lib","test"]}

def receipt(x, now):
    proof={
      "schema_version":1,"job_sha256":job_digest(x),
      "repository":x["target"]["repository"],"source_sha":x["target"]["source_sha"],
      "mode":x["mode"],"allowed_paths":x["target"]["allowed_paths"],
      "reviewer":"maintainer","review_url":"https://github.com/riccardopinato/World-Days/pull/99",
      "expires_at":(now+timedelta(minutes=15)).isoformat().replace("+00:00","Z"),
    }
    proof["hmac_sha256"]=hmac.new(KEY,canonical(proof),hashlib.sha256).hexdigest()
    return proof

class JobGatewayTests(unittest.TestCase):
    def test_contract_modes_match_existing_schema(self):
        design=json.loads((ROOT/"contracts/job.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(set(design["properties"]["mode"]["enum"]),
                         {"analyze","run_tests","propose_diff","prepare_pr"})

    def test_mandatory_job_id_and_idempotency(self):
        j=job()
        del j["job_id"]
        self.assertEqual(evaluate(j,policy())["reason"],"MISSING_JOB_IDENTITY")
        j=job()
        j["job_id"]="x"
        self.assertEqual(evaluate(j,policy())["reason"],"MISSING_JOB_IDENTITY")
        j=job()
        del j["idempotency_key"]
        self.assertEqual(evaluate(j,policy())["reason"],"MISSING_IDEMPOTENCY_KEY")
        j=job()
        j["idempotency_key"]="short"
        self.assertEqual(evaluate(j,policy())["reason"],"MISSING_IDEMPOTENCY_KEY")

    def test_malformed_input_never_raises(self):
        for bad_mode in ([], {}, 4, None):
            j=job()
            j["mode"]=bad_mode
            self.assertFalse(evaluate(j,policy())["authorized"])
        j=job()
        j["request"]={"summary":None}
        self.assertEqual(evaluate(j,policy())["reason"],"INVALID_REQUEST")
        j=job()
        j["approval"]={"approved":True}
        self.assertEqual(evaluate(j,policy())["reason"],"UNTRUSTED_JOB_APPROVAL")
        j=job()
        j["target"]["unexpected"]={"secret":1}
        self.assertEqual(evaluate(j,policy())["reason"],"UNKNOWN_TARGET_OR_LIMITS")
        j=job()
        j["limits"]["model_token_budget"]=1.5
        self.assertEqual(evaluate(j,policy())["reason"],"BUDGET_EXCEEDED")

    def test_malformed_approval_receipt_never_raises(self):
        now=datetime(2026,11,12,tzinfo=timezone.utc)
        j=job("prepare_pr")
        for field,value,reason in (
            ("review_url",None,"APPROVAL_PROVENANCE_MISSING"),
            ("review_url",77,"APPROVAL_PROVENANCE_MISSING"),
            ("reviewer",[],"APPROVAL_PROVENANCE_MISSING"),
            ("expires_at",123456,"APPROVAL_TIME_INVALID"),
            ("expires_at",None,"APPROVAL_TIME_INVALID"),
        ):
            proof=receipt(j,now)
            proof[field]=value
            self.assertEqual(evaluate(j,policy(),receipt=proof,verifier_key=KEY,now=now)["reason"],reason)

    def test_read_mode_is_admission_not_execution(self):
        decision=evaluate(job(),policy())
        self.assertTrue(decision["authorized"])
        self.assertEqual(decision["state"],"ADMITTED_FOR_ISOLATED_READ")
        self.assertFalse(decision["side_effects_performed"])
        self.assertFalse(decision["runtime_verified"])

    def test_invalid_or_unknown_repo_and_mode(self):
        self.assertFalse(evaluate(job(),{"repositories":[],"modes":["analyze"],"allowed_paths":["lib"]})["authorized"])
        self.assertFalse(evaluate(job("root"),policy())["authorized"])
        j=job()
        j["target"]["source_sha"]="latest"
        self.assertEqual(evaluate(j,policy())["reason"],"INVALID_SHA")

    def test_scope_traversal_and_protected_files(self):
        for p in ("../private",".github/workflows/ci.yml","AGENTS.md",
                  "/etc/passwd","lib\\secret","lib/../safe"):
            self.assertFalse(safe_path(p), p)
            self.assertEqual(evaluate(job(paths=[p]),policy())["authorized"],False,p)
        self.assertEqual(evaluate(job(paths=["assets/file.txt"]),policy())["reason"],"PATH_OUT_OF_SCOPE")

    def test_reject_bad_budget(self):
        j=job()
        j["limits"]["timeout_seconds"]=7200
        self.assertEqual(evaluate(j,policy())["reason"],"BUDGET_EXCEEDED")
        j["limits"]={"timeout_seconds":180,"max_attempts":3}
        self.assertEqual(evaluate(j,policy())["reason"],"BUDGET_EXCEEDED")

    def test_bad_policy_types_and_ambiguous_numbers(self):
        j=job()
        p=policy()
        p["repositories"]="riccardopinato/World-Days"
        self.assertEqual(evaluate(j,p)["reason"],"INVALID_POLICY")
        j["limits"]["timeout_seconds"]=1.9
        self.assertEqual(evaluate(j,policy())["reason"],"BUDGET_EXCEEDED")

    def test_default_denies_writes(self):
        for mode in ("propose_diff","prepare_pr"):
            result=evaluate(job(mode),policy())
            self.assertEqual(result["reason"],"TRUSTED_APPROVAL_REQUIRED")
        self.assertEqual(evaluate(job("prepare_pr",paths=[]),policy())["reason"],"BAD_PATH_SET")

    def test_trusted_scoped_receipt_allows_proposal_only(self):
        now=datetime(2026,11,12,0,0,0,tzinfo=timezone.utc)
        j=job("propose_diff",paths=["lib/main.dart"])
        proof=receipt(j,now)
        d=evaluate(j,policy(),receipt=proof,verifier_key=KEY,now=now)
        self.assertTrue(d["authorized"])
        self.assertEqual(d["state"],"ADMITTED_FOR_SCOPED_PROPOSAL")
        self.assertFalse(d["side_effects_performed"])
        self.assertFalse(d["runtime_verified"])
        self.assertIn("independent review and required CI",d["requires_runner_checks"])

    def test_receipt_is_bound_to_job_and_sha(self):
        now=datetime(2026,11,12,tzinfo=timezone.utc)
        j=job("prepare_pr",paths=["lib/main.dart"])
        proof=receipt(j,now)
        spoof=copy.deepcopy(j);spoof["target"]["source_sha"]="b"*40
        self.assertEqual(evaluate(spoof,policy(),receipt=proof,verifier_key=KEY,now=now)["reason"],
                         "APPROVAL_JOB_MISMATCH")
        proof["reviewer"]="other"
        self.assertEqual(evaluate(j,policy(),receipt=proof,verifier_key=KEY,now=now)["reason"],
                         "APPROVAL_SIGNATURE_INVALID")

    def test_expired_or_long_receipt_denied(self):
        now=datetime(2026,11,12,tzinfo=timezone.utc)
        j=job("prepare_pr")
        proof=receipt(j,now)
        expired=now+timedelta(hours=1)
        self.assertEqual(evaluate(j,policy(),receipt=proof,verifier_key=KEY,now=expired)["reason"],
                         "APPROVAL_EXPIRED")
        long=copy.deepcopy(proof)
        long["expires_at"]=(now+timedelta(hours=5)).isoformat().replace("+00:00","Z")
        long["hmac_sha256"]=hmac.new(KEY,canonical({k:v for k,v in long.items() if k!="hmac_sha256"}),hashlib.sha256).hexdigest()
        self.assertEqual(evaluate(j,policy(),receipt=long,verifier_key=KEY,now=now)["reason"],
                         "APPROVAL_TTL_TOO_LONG")

    def test_wrong_key_and_path_mismatch(self):
        now=datetime(2026,11,12,tzinfo=timezone.utc)
        j=job("prepare_pr",paths=["lib/main.dart"])
        proof=receipt(j,now)
        self.assertEqual(evaluate(j,policy(),receipt=proof,verifier_key=b"w"*40,now=now)["reason"],
                         "APPROVAL_SIGNATURE_INVALID")
        proof["allowed_paths"]=["test"]
        self.assertEqual(evaluate(j,policy(),receipt=proof,verifier_key=KEY,now=now)["reason"],
                         "APPROVAL_PATH_MISMATCH")

if __name__=="__main__":
    unittest.main()
