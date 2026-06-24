"""Pull SWE-bench-Lite instances + oracle files using only `requests`.

Avoids the `datasets` package (no wheels on py3.14). Uses the HF
datasets-server REST API for rows and GitHub raw for file content at the
buggy base_commit.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

from . import config

ROWS_URL = "https://datasets-server.huggingface.co/rows"
_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)


def _rows(offset: int, length: int) -> list[dict]:
    # HF datasets-server flaps (502/timeout); retry with backoff so a batch
    # pull (which scans the split) doesn't die on a transient blip.
    last = None
    for attempt in range(5):
        try:
            r = requests.get(
                ROWS_URL,
                params={
                    "dataset": config.DATASET,
                    "config": config.CONFIG,
                    "split": config.SPLIT,
                    "offset": offset,
                    "length": length,
                },
                timeout=60,
            )
            r.raise_for_status()
            return [row["row"] for row in r.json().get("rows", [])]
        except requests.RequestException as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise last


# whole split cached per process so a 6-instance pull scans HF once, not 6x
_ALL_ROWS: list[dict] | None = None


def _all_rows() -> list[dict]:
    global _ALL_ROWS
    if _ALL_ROWS is None:
        _ALL_ROWS = list(iter_all())
    return _ALL_ROWS


def iter_all(page: int = 100):
    """Yield every instance row in the split (Lite test = 300)."""
    offset = 0
    while True:
        batch = _rows(offset, page)
        if not batch:
            return
        yield from batch
        offset += len(batch)
        if len(batch) < page:
            return


def list_instances(repo: str | None = None) -> list[str]:
    out = []
    for row in iter_all():
        if repo and row.get("repo") != repo:
            continue
        out.append(row["instance_id"])
    return out


def _gold_files(gold_patch: str) -> list[str]:
    return _FILE_RE.findall(gold_patch)


def _raw_file(repo: str, commit: str, path: str) -> str:
    url = f"https://raw.githubusercontent.com/{repo}/{commit}/{path}"
    r = requests.get(url, timeout=60)
    if r.status_code == 404:
        return ""  # file is created by the patch; no base content
    r.raise_for_status()
    return r.text


def pull(instance_id: str) -> Path:
    """Fetch one instance + its oracle files; write instances/<id>.json."""
    row = next((r for r in _all_rows() if r["instance_id"] == instance_id), None)
    if row is None:
        raise SystemExit(f"instance not found in {config.DATASET}: {instance_id}")

    repo, commit = row["repo"], row["base_commit"]
    files = {p: _raw_file(repo, commit, p) for p in _gold_files(row["patch"])}

    bundle = {
        "instance_id": instance_id,
        "repo": repo,
        "base_commit": commit,
        "problem_statement": row["problem_statement"],
        "oracle_files": files,         # path -> content @ base_commit
        "gold_patch": row["patch"],    # for gold-validate only; never fed to models
    }
    out = config.INSTANCES / f"{instance_id}.json"
    out.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    return out


def load(instance_id: str) -> dict:
    p = config.INSTANCES / f"{instance_id}.json"
    if not p.exists():
        raise SystemExit(f"not pulled yet: {instance_id} (run: pull {instance_id})")
    return json.loads(p.read_text(encoding="utf-8"))
