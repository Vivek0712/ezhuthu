"""Hosted Strands Decider API client (decider-cloud /v1/decide) against a local fake server. No network."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from ezhuthu.agent.config import parse_models_config
from ezhuthu.agent.decider import (
    DeciderUnavailable,
    HostedDecider,
    HttpDecider,
    NoDecider,
    decider_backend,
    default_decider,
    hosted_decider,
)
from ezhuthu.agent.restorer import Candidate, Restorer
from ezhuthu.agent.tutor import policy

MODEL = "strands-decider-2b-hobson-v19"
KEY = "dcd_live_TESTKEY"


class FakeCloud:
    """Mimics decider-cloud: bearer auth, GET /v1/models, POST /v1/decide (choice + noul), scripted errors."""

    def __init__(self):
        self.requests: list[dict] = []
        self.fail_next: list[tuple[int, str, dict]] = []  # (status, code, headers)
        self.raw_next: list[tuple[int, bytes, dict]] = []  # (status, raw body, headers): malformed replies
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):  # quiet
                pass

            def _send(self, status, body, headers=None):
                raw = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("x-ratelimit-remaining-requests", "9")
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(raw)

            def _auth(self):
                if self.headers.get("authorization") != f"Bearer {KEY}":
                    self._send(401, {"error": {"code": "invalid_api_key", "message": "bad key"}, "id": "r"})
                    return False
                return True

            def do_GET(self):
                fake.requests.append({"method": "GET", "path": self.path, "auth": self.headers.get("authorization")})
                if not self._auth():
                    return
                self._send(200, {"data": [{"id": MODEL, "type": "decider", "ready": True}]})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["content-length"])))
                fake.requests.append({"method": "POST", "path": self.path, "body": body,
                                      "auth": self.headers.get("authorization")})
                if not self._auth():
                    return
                if fake.raw_next:
                    status, raw, headers = fake.raw_next.pop(0)
                    self.send_response(status)
                    for k, v in headers.items():
                        self.send_header(k, v)
                    self.send_header("content-length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                if fake.fail_next:
                    status, code, headers = fake.fail_next.pop(0)
                    self._send(status, {"error": {"code": code, "message": code}, "id": "r"}, headers)
                    return
                answers = {}
                for name, q in body["questions"].items():
                    if q["type"] == "noul":
                        answers[name] = {"type": "noul", "noul": 0.8}
                    else:
                        opts = list(q["criteria"])
                        probs = {o: (0.7 if i == 0 else 0.3 / (len(opts) - 1)) for i, o in enumerate(opts)}
                        answers[name] = {"type": "choice", "choice": opts[0], "probabilities": probs,
                                         "confidence": 0.55}
                self._send(200, {"id": "req_1", "model": MODEL, "latency_ms": 12.5, "answers": answers,
                                 "usage": {"input_tokens": 10, "output_tokens": 1}})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


@pytest.fixture
def cloud():
    c = FakeCloud()
    yield c
    c.close()


def make(cloud, **kw):
    sleeps: list[float] = []
    d = HostedDecider(cloud.url, MODEL, api_key=kw.pop("api_key", KEY), sleep=sleeps.append, **kw)
    return d, sleeps


def test_choice_maps_to_v1_decide_schema(cloud):
    d, _ = make(cloud, rpm=None)
    res = d.choice({"x": 1}, "pick", {"a": "first", "b": "second"}, name="restoration")
    req = cloud.requests[-1]
    assert req["path"] == "/v1/decide" and req["auth"] == f"Bearer {KEY}"
    assert req["body"] == {"state": {"x": 1}, "model": MODEL, "questions": {
        "restoration": {"type": "choice", "instructions": "pick", "criteria": {"a": "first", "b": "second"}}}}
    assert (res.choice, res.model, res.source, res.confidence) == ("a", MODEL, "hosted", 0.55)
    assert res.probabilities["a"] == pytest.approx(0.7)
    assert d.last_headers.get("x-ratelimit-remaining-requests") == "9"


def test_noul_maps_to_v1_decide_schema(cloud):
    d, _ = make(cloud, rpm=None)
    res = d.noul("Is the gap a royal title?", "yes or no", name="title")
    assert cloud.requests[-1]["body"]["questions"] == {"title": {"type": "noul", "instructions": "yes or no"}}
    assert (res.probability, res.source, res.model) == (0.8, "hosted", MODEL)


def test_health_uses_models_listing(cloud):
    d, _ = make(cloud)
    assert d.available() and d.health()["source"] == "hosted"
    other = HostedDecider(cloud.url, "some-other-model", api_key=KEY)
    assert other.available() is False


def test_bad_key_is_unavailable_and_never_echoed(cloud, caplog):
    d, _ = make(cloud, api_key="dcd_live_WRONG", rpm=None)
    with pytest.raises(DeciderUnavailable) as ei:
        d.choice("s", "i", {"a": "1", "b": "2"})
    assert "401" in str(ei.value) and "WRONG" not in str(ei.value)
    assert "WRONG" not in caplog.text
    assert d.available() is False


def test_429_retries_once_after_retry_after(cloud):
    d, sleeps = make(cloud, rpm=None)
    cloud.fail_next = [(429, "rate_limited", {"Retry-After": "3"})]
    assert d.choice("s", "i", {"a": "1", "b": "2"}).choice == "a"
    assert sleeps == [3.0]
    cloud.fail_next = [(503, "overloaded", {"Retry-After": "1"}), (503, "overloaded", {"Retry-After": "1"})]
    with pytest.raises(DeciderUnavailable, match="503"):
        d.choice("s", "i", {"a": "1", "b": "2"})


@pytest.mark.parametrize("status,code", [(413, "input_too_large"), (402, "quota_exhausted"), (422, "invalid_request")])
def test_refusals_raise_unavailable_without_retry(cloud, status, code):
    d, sleeps = make(cloud, rpm=None)
    cloud.fail_next = [(status, code, {})]
    with pytest.raises(DeciderUnavailable, match=code):
        d.choice("s", "i", {"a": "1", "b": "2"})
    assert sleeps == []


def test_client_side_pacing_respects_rpm(cloud):
    d, sleeps = make(cloud, rpm=10)  # 6 s between requests
    for _ in range(3):
        d.choice("s", "i", {"a": "1", "b": "2"})
    # the fake sleep does not advance the clock, so the schedule shows as 6 s and 12 s from the first call
    assert len(sleeps) == 2 and 5.0 < sleeps[0] <= 6.0 and 11.0 < sleeps[1] <= 12.0


def test_unreachable_is_unavailable():
    d = HostedDecider("http://127.0.0.1:9", MODEL, api_key=KEY, rpm=None)
    assert d.available() is False
    with pytest.raises(DeciderUnavailable):
        d.choice("s", "i", {"a": "1", "b": "2"})


def test_missing_key_is_unavailable(monkeypatch):
    monkeypatch.delenv("EZHUTHU_DECIDER_API_KEY", raising=False)
    d = HostedDecider("http://127.0.0.1:9", MODEL, rpm=None)
    with pytest.raises(DeciderUnavailable, match="EZHUTHU_DECIDER_API_KEY"):
        d.choice("s", "i", {"a": "1", "b": "2"})


def test_key_from_secret_json_or_raw(monkeypatch):
    import ezhuthu.agent.decider as dec

    monkeypatch.delenv("EZHUTHU_DECIDER_API_KEY", raising=False)
    monkeypatch.setattr(dec, "_secret_api_key", lambda name, region, profile: KEY if name == "s" else 1 / 0)
    assert HostedDecider("http://x", MODEL, secret_name="s").api_key == KEY
    bad = HostedDecider("http://x", MODEL, secret_name="bad")
    with pytest.raises(DeciderUnavailable, match="ZeroDivisionError"):
        bad.api_key  # noqa: B018
    calls = []
    monkeypatch.setattr(dec, "_secret_api_key", lambda *a: calls.append(a) or 1 / 0)
    with pytest.raises(DeciderUnavailable, match="cached failure"):
        bad.api_key  # noqa: B018
    assert calls == []  # no Secrets Manager call while the failure is cached


CFG = parse_models_config({"llm": {"default": "m"}, "decider": {
    "fast": "StrandsAgents/strands-decider-2B-qwen3.5-v1-2610",
    "cloud": {"url": "https://example.invalid/", "model": MODEL, "secret_name": "ezhuthu/decider-api-key", "rpm": 10}}})


def test_backend_selection(monkeypatch):
    monkeypatch.delenv("EZHUTHU_DECIDER", raising=False)
    monkeypatch.delenv("EZHUTHU_DECIDER_BACKEND", raising=False)
    assert decider_backend() == "local" and isinstance(default_decider(), HttpDecider)
    monkeypatch.setenv("EZHUTHU_DECIDER_BACKEND", "fallback")
    assert isinstance(default_decider(), NoDecider)
    monkeypatch.setenv("EZHUTHU_DECIDER_BACKEND", "bogus")
    with pytest.raises(ValueError):
        decider_backend()
    monkeypatch.setenv("EZHUTHU_DECIDER_BACKEND", "hosted")
    monkeypatch.setenv("EZHUTHU_DECIDER", "off")
    assert isinstance(default_decider(), NoDecider)


def test_hosted_from_config_and_repo_models_yaml():
    d = hosted_decider(CFG)
    assert (d.base_url, d.model, d._secret_name, d.min_interval) == (
        "https://example.invalid", MODEL, "ezhuthu/decider-api-key", 6.0)
    from ezhuthu.agent.config import load_models_config

    cloud = load_models_config().decider["cloud"]
    assert cloud["model"] == MODEL and cloud["secret_name"] == "ezhuthu/decider-api-key"
    with pytest.raises(ValueError, match="decider.cloud"):
        hosted_decider(parse_models_config({"llm": {"default": "m"}}))


def test_restorer_flags_hosted_source_and_fallback(cloud):
    d, _ = make(cloud, rpm=None)
    r = Restorer(decider=d, corpus=[], use_ontology=False, config=CFG)
    model, ranked = r.rank_and_decide([Candidate("rājakēcari"), Candidate("parakēcari")], left="kō ", right=" yāṇṭu",
                                      gap_chars=9, parallels=[], hints=[])
    assert model == MODEL and ranked[0].text == "rājakēcari"
    api = ranked[0].to_api(model)
    assert api["decider_model"] == MODEL and api["decider_source"] == "hosted"
    cloud.fail_next = [(413, "input_too_large", {})]
    tag, ranked = r.rank_and_decide([Candidate("a", llm_confidence=0.4), Candidate("b", llm_confidence=0.6)],
                                    left="", right="", gap_chars=1, parallels=[], hints=[])
    assert tag == "fallback:llm-self-report" and ranked[0].to_api(tag)["decider_source"] == "fallback"


def test_policy_reports_backend(cloud):
    d, _ = make(cloud, rpm=None)
    state = {"correct": False, "attempts_on_item": 1, "hint_already_given": False}
    out = policy.decide(d, state)
    assert out.backend == "hosted" and out.source == MODEL and out.action in policy.ACTIONS
    assert policy.decide(NoDecider(), state).backend == "rules"


def test_hosted_trims_tail_options_to_tier_limit(cloud):
    from ezhuthu.agent.decider import fit_choice, request_chars

    opts = {f"c{i}": {"fill": "ṉ" * 60} for i in range(8)} | {"none": "none fits"}
    limit = request_chars(fit_choice({"s": 1}, "i", opts, "restoration", None)) - 500
    d, _ = make(cloud, rpm=None, max_input_chars=limit)
    res = d.choice({"s": 1}, "i", opts, name="restoration")
    sent = cloud.requests[-1]["body"]["questions"]["restoration"]["criteria"]
    assert "none" in sent and "c0" in sent and len(sent) < len(opts) and d.last_trimmed == len(opts) - len(sent)
    assert res.probabilities.get("c7") is None  # dropped options carry no probability


# ---- malformed replies must become DeciderUnavailable (QA on PR #19) -------------------------------------

def test_retry_after_http_date_and_garbage_are_parsed_defensively(cloud):
    from email.utils import formatdate

    from ezhuthu.agent.decider import retry_after_seconds

    assert retry_after_seconds(None) == 5.0 and retry_after_seconds("soon") == 5.0
    assert retry_after_seconds("-3") == 0.0 and retry_after_seconds(" 2.5 ") == 2.5
    assert retry_after_seconds(formatdate(0, usegmt=True)) == 0.0  # a date in the past: retry now
    assert 0.0 < retry_after_seconds(formatdate(__import__("time").time() + 30, usegmt=True)) <= 30.0
    d, sleeps = make(cloud, rpm=None, max_retry_wait=20.0)
    import time as _t

    cloud.fail_next = [(429, "rate_limited", {"Retry-After": formatdate(_t.time() + 600, usegmt=True)})]
    assert d.choice("s", "i", {"a": "1", "b": "2"}).choice == "a"
    assert sleeps == [20.0]  # HTTP date honoured, capped at max_retry_wait
    cloud.fail_next = [(503, "overloaded", {"Retry-After": "not-a-number"})]
    assert d.choice("s", "i", {"a": "1", "b": "2"}).choice == "a"
    assert sleeps[-1] == 5.0


def test_non_json_200_is_unavailable(cloud):
    d, _ = make(cloud, rpm=None)
    cloud.raw_next = [(200, b"<html>gateway hiccup</html>", {"content-type": "text/html"})]
    with pytest.raises(DeciderUnavailable, match="non-JSON"):
        d.choice("s", "i", {"a": "1", "b": "2"})
    cloud.raw_next = [(200, b"\xff\xfe not utf-8", {})]
    with pytest.raises(DeciderUnavailable):
        d.noul("s", "i")


@pytest.mark.parametrize("body", [
    {"id": "r", "model": MODEL, "answers": {}},                                          # no answers[name]
    {"id": "r", "model": MODEL},                                                         # no answers at all
    {"id": "r", "answers": {"q": {"choice": "a", "probabilities": None, "confidence": 1}}},  # TypeError
    {"id": "r", "answers": {"q": {"choice": "a", "probabilities": {"a": "x"}, "confidence": 1}}},  # ValueError
    ["not", "an", "object"],
])
def test_malformed_200_answer_is_unavailable(cloud, body):
    d, _ = make(cloud, rpm=None)
    cloud.raw_next = [(200, json.dumps(body).encode(), {"content-type": "application/json"})]
    with pytest.raises(DeciderUnavailable, match="unusable"):
        d.choice("s", "i", {"a": "1", "b": "2"}, name="q")
    cloud.raw_next = [(200, json.dumps(body).encode(), {"content-type": "application/json"})]
    with pytest.raises(DeciderUnavailable, match="unusable"):
        d.noul("s", "i", name="q")


@pytest.mark.parametrize("raw", [b"not json", json.dumps({"answers": {}}).encode()])
def test_restorer_falls_back_on_malformed_hosted_reply(cloud, raw):
    d, _ = make(cloud, rpm=None)
    r = Restorer(decider=d, corpus=[], use_ontology=False, config=CFG)
    cloud.raw_next = [(200, raw, {"content-type": "application/json"})]
    tag, ranked = r.rank_and_decide([Candidate("a", llm_confidence=0.4), Candidate("b", llm_confidence=0.6)],
                                    left="", right="", gap_chars=1, parallels=[], hints=[])
    assert tag == "fallback:llm-self-report" and ranked[0].text == "b"
    assert ranked[0].to_api(tag)["decider_source"] == "fallback"


@pytest.mark.parametrize("raw", [b"<html>oops</html>", json.dumps({"answers": {}}).encode(),
                                 json.dumps({"answers": {"q": {"choice": "a"}}}).encode()])
def test_local_http_decider_malformed_reply_is_unavailable(raw):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers["content-length"]))
            self.send_response(200)
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        d = HttpDecider(f"http://127.0.0.1:{srv.server_address[1]}")
        with pytest.raises(DeciderUnavailable):
            d.choice("s", "i", {"a": "1", "b": "2"}, name="q")
        with pytest.raises(DeciderUnavailable):
            d.noul("s", "i", name="q")
    finally:
        srv.shutdown()


def test_trimmed_candidates_are_labelled_decider_trimmed(cloud):
    from ezhuthu.agent.decider import request_chars

    cands = [Candidate("ṉ" * 40 + str(i)) for i in range(8)]
    d, _ = make(cloud, rpm=None)
    r = Restorer(decider=d, corpus=[], use_ontology=False, config=CFG)
    r.rank_and_decide(cands, left="", right="", gap_chars=40, parallels=[], hints=[], strategy="choice-all")
    full = cloud.requests[-1]["body"]
    d.max_input_chars = request_chars({"state": full["state"], "questions": full["questions"]}) - 400
    model, ranked = r.rank_and_decide([Candidate("ṉ" * 40 + str(i)) for i in range(8)], left="", right="",
                                      gap_chars=40, parallels=[], hints=[], strategy="choice-all")
    assert model == MODEL and d.last_trimmed > 0
    srcs = [c.confidence_source for c in ranked]
    assert srcs.count("decider-trimmed") == d.last_trimmed and srcs.count("decider") == 8 - d.last_trimmed
    assert all(c.confidence == 0.0 for c in ranked if c.confidence_source == "decider-trimmed")
