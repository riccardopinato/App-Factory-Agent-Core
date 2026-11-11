#!/usr/bin/env python3
"""Snapshot deterministico e consultivo delle baseline GitHub pubbliche.
Non modifica Product Bible, Roadmap, Master, codice, CAP o Golden.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "automation" / "SOURCES.json"
STATE = ROOT / "docs" / "AUTO_CONTEXT.json"
REPORT = ROOT / "docs" / "AUTO_CONTEXT.md"

def stable_json(value):
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

def report_text(payload):
    lines = [
        "# Baseline monitorate — snapshot automatico",
        "",
        "> Generato da `scripts/sync_context.py`. Raccoglie solo commit GitHub; NON certifica codice, CI, sicurezza, provider, dispositivo o pubblicazione.",
        "",
    ]
    items = payload["sources"]
    if not items:
        lines.extend(["**In attesa della prima esecuzione autorizzata del workflow.**", ""])
    else:
        lines.extend(["| Repository | Utilizzo | Branch | SHA | Data commit (UTC) |", "|---|---|---|---|---|"])
        for row in items:
            u = "https://github.com/" + row["repository"]
            sha = row["sha"]
            lines.append(f'| [{row["repository"]}]({u}) | {row["purpose"]} | `{row["branch"]}` | [`{sha[:12]}`]({u}/commit/{sha}) | {row["commit_date"]} |')
        lines.append("")
        lines.append("I cambiamenti indicano nuovi commit, non modifiche automaticamente approvate o importate nei moduli.")
        lines.append("")
    lines.extend([
        "## Vincoli di aggiornamento",
        "",
        "- Documenti narrativi e codice non sono riscritti da questa automazione; il riepilogo segnala revisioni upstream da riesaminare.",
        "- Lo stato di questo repository non viene ricopiato qui per evitare cicli di aggiornamento tra agenti.",
        "- In caso di API non disponibili, lo script fallisce senza sovrascrivere prove precedenti.",
        "- La PR creata dal workflow richiede i normali gate; un branch automatico non è una release.",
        "",
    ])
    return "\n".join(lines)

def get_json(url):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "AppFactory-Context-Sync/1.0"}
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)

def build_state(config):
    rows = []
    for item in config["repositories"]:
        repo = item["full_name"]
        metadata = get_json("https://api.github.com/repos/" + repo)
        branch = metadata["default_branch"]
        commit = get_json("https://api.github.com/repos/" + repo + "/commits/" + branch)
        sha = commit["sha"]
        date = commit["commit"]["committer"]["date"]
        if len(sha) != 40 or not all(c in "0123456789abcdef" for c in sha):
            raise ValueError("Invalid GitHub commit SHA for " + repo)
        rows.append({"repository": repo, "purpose": item["purpose"], "branch": branch,
                     "sha": sha, "commit_date": date})
    return {"schema": 1, "sources": sorted(rows, key=lambda r: r["repository"])}

def validate_files():
    config = json.loads(SOURCES.read_text(encoding="utf-8"))
    if config.get("schema") != 1 or not isinstance(config.get("repositories"), list):
        raise ValueError("Invalid automation/SOURCES.json")
    names = [item["full_name"] for item in config["repositories"]]
    if len(names) != len(set(names)) or not names or any("/" not in n for n in names):
        raise ValueError("Missing or duplicate repository name")
    data = json.loads(STATE.read_text(encoding="utf-8"))
    if data.get("schema") != 1 or not isinstance(data.get("sources"), list):
        raise ValueError("Invalid docs/AUTO_CONTEXT.json")
    reported = REPORT.read_text(encoding="utf-8")
    if reported != report_text(data):
        raise ValueError("Markdown snapshot drift; regenerate with --write")
    if data["sources"] and sorted(n["repository"] for n in data["sources"]) != sorted(names):
        raise ValueError("Snapshot sources do not match tracked configuration")

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="Fetch only public GitHub metadata")
    group.add_argument("--check", action="store_true", help="Offline validation")
    args = parser.parse_args()
    if args.check:
        validate_files()
        print("CONTEXT_SNAPSHOT_CHECK_PASS")
        return
    config = json.loads(SOURCES.read_text(encoding="utf-8"))
    data = build_state(config)
    json_text = stable_json(data)
    md_text = report_text(data)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json_text, encoding="utf-8")
    REPORT.write_text(md_text, encoding="utf-8")
    validate_files()
    print("CONTEXT_SNAPSHOT_WRITE_PASS")

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print("CONTEXT_SNAPSHOT_BLOCKED: " + str(exc), file=sys.stderr)
        sys.exit(1)
