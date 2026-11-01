"""Fetch the DHARMA Tamil epigraphy repositories at pinned commits.

    python -m ezhuthu.corpus.fetch            # clone/checkout every repo in config/dharma.lock.json
    python -m ezhuthu.corpus.fetch --update   # discover repos on GitHub, pin their current HEAD

Discovery lists every ``erc-dharma/tfa-*-epigraphy`` repository (the "Tamil" family of DHARMA
epigraphy repos) through the GitHub API. Each repo is shallow-fetched at exactly one commit into
``data/raw/<repo>`` (gitignored). The lock records repo, commit, licence (as GitHub reports it) and the
number of TEI edition files found at that commit.

Set ``GITHUB_TOKEN`` to raise the GitHub API rate limit; it is only needed for ``--update``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ORG = "erc-dharma"
REPO_RE = re.compile(r"^tfa-.*-epigraphy$")
ROOT = Path(__file__).resolve().parents[3]
LOCK_PATH = ROOT / "config" / "dharma.lock.json"
RAW_DIR = ROOT / "data" / "raw"


def _api(url: str) -> list | dict:
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "ezhuthu-corpus-fetch"})
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def discover() -> list[dict]:
    """Every erc-dharma tfa-*-epigraphy repo with its default branch HEAD commit."""
    repos: list[dict] = []
    page = 1
    while True:
        batch = _api(f"https://api.github.com/orgs/{ORG}/repos?per_page=100&page={page}")
        if not batch:
            break
        for r in batch:
            if REPO_RE.match(r["name"]) and not r.get("archived"):
                repos.append(r)
        page += 1
    out = []
    for r in sorted(repos, key=lambda r: r["name"]):
        branch = r["default_branch"]
        head = _api(f"https://api.github.com/repos/{ORG}/{r['name']}/commits/{branch}")
        out.append({
            "repo": r["name"],
            "url": r["clone_url"],
            "branch": branch,
            "commit": head["sha"],
            "commit_date": head["commit"]["committer"]["date"],
            "license": (r.get("license") or {}).get("spdx_id"),
        })
    return out


def _git(*args: str, cwd: Path | None = None) -> str:
    res = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return res.stdout.strip()


def checkout(entry: dict, raw_dir: Path = RAW_DIR) -> Path:
    """Shallow-fetch ``entry['commit']`` into ``raw_dir/<repo>``; a no-op when already there."""
    dest = raw_dir / entry["repo"]
    if (dest / ".git").exists():
        try:
            if _git("rev-parse", "HEAD", cwd=dest) == entry["commit"]:
                return dest
        except subprocess.CalledProcessError:
            pass
    else:
        dest.mkdir(parents=True, exist_ok=True)
        _git("init", "-q", cwd=dest)
        _git("remote", "add", "origin", entry["url"], cwd=dest)
    _git("fetch", "-q", "--depth", "1", "origin", entry["commit"], cwd=dest)
    _git("checkout", "-q", "--force", "--detach", "FETCH_HEAD", cwd=dest)
    return dest


def edition_files(repo_dir: Path) -> list[Path]:
    """TEI edition files of a repo: ``DHARMA_INS*.xml`` minus templates, editor backups and non-TEI."""
    from ezhuthu.corpus.epidoc import is_tei

    files = []
    for p in sorted(repo_dir.rglob("DHARMA_INS*.xml")):
        if ".git" in p.parts or "template" in p.name.lower():
            continue
        if is_tei(p):
            files.append(p)
    return files


def load_lock(path: Path = LOCK_PATH) -> dict:
    return json.loads(path.read_text())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--update", action="store_true", help="re-discover repos and pin current HEADs")
    ap.add_argument("--lock", type=Path, default=LOCK_PATH)
    ap.add_argument("--raw", type=Path, default=RAW_DIR)
    args = ap.parse_args(argv)

    if args.update or not args.lock.exists():
        entries = discover()
    else:
        entries = load_lock(args.lock)["repos"]

    for e in entries:
        dest = checkout(e, args.raw)
        e["tei_files"] = len(edition_files(dest))
        print(f"{e['repo']:<45} {e['commit'][:10]}  {e['tei_files']:>4} TEI files", file=sys.stderr)

    if args.update or not args.lock.exists():
        lock = {
            "source": f"https://github.com/{ORG}",
            "pinned_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "repos": entries,
        }
        args.lock.parent.mkdir(parents=True, exist_ok=True)
        args.lock.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n")
        print(f"wrote {args.lock}", file=sys.stderr)
    else:
        lock = load_lock(args.lock)
        drift = [e["repo"] for e, old in zip(entries, lock["repos"], strict=True)
                 if e["tei_files"] != old.get("tei_files")]
        if drift:
            print(f"warning: TEI file count differs from lock for {drift}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
