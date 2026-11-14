# X10-008 Windows private source import precheck v0.1 (report-only)

## Scope
No owner PowerShell required for this development step. This PR **does not** collect installed Windows files or original ZIPs, does not create or write to a private repository and does not activate Autopilot or AppLab jobs.

`scripts/windows_import_admission.py::evaluate_private_source_candidate(receipt, current_factory_sha=...)` operates on the **reported output** of the already existing `x10_windows_autopilot_receipt.py`:
- compares only the strict allowlisted v0.6.0 source fingerprints recorded in the X10-008/015 reconciliation documentation (two mandatory Python files, one optional PowerShell upgrade file);
- requires owner-PC **report-only** authority, explicit limited secret-scanning scope and no runtime/import success claims;
- rejects wrong hashes/sizes, unknown paths, malformed reports and false attestation;
- identifies historical Factory SHA drift separately from actual source hash mismatch;
- returns `OWNER_PRIVATE_REVIEW_REQUIRED` at best, never `IMPORTED`, `CERTIFIED`, `SIGNED_APPROVAL` or `RUNNER_VERIFIED`. No raw source, logs, secrets or local paths are returned.

## Test
`python3 -m unittest discover -s tests -p 'test_windows_import_admission.py' -v`. All fixtures use fake local reports, no external file or queue.

## What still requires the owner machine / explicit action
1. Inventory the **actual installed version** (which may differ from the documented ZIP); compare hashes without disclosing source code publicly.
2. Independently review and run full secret/license provenance checks **on private material**; a regex scan is not sufficient.
3. Choose an authorized private canonical source repository and import only sanitized allowlisted source, with exact SHA and owner review.
4. Shadow-reconcile the local SQLite queue against existing AppLab operations and idempotency keys; stop the old writer before enabling any new writer. Never delete old SQLite until backup/restore and replay are confirmed.
5. Execute authorized two-repo pilots and crash/recovery with exact worker receipts before X10-015 admission.

Factory baseline: `App-Factory-Core@c5adc147046beb7024629466d10eeb799c3c2619` Master v27/Golden Index v29. This precheck is **not** an authority source and cannot approve work.
