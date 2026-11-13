#!/usr/bin/env python3
"""X10-008/015 read-only Windows source inventory + scoped runtime evidence.

NO upload, no queue mutations, no subprocess shell, no AppLab dispatch.
Run on the owner PC, review output before transferring anything private.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

FILES = ('app_factory_autopilot.py', 'test_autopilot.py', 'upgrade_autopilot_v060.ps1')
DENY = (
    re.compile(rb'gh[pousr]_[A-Za-z0-9]{20,}'),
    re.compile(rb'github_pat_[A-Za-z0-9_]{24,}'),
    re.compile(rb'sk-[A-Za-z0-9_-]{24,}'),
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(rb'(?i)(?:api[_-]?key|token|password|secret)\s*[=:]\s*["\x27][A-Za-z0-9+/=_-]{24,}'),
)
SHA = re.compile(r'^[a-f0-9]{40}$')
REPO = re.compile(r'^riccardopinato/[A-Za-z0-9_.-]+$')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_inventory(root: Path):
    inventory, errors, contents = {}, [], {}
    for name in FILES:
        f = root / name
        if not f.is_file() or f.is_symlink() or f.stat().st_size > 200_000:
            errors.append('SOURCE_MISSING_OR_UNSAFE:' + name)
            continue
        data = f.read_bytes()
        if b'\0' in data or any(regex.search(data) for regex in DENY):
            errors.append('SOURCE_REQUIRES_PRIVATE_REVIEW:' + name)
            continue
        inventory[name] = {'sha256': digest(data), 'bytes': len(data)}
        contents[name] = data
    return inventory, errors, contents


def local_jobs(root: Path):
    db = root / 'autopilot-state' / 'queue.sqlite3'
    if not db.exists():
        return {'state': 'NOT_AVAILABLE', 'jobs': []}
    jobs = []
    try:
        with sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True, timeout=5) as con:
            for row in con.execute('SELECT repo, issue, status, pr, pr_sha, attempts, ci_repairs FROM jobs ORDER BY created_at DESC LIMIT 25'):
                repo, issue, status, pr, sha, attempts, repairs = row
                if not (isinstance(repo, str) and REPO.fullmatch(repo)):
                    continue
                jobs.append({'repo': repo, 'issue': issue, 'status': status,
                             'pr': pr, 'pr_head_sha': sha if isinstance(sha, str) and SHA.fullmatch(sha) else None,
                             'attempts': attempts, 'ci_repairs': repairs})
    except (OSError, sqlite3.Error) as exc:
        return {'state': 'READ_FAILED', 'error_kind': type(exc).__name__, 'jobs': []}
    return {'state': 'READ_ONLY_LOCAL_UNVERIFIED', 'jobs': jobs}


def gh_read_json(*args):
    kwargs = {'capture_output': True, 'text': True, 'encoding': 'utf-8', 'errors': 'replace',
              'timeout': 30, 'shell': False}
    if sys.platform == 'win32':
        kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    p = subprocess.run(['gh', 'api', *args], **kwargs)
    if p.returncode:
        raise RuntimeError('GITHUB_READ_UNAVAILABLE')
    return json.loads(p.stdout)


def remote_evidence(jobs):
    results = []
    for job in jobs[:10]:
        if not job['pr'] or not job['pr_head_sha']:
            continue
        repo, number, sha = job['repo'], job['pr'], job['pr_head_sha']
        result = {'repo': repo, 'pr': number, 'expected_head_sha': sha,
                  'pr_exact_head': False, 'draft': False, 'ci_exact_head_pass': False}
        try:
            pr = gh_read_json(f'repos/{repo}/pulls/{int(number)}')
            result['pr_exact_head'] = pr.get('head', {}).get('sha') == sha
            result['draft'] = pr.get('draft') is True and pr.get('state') == 'open'
            result['pr_url'] = pr.get('html_url') if result['pr_exact_head'] else None
            if result['pr_exact_head'] and result['draft']:
                runs = gh_read_json(f'repos/{repo}/actions/runs?head_sha={sha}&per_page=100')
                result['ci_exact_head_pass'] = any(
                    run.get('head_sha') == sha and run.get('status') == 'completed' and
                    run.get('conclusion') == 'success' and run.get('event') == 'pull_request'
                    for run in runs.get('workflow_runs', [])
                )
        except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired):
            result['remote_read'] = 'UNAVAILABLE'
        results.append(result)
    return results


def make_receipt(root: Path, check_github: bool = False, export: Path | None = None):
    inventory, problems, contents = source_inventory(root)
    jobs = local_jobs(root)
    receipt = {
        'schema_version': 1,
        'record_type': 'X10_WINDOWS_AUTOPILOT_OBSERVATION',
        'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'authority': 'OWNER_PC_REPORT_ONLY',
        'factory_baseline_sha': 'ee72dbb1b0de2cd71bc4aac42c350853c6915159',
        'source_scope': 'X10-008_LOCAL_SOURCE_INVENTORY_NOT_CANONICAL_IMPORT',
        'source_files': inventory,
        'source_problems': problems,
        'secret_scan_scope': 'LIMITED_REGEX_ONLY_MANUAL_REVIEW_REQUIRED',
        'local_queue': jobs,
        'remote_pr_ci': remote_evidence(jobs['jobs']) if check_github else [],
        'app_lab_backend_connected': False,
        'signed_control_plane_approval_verified': False,
        'crash_recovery_observed': False,
        'second_repository_pilot_verified': False,
        'x10_008_complete': False,
        'x10_015_complete': False,
        'no_main_or_queue_changes_performed': True,
    }
    if export is not None:
        if problems or len(contents) != len(FILES):
            raise ValueError('PRIVATE_EXPORT_BLOCKED_SOURCE_REVIEW_REQUIRED')
        export.parent.mkdir(parents=True, exist_ok=True)
        if export.exists():
            raise FileExistsError('EXPORT_EXISTS_REFUSE_OVERWRITE')
        with zipfile.ZipFile(export, 'x', compression=zipfile.ZIP_DEFLATED) as z:
            for name, data in contents.items():
                z.writestr('source/' + name, data)
            z.writestr('MANIFEST.json', json.dumps({'files': inventory,
                'import_status': 'PRIVATE_REVIEW_REQUIRED',
                'no_tokens_or_state_included': True}, sort_keys=True, indent=2))
        receipt['private_export_sha256'] = digest(export.read_bytes())
    return receipt


def main():
    parser = argparse.ArgumentParser(description='X10-008/015 offline/optional GitHub read-only evidence')
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--github-read-only', action='store_true')
    parser.add_argument('--export-private', type=Path)
    args = parser.parse_args()
    receipt = make_receipt(args.root.expanduser().resolve(), args.github_read_only, args.export_private)
    payload = json.dumps(receipt, indent=2, sort_keys=True) + '\n'
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding='utf-8')
        print('RECEIPT_WRITTEN', args.out.name, 'import=NOT_VERIFIED e2e=NOT_VERIFIED')
    else:
        print(payload)


if __name__ == '__main__':
    main()
