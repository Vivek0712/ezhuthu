"""Reader (POST /api/read): image prep, prompt/reply parsing, routing, text/EpiDoc uploads. Offline (FakeLLM)."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from ezhuthu.agent.decider import FakeDecider
from ezhuthu.agent.llm import FakeLLM, LiveCallsDisabled
from ezhuthu.agent.reader import (
    Reader,
    ReadError,
    ReaderSettings,
    ReaderUnavailable,
    clean_line,
    decode_base64_image,
    parse_reader_reply,
    prepare_image,
    read_epidoc,
)
from ezhuthu.agent.restorer import Restorer
from ezhuthu.agentcore_app import handle_proxy
from ezhuthu.api.app import create_app
from ezhuthu.api.service import EzhuthuService
from ezhuthu.api.storage import MemoryStore

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "dharma" / "raw"


def jpeg_with_gps(w: int = 400, h: int = 300) -> bytes:
    im = Image.new("RGB", (w, h), (180, 170, 150))
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"          # Make
    exif[0x0112] = 6                     # Orientation: rotate 90 CW
    gps = {1: "N", 2: (9.0, 55.0, 0.0), 3: "E", 4: (78.0, 7.0, 0.0)}
    exif[0x8825] = gps                   # GPSInfo
    buf = io.BytesIO()
    im.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def reply(lines, conf=0.9, script="chola-tamil", **kw):
    return json.dumps({"script": script, "script_confidence": 0.7, "era": "10th century", "kind": "inscription",
                       "lines": lines, "confidence": conf, "note": "", **kw})


# ---- image preparation -----------------------------------------------------------------------------------------

def test_prepare_strips_exif_gps_and_applies_orientation():
    img = prepare_image(jpeg_with_gps())
    assert img.format == "jpeg" and img.source_format == "JPEG"
    assert set(img.metadata_removed) >= {"exif", "gps"}
    out = Image.open(io.BytesIO(img.data))
    assert not out.getexif(), "re-encoded image must carry no EXIF"
    assert b"Exif" not in img.data[:64] and b"PhoneMaker" not in img.data
    assert out.size == (300, 400)  # orientation 6 applied, then the tag dropped


def test_prepare_downscales_to_long_side_and_converts_png_alpha():
    im = Image.new("RGBA", (4000, 1000), (0, 0, 0, 0))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    img = prepare_image(buf.getvalue(), ReaderSettings(max_long_side=1568))
    assert img.resized and max(img.width, img.height) == 1568 and img.source_format == "PNG"


def test_prepare_rejects_too_large_bad_and_unsupported():
    s = ReaderSettings(max_upload_bytes=1000)
    with pytest.raises(ReadError) as e:
        prepare_image(b"x" * 2000, s)
    assert e.value.code == "too_large" and e.value.status == 413
    with pytest.raises(ReadError) as e:
        prepare_image(b"not an image at all")
    assert e.value.code == "bad_image"
    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="BMP")
    with pytest.raises(ReadError) as e:
        prepare_image(buf.getvalue())
    assert e.value.code == "unsupported_format" and e.value.status == 415


def test_prepare_keeps_black_text_on_a_transparent_png_visible():
    im = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
    for x in range(50, 150):
        for y in range(40, 60):
            im.putpixel((x, y), (0, 0, 0, 255))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    out = Image.open(io.BytesIO(prepare_image(buf.getvalue()).data)).convert("L")
    assert out.getpixel((10, 10)) > 240, "transparent background must become white, not black"
    assert out.getpixel((100, 50)) < 40, "the text stays black"
    pal = Image.new("P", (20, 20), 0)
    pal.info["transparency"] = 0
    buf = io.BytesIO()
    pal.save(buf, format="PNG", transparency=0)
    assert Image.open(io.BytesIO(prepare_image(buf.getvalue()).data)).convert("L").getpixel((5, 5)) > 240


def test_pillow_decompression_bomb_is_too_large_not_bad_image(monkeypatch):
    buf = io.BytesIO()
    Image.new("L", (100, 100)).save(buf, format="PNG")
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)  # 10,000 px > 2x the limit: Pillow raises at open
    with pytest.raises(ReadError) as e:
        prepare_image(buf.getvalue())
    assert e.value.code == "too_large" and e.value.status == 413


def test_prepare_rejects_pixel_bombs_before_decoding():
    buf = io.BytesIO()
    Image.new("L", (3000, 3000)).save(buf, format="PNG")
    with pytest.raises(ReadError) as e:
        prepare_image(buf.getvalue(), ReaderSettings(max_pixels=1_000_000))
    assert e.value.code == "too_large"


def test_decode_base64_limits():
    with pytest.raises(ReadError):
        decode_base64_image("@@@", max_bytes=100)
    with pytest.raises(ReadError) as e:
        decode_base64_image("A" * 400, max_bytes=100)
    assert e.value.code == "too_large"
    assert decode_base64_image("data:image/jpeg;base64," + b64(b"abc"), max_bytes=100) == b"abc"


# ---- parsing ----------------------------------------------------------------------------------------------------

def test_parse_reply_full_and_fenced():
    p = parse_reader_reply("```json\n" + reply([["svasti śrī", 0.9], ["kō[?3]", 0.4]]) + "\n```")
    assert p["lines"] == [("svasti śrī", 0.9), ("kō[?3]", 0.4)] and p["script"] == "chola-tamil"
    assert p["confidence"] == 0.9 and not p["partial"]


def test_parse_reply_truncated_keeps_complete_pairs():
    cut = '{"script": "tamil-brahmi", "lines": [["kaṇiy nanta", 0.8], ["ciri[?2]", 0.5], ["ari'
    p = parse_reader_reply(cut)
    assert p["partial"] and p["script"] == "tamil-brahmi"
    assert [t for t, _ in p["lines"]] == ["kaṇiy nanta", "ciri[?2]"]


def test_parse_reply_unknown_script_and_clamped_probabilities():
    p = parse_reader_reply(json.dumps({"script": "Martian", "lines": [["a", 7], ["b", "x"]], "confidence": -1}))
    assert p["script"] == "unknown" and p["lines"] == [("a", 1.0), ("b", None)] and p["confidence"] == 0.0


def test_clean_line_gap_notation_and_tamil():
    assert clean_line("ஸ்வஸ்தி ஸ்ரீ ... கோ")[0] == "svasti śrī [?] kō"
    assert clean_line("kō [ ? 3 ] [...] x")[0] == "kō [?3] [?]"  # 'x' is not ISO-15919
    iso, dropped = clean_line("abc <b>http://evil</b>")
    assert "<" not in iso and ":" not in iso and set(dropped) >= {"<", ">", ":"}


# ---- reader routing ---------------------------------------------------------------------------------------------

class Clock:
    def __init__(self, step: float):
        self.t, self.step = 0.0, step

    def __call__(self) -> float:
        self.t += self.step
        return self.t


def make_reader(responder, step=0.1, **settings) -> tuple[Reader, FakeLLM]:
    llm = FakeLLM(responder)
    return Reader(llm=llm, settings=ReaderSettings(**settings), clock=Clock(step)), llm


def test_image_read_confident_sonnet_only():
    r, llm = make_reader(lambda role, s, p: reply([["svasti śrī kō[?4]kēcari", 0.85]], conf=0.85))
    out = r.read(image_base64=b64(jpeg_with_gps()))
    assert [c[0] for c in llm.calls] == ["default"]
    assert out["source"] == "image" and out["experimental"] is True
    assert out["lines"][0]["text"] == "svasti śrī kō[?4]kēcari" and out["lines"][0]["gaps"] == 1
    assert out["lines"][0]["text_tamil"].startswith("ஸ்வஸ்தி")
    assert out["script_guess"]["script"] == "chola-tamil" and out["script_guess"]["level"] == "L2"
    assert out["models_used"] == ["sonnet"] and not out["escalated"] and out["gaps"] == 1
    assert "gps" in out["image"]["metadata_removed"]
    # the bytes the model saw carry no EXIF
    sent = llm.images[0][0][0]
    assert not Image.open(io.BytesIO(sent)).getexif()


def test_image_read_escalates_to_opus_when_unsure():
    def responder(role, s, p):
        return reply([["kō", 0.3]], conf=0.3) if role == "default" else reply([["kōvirāja", 0.7]], conf=0.7)

    r, llm = make_reader(responder)
    out = r.read(image_base64=b64(jpeg_with_gps()))
    assert [c[0] for c in llm.calls] == ["default", "escalate"]
    assert out["escalated"] and out["models_used"] == ["sonnet", "opus"] and out["model"] == "opus"
    assert out["lines"][0]["text"] == "kōvirāja"


def test_escalation_skipped_when_too_little_budget_is_left():
    # clock steps 11 s per reading: request starts at 11 (deadline 36), the first read ends at 33 -> 3 s left
    r, llm = make_reader(lambda role, s, p: reply([["kō", 0.2]], conf=0.2), step=11.0,
                         request_budget_s=25, escalate_min_remaining_s=15)
    out = r.read(image_base64=b64(jpeg_with_gps()))
    assert len(llm.calls) == 1 and out["escalation_skipped"] == "time_budget" and not out["escalated"]
    assert isinstance(out["reread_token"], str) and len(out["reread_token"]) == 32


def test_router_opus_needs_a_one_time_reread_token_for_the_same_photo():
    calls = []

    def responder(role, s, p):
        calls.append(role)
        return reply([["kō", 0.2]], conf=0.2)

    r, _ = make_reader(responder, step=11.0, request_budget_s=25, escalate_min_remaining_s=15)
    photo = b64(jpeg_with_gps())
    with pytest.raises(ReadError) as e:  # no token: anonymous callers cannot pick Opus
        r.read(image_base64=photo, router="opus")
    assert e.value.code == "reread_token_invalid" and e.value.status == 403
    token = r.read(image_base64=photo)["reread_token"]
    with pytest.raises(ReadError):  # bound to the photo it was issued for
        r.read(image_base64=b64(jpeg_with_gps(500, 300)), router="opus", reread_token=token)
    out = r.read(image_base64=photo, router="opus", reread_token=token)
    assert out["model"] == "opus" and "reread_token" not in out
    with pytest.raises(ReadError):  # works once
        r.read(image_base64=photo, router="opus", reread_token=token)
    with pytest.raises(ReadError):
        r.read(image_base64=photo, router="opus", reread_token="../../etc")
    assert calls == ["default", "escalate"]


def test_reread_token_expires():
    from ezhuthu.agent.reader import RereadTokens

    now = [1000.0]
    t = RereadTokens(ttl_s=60, clock=lambda: now[0])
    tok = t.issue("abc")
    now[0] += 61
    assert not t.consume(tok, "abc")


def test_router_opus_goes_straight_to_escalate_and_sonnet_never_escalates():
    r, llm = make_reader(lambda role, s, p: reply([["a", 0.1]], conf=0.1))
    img = prepare_image(jpeg_with_gps())
    r.read_image(img, router="opus")
    r.read(image_base64=b64(jpeg_with_gps()), router="sonnet")
    assert [c[0] for c in llm.calls] == ["escalate", "default"]


def test_failed_escalation_keeps_the_first_reading():
    def responder(role, s, p):
        if role == "escalate":
            raise RuntimeError("ModelTimeoutException: Opus took too long")
        return reply([["kō[?2]", 0.4]], conf=0.4)

    r, llm = make_reader(responder)
    out = r.read(image_base64=b64(jpeg_with_gps()))
    assert [c[0] for c in llm.calls] == ["default", "escalate"]
    assert out["escalation_skipped"] == "error" and not out["escalated"]
    assert out["lines"][0]["text"] == "kō[?2]" and out["model"] == "sonnet" and out["models_used"] == ["sonnet"]


def test_escalation_keeps_the_more_confident_reading():
    def responder(role, s, p):
        return reply([["kō", 0.45]], conf=0.45) if role == "default" else reply([["jambai", 0.3]], conf=0.3)

    r, _ = make_reader(responder)
    out = r.read(image_base64=b64(jpeg_with_gps()))
    assert out["escalated"] and out["models_used"] == ["sonnet", "opus"]
    assert out["model"] == "sonnet" and out["lines"][0]["text"] == "kō" and out["confidence"] == 0.45


def test_every_model_call_is_bounded_by_the_request_budget():
    r, llm = make_reader(lambda role, s, p: reply([["kō", 0.2]], conf=0.2), step=2.0,
                         request_budget_s=25, escalate_min_remaining_s=15)
    r.read(image_base64=b64(jpeg_with_gps()))
    # clock: start 2 (deadline 27); first call at 4 -> 23 s; it ends at 6, check at 8 (19 left), Opus at 10 -> 17 s
    assert llm.timeouts == [23.0, 17.0]
    assert all(t <= 25 for t in llm.timeouts)


def test_budget_exhaustion_on_escalation_keeps_first_reading():
    def responder(role, s, p):
        if role == "escalate":
            raise LiveCallsDisabled("budget")
        return reply([["kō", 0.2]], conf=0.2)

    r, _ = make_reader(responder)
    out = r.read(image_base64=b64(jpeg_with_gps()))
    assert out["escalation_skipped"] == "budget" and out["lines"][0]["text"] == "kō"


def test_warnings_carry_codes_for_the_app_to_localise():
    r, _ = make_reader(lambda role, s, p: reply([["satiyaputo", 0.2]], conf=0.2, script="tamil-brahmi"))
    out = r.read(image_base64=b64(jpeg_with_gps()), router="sonnet")
    assert out["warning_codes"] == [{"code": "low_reliability_script", "params": {"script": "tamil-brahmi"}}]
    assert len(out["warnings"]) == len(out["warning_codes"])
    out = Reader(llm=None).read(text="svasti śrī <b>", filename="a.txt")
    assert out["warning_codes"] == [{"code": "dropped_chars", "params": {"chars": "<>"}}]


def test_no_text_in_image_is_a_warning_not_an_error():
    r, _ = make_reader(lambda role, s, p: reply([], conf=0.9, script="unknown", note="a cat"))
    out = r.read(image_base64=b64(jpeg_with_gps()), router="sonnet")
    assert out["lines"] == [] and any("no readable" in w for w in out["warnings"])


def test_image_without_live_model_is_unavailable():
    with pytest.raises(ReaderUnavailable):
        Reader(llm=None).read(image_base64=b64(jpeg_with_gps()))


def test_exactly_one_input():
    r, _ = make_reader(lambda *a: "{}")
    with pytest.raises(ReadError):
        r.read()
    with pytest.raises(ReadError):
        r.read(image_base64="x", text="y")


# ---- text and EpiDoc ---------------------------------------------------------------------------------------------

def test_text_file_tamil_and_iso_lines():
    out = Reader(llm=None).read(text="1. ஸ்வஸ்தி ஸ்ரீ\n\n2. kōp[?4]kēcari yāṇṭu ...\n", filename="a.txt")
    assert out["source"] == "text" and not out["experimental"]
    assert [ln["text"] for ln in out["lines"]] == ["svasti śrī", "kōp[?4]kēcari yāṇṭu [?]"]
    assert out["gaps"] == 2 and out["script_guess"] is None


def test_text_file_without_tamil_is_rejected():
    with pytest.raises(ReadError) as e:
        Reader(llm=None).read(text="<<<>>> !!!", filename="a.txt")
    assert e.value.code == "no_text"


def test_epidoc_upload_masks_supplied_as_gaps():
    xml = (FIX / "tfa-pallava-epigraphy" / "DHARMA_INSPallava90001.xml").read_text(encoding="utf-8")
    out = Reader(llm=None).read(text=xml, filename="DHARMA_INSPallava90001.xml")
    assert out["source"] == "epidoc" and out["lines"]
    assert out["title"]
    assert out["licence"] == "CC BY-SA 4.0"
    assert out["licence_url"] == "https://creativecommons.org/licenses/by-sa/4.0/"
    assert out["inscription_id"] is None and out["source_url"] is None  # the fixture has no <idno type="filename">
    if out["masked_supplied"]:
        assert out["gaps"] >= out["masked_supplied"]


def test_epidoc_refuses_entities_and_non_tei():
    evil = ('<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
            '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><div type="edition"><p>&x;</p></div>'
            '</body></text></TEI>')
    try:
        out = read_epidoc(evil.encode())
        assert "root:" not in json.dumps(out)
    except ReadError:
        pass
    with pytest.raises(ReadError) as e:
        read_epidoc(b"<html/>")
    assert e.value.code == "not_epidoc"


# ---- API contract ------------------------------------------------------------------------------------------------

def _svc(llm):
    dec = FakeDecider(lambda s, o: {n: 1 / len(o) for n in o})
    return EzhuthuService(store=MemoryStore(), llm=llm, decider=dec, restorer=Restorer(decider=dec, llm=llm),
                          model_factory=None, admin_token=None)


def test_api_read_image_contract():
    llm = FakeLLM(lambda role, s, p: reply([["svasti śrī", 0.8], ["kō[?3]", 0.6]], conf=0.8))
    c = TestClient(create_app(_svc(llm)))
    r = c.post("/api/read", json={"image_base64": b64(jpeg_with_gps()), "media_type": "image/jpeg"})
    assert r.status_code == 200
    body = r.json()
    for k in ("source", "experimental", "lines", "text", "text_tamil", "gaps", "script_guess", "confidence",
              "models_used", "escalated", "warnings", "image", "trace_id", "latency_ms"):
        assert k in body, k
    assert set(body["lines"][0]) == {"n", "text", "text_tamil", "confidence", "gaps"}
    assert {"script", "label_en", "label_ta", "era", "confidence", "level"} <= set(body["script_guess"])
    assert body["text"] == "svasti śrī\nkō[?3]"


def test_api_read_text_and_errors():
    c = TestClient(create_app(_svc(None)))
    assert c.post("/api/read", json={"text": "svasti śrī [?2]", "filename": "x.txt"}).json()["gaps"] == 1
    r = c.post("/api/read", json={"image_base64": b64(jpeg_with_gps())})
    assert r.status_code == 503 and r.json()["code"] == "reader_unavailable"
    r = c.post("/api/read", json={"image_base64": b64(b"GIF89a" + b"0" * 50)})
    assert r.status_code in (415, 422, 503)
    assert c.post("/api/read", json={}).status_code == 422
    assert c.post("/api/read", json={"text": "a", "bogus": 1}).status_code == 422


def test_api_read_bad_image_is_422_with_live_model():
    c = TestClient(create_app(_svc(FakeLLM(lambda *a: "{}"))))
    r = c.post("/api/read", json={"image_base64": b64(b"definitely not an image")})
    assert r.status_code == 422 and r.json()["code"] == "bad_image"


def test_agentcore_proxy_route_read():
    llm = FakeLLM(lambda role, s, p: reply([["svasti", 0.9]], conf=0.9))
    out = handle_proxy({"version": 1, "route": "/api/read", "method": "POST",
                        "body": {"image_base64": b64(jpeg_with_gps())}}, _svc(llm))
    assert out["status"] == 200 and out["body"]["lines"][0]["text"] == "svasti"
    out = handle_proxy({"version": 1, "route": "/api/read", "method": "POST",
                        "body": {"image_base64": b64(b"x" * 10)}}, _svc(llm))
    assert out["status"] == 422 and out["body"]["error"]["code"] == "bad_image"
    out = handle_proxy({"version": 1, "route": "/api/read", "method": "POST", "body": {"image_base64": "QQ=="}},
                       _svc(None))
    assert out["status"] == 503 and out["body"]["error"]["code"] == "reader_unavailable"


def test_low_reliability_scripts_and_low_confidence_warn():
    r, _ = make_reader(lambda role, s, p: reply([["satiyaputo", 0.2]], conf=0.2, script="tamil-brahmi"))
    out = r.read(image_base64=b64(jpeg_with_gps()), router="sonnet")
    assert any("cannot yet read Tamil-Brahmi" in w for w in out["warnings"])
    r, _ = make_reader(lambda role, s, p: reply([["svasti", 0.3]], conf=0.3, script="chola-tamil"))
    out = r.read(image_base64=b64(jpeg_with_gps()), router="sonnet")
    assert any("unsure" in w for w in out["warnings"])
    r, _ = make_reader(lambda role, s, p: reply([["svasti", 0.9]], conf=0.9, script="chola-tamil"))
    assert r.read(image_base64=b64(jpeg_with_gps()), router="sonnet")["warnings"] == []
