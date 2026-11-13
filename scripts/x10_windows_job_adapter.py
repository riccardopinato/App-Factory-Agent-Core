#!/usr/bin/env python3
"""Translate legacy Autopilot rows to Agent Core X10-010 jobs, without executing.

The Windows SQLite row/issue text is UNTRUSTED. No approval, operation ID,
lease, queue write, PR materialization, dispatch or runtime certification is
created here. Only an external trusted controller may inject policy/receipt.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

try:
    from scripts.agent_job_gateway import evaluate, safe_path
except ModuleNotFoundError:
    from agent_job_gateway import evaluate, safe_path

REPO = re.compile(r'^riccardopinato/[A-Za-z0-9_.-]+$')
SHA = re.compile(r'^[a-f0-9]{40}$')
MODES = {'analyze', 'run_tests', 'propose_diff', 'prepare_pr'}


class LegacyJobInvalid(ValueError):
    pass


def propose_canonical_job(row: dict[str, Any], *, mode: str = 'analyze') -> dict[str, Any]:
    """Produce a job design candidate, not a persisted AppLab operation."""
    if not isinstance(row, dict) or mode not in MODES:
        raise LegacyJobInvalid('INVALID_JOB_MODE')
    repo, number, sha = row.get('repo'), row.get('issue'), row.get('base_sha')
    file, task = row.get('file'), row.get('task')
    if not isinstance(repo, str) or REPO.fullmatch(repo) is None:
        raise LegacyJobInvalid('REPOSITORY_NOT_TRUSTED')
    if type(number) is not int or number < 1 or number > 1_000_000_000:
        raise LegacyJobInvalid('INVALID_ISSUE_ID')
    if not isinstance(sha, str) or SHA.fullmatch(sha) is None:
        raise LegacyJobInvalid('PINNED_SOURCE_SHA_REQUIRED')
    if not isinstance(file, str) or not safe_path(file):
        raise LegacyJobInvalid('UNSAFE_FILE_PATH')
    if not isinstance(task, str) or not task.strip() or len(task) > 1000:
        raise LegacyJobInvalid('INVALID_UNTRUSTED_SUMMARY')
    # Stable across replay; the remote PR SHA must never replace original base SHA.
    name = hashlib.sha256(f'{repo}\0{number}\0{sha}'.encode('utf-8')).hexdigest()
    return {
        'schema_version': 1,
        'job_id': 'x10win-' + name[:32],
        'idempotency_key': 'x10win-' + name,
        'target': {'repository': repo, 'source_sha': sha, 'allowed_paths': [file]},
        'mode': mode,
        'request': {'summary': task, 'issue_url': f'https://github.com/{repo}/issues/{number}'},
        'limits': {'timeout_seconds': 600, 'max_attempts': 2, 'model_token_budget': 4096},
        'approval': {'approved': False, 'reason': 'Local task not independently authorized'},
    }


def evaluate_legacy_candidate(row: dict[str, Any], policy: dict[str, Any], *,
                              mode: str = 'analyze', receipt=None, verifier_key=None) -> dict[str, Any]:
    """Reuse X10-010 gate; never self-sign/approve or dispatch to AppLab."""
    job = propose_canonical_job(row, mode=mode)
    decision = evaluate(job, policy, receipt=receipt, verifier_key=verifier_key)
    return {'job': job, 'decision': decision, 'app_lab_operation_bound': False,
            'writes_performed': False, 'live_worker_verified': False,
            'next_gate': 'TRUSTED_APPLAB_OPERATION_AND_SIGNED_EXTERNAL_APPROVAL'}
