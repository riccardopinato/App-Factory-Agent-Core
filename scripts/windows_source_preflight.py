#!/usr/bin/env python3
"""Local, offline, opt-in inventory for AppFactoryAgent source import.

Never imports, executes, uploads, archives, or logs source contents.
This is not a secrets scanner. It must run locally against a user-selected directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ALLOW_EXT = frozenset({".py", ".ps1", ".toml", ".json", ".yaml", ".yml", ".md", ".txt", ".bat", ".cmd"})
EXCLUDE_DIRS = frozenset({
    ".git", ".venv", "venv", "__pycache__", "node_modules", "models", "results",
    "workspaces", "backups", "backup", "secrets", "logs", "dist", "build",
    "cache", ".idea", ".vscode", ".pytest_cache", "output", "artifacts",
})
EXCLUDE_FILE = re.compile(
    r"(^[.]|[.]env\b|password|secret|credential|api[_-]?key|private[_-]?key|"
    r"access[_-]?token|auth[_-]?token|keystore|[.]sqlite|[.]db\b|[.]log\b)",
    re.IGNORECASE,
)
MAX_FILES = 500
MAX_FILE_SIZE = 5 * 1024 * 1024

def inventory(root: Path) -> dict:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Source location must be a directory")
    files, skipped = [], {"excluded": 0, "too_large": 0, "symlink": 0, "unsupported": 0}
    for path in sorted(root.rglob("*"), key=lambda x: x.as_posix()):
        rel = path.relative_to(root)
        if any(part.lower() in EXCLUDE_DIRS or part.startswith(".") for part in rel.parts[:-1]):
            continue
        if path.is_symlink():
            skipped["symlink"] += 1
            continue
        if not path.is_file():
            continue
        if EXCLUDE_FILE.search(path.name) or path.name.startswith("."):
            skipped["excluded"] += 1
            continue
        if path.suffix.lower() not in ALLOW_EXT:
            skipped["unsupported"] += 1
            continue
        size = path.stat().st_size
        if size > MAX_FILE_SIZE:
            skipped["too_large"] += 1
            continue
        if len(files) >= MAX_FILES:
            raise ValueError("Source file count exceeds bounded inventory limit")
        h = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                h.update(chunk)
        files.append({"relative_path": rel.as_posix(), "sha256": h.hexdigest(), "bytes": size})
    return {
        "schema_version": 1,
        "authority": "LOCAL_READ_ONLY_MANIFEST",
        "source_imported": False,
        "secrets_scanned": False,
        "requires_user_review": True,
        "files": files,
        "skipped_counts": skipped,
        "warnings": [
            "Manifest hashes do not prove code safety, license, completeness or functional tests.",
            "Never commit private paths, tokens, SQLite databases, model weights or personal logs.",
            "This tool never copies local code or connects to GitHub.",
        ],
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True, help="Directory of locally owned source")
    args = parser.parse_args()
    print(json.dumps(inventory(args.root), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
