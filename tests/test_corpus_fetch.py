import json
import shutil
import subprocess
from pathlib import Path

from ezhuthu.corpus import fetch

FIX = Path(__file__).parent / "fixtures" / "dharma" / "raw" / "tfa-sii-epigraphy"


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def _make_origin(tmp_path: Path) -> tuple[Path, str, str]:
    origin = tmp_path / "origin" / "tfa-sii-epigraphy"
    shutil.copytree(FIX, origin)
    _git("init", "-q", "-b", "master", cwd=origin)
    _git("-c", "user.email=t@e", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "empty",
         cwd=origin)
    first = _git("rev-parse", "HEAD", cwd=origin)
    _git("add", ".", cwd=origin)
    _git("-c", "user.email=t@e", "-c", "user.name=t", "commit", "-q", "-m", "files", cwd=origin)
    second = _git("rev-parse", "HEAD", cwd=origin)
    _git("config", "uploadpack.allowAnySHA1InWant", "true", cwd=origin)
    return origin, first, second


def test_checkout_pins_exact_commit_and_counts_tei(tmp_path):
    origin, first, second = _make_origin(tmp_path)
    raw = tmp_path / "raw"
    entry = {"repo": "tfa-sii-epigraphy", "url": origin.as_uri(), "commit": second}
    dest = fetch.checkout(entry, raw)
    assert _git("rev-parse", "HEAD", cwd=dest) == second
    # the non-TEI book scan is not an edition
    assert [p.name for p in fetch.edition_files(dest)] == ["DHARMA_INSSII90001.xml", "DHARMA_INSSII90002.xml"]
    # re-pinning to an older commit moves the checkout
    entry["commit"] = first
    fetch.checkout(entry, raw)
    assert _git("rev-parse", "HEAD", cwd=dest) == first
    assert fetch.edition_files(dest) == []


def test_main_uses_lock_without_network(tmp_path):
    origin, _, second = _make_origin(tmp_path)
    lock = tmp_path / "dharma.lock.json"
    lock.write_text(json.dumps({"repos": [{"repo": "tfa-sii-epigraphy", "url": origin.as_uri(),
                                           "commit": second, "tei_files": 2}]}))
    assert fetch.main(["--lock", str(lock), "--raw", str(tmp_path / "raw")]) == 0
    assert (tmp_path / "raw" / "tfa-sii-epigraphy" / "texts" / "DHARMA_INSSII90001.xml").exists()


def test_committed_lock_is_well_formed():
    lock = fetch.load_lock()
    names = [r["repo"] for r in lock["repos"]]
    assert names == sorted(names) and len(names) == len(set(names))
    for r in lock["repos"]:
        assert fetch.REPO_RE.match(r["repo"])
        assert len(r["commit"]) == 40
        assert isinstance(r["tei_files"], int)
