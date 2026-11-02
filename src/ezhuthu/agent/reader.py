"""Reader: photo or file in, editable transcription out (``POST /api/read``, contracts/restore-api.md).

Learners rarely have inscription text to paste. The Reader turns what they do have into the restorer's input:

* **image** (photo of a stone, copper plate or palm leaf, or a printed page): a Strands ``Agent`` on Bedrock
  (Sonnet 4.6 vision, ``llm.default``) transcribes it line by line in ISO-15919, guesses the script/era and marks
  illegible stretches as ``[?N]`` / ``[?]`` gaps, the same notation ``/api/restore`` takes. When its confidence is
  under ``routing.escalate_if_confidence_below`` the image is read again by Opus 4.6 (``llm.escalate``), unless less
  than ``reader.escalate_min_remaining_s`` of the request's ``reader.request_budget_s`` is left: the response then
  says ``escalation_skipped: "time_budget"`` and carries a one-time ``reread_token`` that the app sends back with
  ``router: "opus"`` to read the same photo again. ``router: "opus"`` without that token is refused (403), so an
  anonymous caller cannot pick the expensive model at will. A failed escalation keeps the first reading
  (``escalation_skipped: "error"``), and of two readings the higher-confidence one is kept.
* **text file** (``.txt``, Tamil script or ISO-15919): normalised to the same line form.
* **DHARMA EpiDoc/TEI XML**: parsed with ``ezhuthu.corpus.epidoc`` (no network, no entities); editorial
  restorations (``<supplied>``) become ``[?N]`` gaps so the learner can try restoring them.

Images are decoded with Pillow, size-guarded, auto-rotated from EXIF, downscaled to
``reader.max_long_side`` and re-encoded as JPEG **without any metadata** (EXIF/GPS/XMP never reach the model,
the cache or the logs). Photo reading is experimental: the response always carries ``experimental: true``.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import logging
import math
import re
import time
import unicodedata
import uuid
from dataclasses import dataclass, field
from typing import Any, ClassVar

from .config import ModelsConfig, load_models_config
from .llm import LiveCallsDisabled, LLMClient, LLMResponse, short_name
from .text import GAP_RE, looks_tamil, non_iso_chars, tamil_to_iso

log = logging.getLogger(__name__)

SCRIPTS = ("tamil-brahmi", "vatteluttu", "grantha", "pallava-tamil", "chola-tamil", "modern-tamil", "unknown")
# Tutor level (contracts/restore-api.md "Tutor") a detected script maps to.
SCRIPT_LEVEL = {"tamil-brahmi": "L5", "vatteluttu": "L4", "grantha": "L3", "pallava-tamil": "L3",
                "chola-tamil": "L2", "modern-tamil": "L1"}
SCRIPT_LABELS = {
    "tamil-brahmi": ("Tamil-Brahmi", "தமிழ்-பிராமி"), "vatteluttu": ("Vatteluttu", "வட்டெழுத்து"),
    "grantha": ("Grantha", "கிரந்தம்"), "pallava-tamil": ("Pallava-era Tamil", "பல்லவர் காலத் தமிழ்"),
    "chola-tamil": ("Chola-era Tamil", "சோழர் காலத் தமிழ்"), "modern-tamil": ("Modern Tamil", "தற்காலத் தமிழ்"),
    "unknown": ("Unknown", "தெரியவில்லை"),
}
ROUTERS = ("routed", "sonnet", "opus")
# Measured in eval/reports/2026-11-02-ocr-eval.md: Sonnet and Opus both read these scripts at CER 0.5-0.9 (synthetic
# Tamil-Brahmi/Grantha renderings and three real Jambai Tamil-Brahmi images), against ~0.05 for Tamil script.
LOW_RELIABILITY_SCRIPTS = ("tamil-brahmi", "vatteluttu", "grantha")
LOW_CONFIDENCE = 0.5
ALLOWED_PUNCT = "=’‘·[]?"  # same editorial marks the restore API accepts (api.limits.INSCRIPTION_PUNCT)


class ReadError(ValueError):
    """Bad input for the reader (HTTP 422). ``code`` is a stable machine-readable reason."""

    STATUS: ClassVar[dict[str, int]] = {"too_large": 413, "unsupported_format": 415, "reread_token_invalid": 403}

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.status = self.STATUS.get(code, 422)


class ReaderUnavailable(RuntimeError):
    """Image reading needs a live model (EZHUTHU_LIVE=1 on the server)."""


@dataclass(frozen=True)
class ReaderSettings:
    """``config/models.yaml`` ``reader:``."""

    max_upload_bytes: int = 5 * 1024 * 1024   # decoded image bytes; the app resizes before upload
    max_pixels: int = 40_000_000               # decompression-bomb guard (before decoding)
    max_long_side: int = 1568                  # Claude vision sees at most ~1.15 MP; larger only costs tokens
    jpeg_quality: int = 88
    max_tokens: int = 3000
    max_lines: int = 60
    max_text_bytes: int = 512 * 1024           # .txt / .xml uploads
    escalate_if_confidence_below: float | None = None  # None: routing.escalate_if_confidence_below
    request_budget_s: float = 25.0         # the proxy gives AgentCore 27 s; keep 2 s for decode and transport
    escalate_min_remaining_s: float = 15.0  # Opus vision takes ~10-15 s (eval/reports/2026-11-02-ocr-eval.md)
    reread_token_ttl_s: int = 900          # how long the "read again" offer stays valid


def reader_settings(config: ModelsConfig) -> ReaderSettings:
    raw = getattr(config, "reader", None) or {}
    return ReaderSettings(**{k: v for k, v in raw.items() if k in ReaderSettings.__dataclass_fields__})


# ---------------------------------------------------------------------------------------------------------------
# images


@dataclass
class PreparedImage:
    data: bytes          # JPEG, no metadata
    format: str          # "jpeg"
    width: int
    height: int
    source_format: str   # what was uploaded (JPEG, PNG, WEBP, HEIF, ...)
    source_bytes: int
    resized: bool
    metadata_removed: list[str] = field(default_factory=list)

    def to_api(self) -> dict[str, Any]:
        return {"width": self.width, "height": self.height, "bytes": len(self.data), "format": self.format,
                "source_format": self.source_format.lower(), "source_bytes": self.source_bytes,
                "resized": self.resized, "metadata_removed": self.metadata_removed}


SOURCE_FORMATS = {"JPEG", "PNG", "WEBP", "HEIF", "HEIC", "MPO"}


def _register_heif() -> bool:
    try:  # optional: browsers convert HEIC to JPEG on upload (iOS "Most Compatible"); this covers direct API use
        from pillow_heif import register_heif_opener  # type: ignore[import-not-found]

        register_heif_opener()
        return True
    except ImportError:
        return False


def decode_base64_image(b64: str, *, max_bytes: int) -> bytes:
    if not isinstance(b64, str) or not b64:
        raise ReadError("empty", "image_base64 is empty")
    if b64.startswith("data:"):
        b64 = b64.split(",", 1)[-1]
    # 4 base64 chars -> 3 bytes: refuse before decoding anything too large.
    if len(b64) * 3 // 4 > max_bytes + 3:
        raise ReadError("too_large", f"image is larger than {max_bytes // (1024 * 1024)} MB; resize it first")
    try:
        data = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ReadError("bad_base64", "image_base64 is not valid base64") from exc
    if len(data) > max_bytes:
        raise ReadError("too_large", f"image is larger than {max_bytes // (1024 * 1024)} MB; resize it first")
    return data


def flatten_on_white(im):
    """RGB copy of ``im``; transparent pixels become white (``convert("RGB")`` alone turns them black, which hides
    black text drawn on a transparent PNG)."""
    from PIL import Image

    has_alpha = im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info) \
        or (im.mode in ("RGB", "L") and "transparency" in im.info)
    if not has_alpha:
        return im.convert("RGB")
    rgba = im.convert("RGBA")
    bg = Image.new("RGB", rgba.size, (255, 255, 255))
    bg.paste(rgba, mask=rgba.getchannel("A"))
    return bg


def prepare_image(data: bytes, settings: ReaderSettings | None = None) -> PreparedImage:
    """Validate, auto-rotate, downscale and re-encode an uploaded image without metadata."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    s = settings or ReaderSettings()
    if len(data) > s.max_upload_bytes:
        raise ReadError("too_large", f"image is larger than {s.max_upload_bytes // (1024 * 1024)} MB; resize it first")
    is_heif = data[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1", b"ftypmsf1", b"ftyphevc")
    if is_heif and not _register_heif():
        raise ReadError("unsupported_format", "HEIC photos are not supported here; export the photo as JPEG")
    try:
        im = Image.open(io.BytesIO(data))
        fmt = (im.format or "").upper()
        w, h = im.size
        if fmt not in SOURCE_FORMATS:
            raise ReadError("unsupported_format", f"unsupported image format {fmt or 'unknown'}; use JPEG, PNG or WebP")
        if w * h > s.max_pixels:
            raise ReadError("too_large", f"image is {w}x{h} pixels; the limit is {s.max_pixels // 1_000_000} MP")
        removed = []
        info = im.info or {}
        exif = im.getexif()
        if exif:
            removed.append("exif")
            if 0x8825 in exif:  # GPSInfo IFD pointer
                removed.append("gps")
        for key in ("xmp", "XML:com.adobe.xmp", "icc_profile", "comment", "photoshop"):
            if key in info:
                removed.append({"XML:com.adobe.xmp": "xmp"}.get(key, key))
        im = ImageOps.exif_transpose(im)
        if getattr(im, "n_frames", 1) > 1:
            im.seek(0)
        im = flatten_on_white(im)
    except ReadError:
        raise
    except Image.DecompressionBombError as exc:  # Pillow's own guard (> ~179 MP) fires inside Image.open
        raise ReadError("too_large", f"image is too large to decode; the limit is {s.max_pixels // 1_000_000} MP") \
            from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ReadError("bad_image", f"could not read the image ({type(exc).__name__})") from exc
    resized = max(im.size) > s.max_long_side
    if resized:
        im.thumbnail((s.max_long_side, s.max_long_side), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    # A fresh RGB image saved without exif=/icc_profile=/xmp= carries no metadata.
    im.save(out, format="JPEG", quality=s.jpeg_quality, optimize=True)
    return PreparedImage(out.getvalue(), "jpeg", im.size[0], im.size[1], fmt, len(data), resized,
                         sorted(set(removed)))


# ---------------------------------------------------------------------------------------------------------------
# prompts and parsing

READER_SYSTEM = (
    "You are an expert Tamil epigraphist and palaeographer. You read photographs of inscriptions (stone, copper "
    "plate, palm leaf) and printed or handwritten pages in Tamil-Brahmi, Vatteluttu, Grantha, Pallava-, Chola- "
    "and later Tamil, and modern Tamil. You transcribe exactly what is visible, never what the text should say: "
    "you do not restore, complete formulae or correct spelling. Answer with JSON only."
)


def reader_prompt(*, hint: str | None = None) -> str:
    extra = f"\nThe uploader says: {hint[:200]!r} (a hint only; trust the image)." if hint else ""
    return (
        "Transcribe the text in this image line by line, top to bottom, as it is written.\n"
        "Rules:\n"
        "- Write each line in ISO-15919 transliteration as DHARMA editions use it (a ā i ī u ū e ē o ō, k ṅ c ñ ṭ ṇ "
        "t n p m y r l v ḻ ḷ ṟ ṉ, Grantha ś ṣ s j h). Lower case. Keep word spaces as you see them.\n"
        "- Where letters are lost, broken or illegible, write [?N] with N = your estimate of the number of "
        "letters (aksharas) missing, or [?] if you cannot estimate. Never guess hidden letters.\n"
        "- Do not add punctuation, translations or line numbers inside the text.\n"
        "- Give each line your probability (0 to 1) that the transcription is letter-for-letter right.\n"
        "- Identify the script: one of tamil-brahmi, vatteluttu, grantha, pallava-tamil, chola-tamil, "
        "modern-tamil, unknown (modern-tamil for printed or present-day text), an era guess in a few words, and "
        "your probability that the script is right.\n"
        "- kind: inscription | printed | handwritten | other. If there is no readable Tamil-family text, return "
        "no lines and say why in note.\n"
        "Reply with ONE line of JSON: {\"script\": \"...\", \"script_confidence\": p, \"era\": \"...\", "
        "\"kind\": \"...\", \"lines\": [[\"<iso text>\", p], ...], \"confidence\": p, \"note\": \"...\"}"
        + extra
    )


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
_LINE_PAIR_RE = re.compile(r"\[\s*\"((?:[^\"\\]|\\.)*)\"\s*,\s*(-?[0-9.]+)\s*\]")


def _prob(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else min(1.0, max(0.0, f))


def parse_reader_reply(text: str) -> dict[str, Any]:
    """Parse the model's JSON. A reply cut at max_tokens keeps every complete ``["line", p]`` pair."""
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\s*|\s*```$", "", raw)
    m = _JSON_RE.search(raw)
    data: dict[str, Any] | None = None
    if m:
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            data = None
    if not isinstance(data, dict):
        pairs = [[json.loads(f'"{t}"'), float(p)] for t, p in _LINE_PAIR_RE.findall(raw)]
        sm = re.search(r'"script"\s*:\s*"([a-z-]+)"', raw)
        data = {"lines": pairs, "script": sm.group(1) if sm else "unknown", "partial": True}
    lines = []
    for item in data.get("lines") or []:
        if isinstance(item, (list, tuple)) and item:
            lines.append((str(item[0]), _prob(item[1]) if len(item) > 1 else None))
        elif isinstance(item, dict):
            lines.append((str(item.get("iso") or item.get("text") or ""), _prob(item.get("confidence"))))
        elif isinstance(item, str):
            lines.append((item, None))
    script = str(data.get("script") or "unknown").strip().lower().replace("_", "-").replace(" ", "-")
    if script not in SCRIPTS:
        script = {"brahmi": "tamil-brahmi", "tamil": "modern-tamil", "vattezhuthu": "vatteluttu",
                  "vatteḻuttu": "vatteluttu"}.get(script, "unknown")
    return {"lines": lines, "script": script, "script_confidence": _prob(data.get("script_confidence")),
            "era": str(data.get("era") or "")[:120] or None, "kind": str(data.get("kind") or "")[:20] or None,
            "confidence": _prob(data.get("confidence")), "note": str(data.get("note") or "")[:400] or None,
            "partial": bool(data.get("partial"))}


# ---------------------------------------------------------------------------------------------------------------
# per-glyph reading (letter by letter, on boxes someone drew around the carved letters)

GLYPH_MAX_BOXES = 40


def glyph_prompt(n_boxes: int, *, script: str | None = None, line_hint: str | None = None) -> str:
    """Ask for the modern Tamil letter behind each numbered box. The first image is the clean photo, the second the
    same photo with boxes 1..n drawn on it (outlines and numbers only, so the strokes stay visible in the first)."""
    era = f"\nThe script is probably {SCRIPT_LABELS.get(script, (script,))[0]}." if script else ""
    hint = (f"\nA line-level reading of this line was {line_hint[:200]!r}; it may be wrong or split differently. "
            "Read each box from the image.") if line_hint else ""
    return (
        f"Two images of the same line of an inscription. In the second, {n_boxes} carved letters are outlined and "
        f"numbered 1 to {n_boxes} from left to right; the first is the same photo without marks.\n"
        "For EACH numbered box, say which letter of today's Tamil script the carved letter in it is: one akshara "
        "(an independent vowel, or a consonant with its vowel sign, or a consonant with pulli). If the box holds two "
        "letters, give both. If it is worn beyond reading, give \"?\" and a low probability. Never guess from what "
        "the text should say: read the shape." + era + hint + "\n"
        "Give your probability (0 to 1) that the letter is right, its ISO-15919 transliteration, and a short note on "
        "the old letterform (what differs from today's shape), at most 12 words.\n"
        f"Reply with ONE line of JSON: {{\"glyphs\": [{{\"box\": 1, \"ta\": \"<Tamil>\", \"iso\": \"<iso>\", "
        f"\"p\": 0.0, \"note\": \"...\"}}, ...]}} with exactly {n_boxes} entries."
    )


def _glyph_ta(raw: Any) -> str | None:
    s = unicodedata.normalize("NFC", str(raw or "")).strip()
    if not s or s in ("?", "[?]", "[?1]"):
        return None
    s = "".join(ch for ch in s if "஀" <= ch <= "௿")
    return s[:8] or None


def parse_glyph_reply(text: str, n_boxes: int) -> list[dict[str, Any]]:
    """One entry per box 1..n_boxes: ``{"box", "ta", "iso", "confidence", "note"}``. ``ta`` is None where the model
    gave no Tamil letter (worn, or missing from the reply), with confidence 0 if it said nothing about that box."""
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\s*|\s*```$", "", raw)
    m = _JSON_RE.search(raw)
    items: list[Any] = []
    if m:
        try:
            data = json.loads(m.group(0))
            items = data.get("glyphs") or [] if isinstance(data, dict) else []
        except json.JSONDecodeError:
            items = [json.loads(g) for g in re.findall(r"\{[^{}]*\"box\"[^{}]*\}", raw) if _loads_ok(g)]
    by_box: dict[int, dict[str, Any]] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            b = int(it.get("box"))
        except (TypeError, ValueError):
            continue
        if 1 <= b <= n_boxes and b not in by_box:
            by_box[b] = it
    out = []
    for b in range(1, n_boxes + 1):
        it = by_box.get(b, {})
        ta = _glyph_ta(it.get("ta"))
        iso = tamil_to_iso(ta) if ta else None
        conf = _prob(it.get("p", it.get("confidence")))
        out.append({"box": b, "ta": ta, "iso": iso, "confidence": 0.0 if not it else conf,
                    "note": (str(it.get("note") or "").strip()[:120] or None)})
    return out


def _loads_ok(s: str) -> bool:
    try:
        json.loads(s)
        return True
    except json.JSONDecodeError:
        return False


# ---------------------------------------------------------------------------------------------------------------
# line normalisation (image, text and XML all end here)

_DOTS_RE = re.compile(r"(?:\.\s*){3,}|…+")
_BRACKET_LOST_RE = re.compile(r"\[(?:\s*[.\-–—x×]+\s*)\]")  # "[...]", "[--]", "[xx]" = lost letters


def clean_line(text: str) -> tuple[str, list[str]]:
    """Return (ISO line, dropped characters). Tamil script is transliterated; '...' and '[...]' become ``[?]``;
    characters the restore API would refuse are dropped (and reported)."""
    t = unicodedata.normalize("NFC", text or "").replace("\t", " ").strip()
    t = _BRACKET_LOST_RE.sub("[?]", t)
    t = _DOTS_RE.sub(" [?] ", t)
    t = re.sub(r"\[\s*\?\s*(\d*)\s*\]", lambda m: f"[?{m.group(1)}]", t)
    if looks_tamil(t):
        t = tamil_to_iso(t)
    t = t.lower()
    dropped: list[str] = []
    out: list[str] = []
    pos = 0
    for m in GAP_RE.finditer(t):
        out.append(t[pos:m.start()])
        n = m.group(1)
        out.append(f"[?{min(int(n), 60)}]" if n and int(n) > 0 else "[?]")
        pos = m.end()
    out.append(t[pos:])
    parts = GAP_RE.split("".join(out))  # [text, N, text, N, text]
    kept: list[str] = []
    for i, part in enumerate(parts):
        if i % 2:
            kept.append(f"[?{part}]")
            continue
        bad = non_iso_chars(part, extra_allowed=ALLOWED_PUNCT.replace("[", "").replace("]", "").replace("?", ""))
        if bad:
            dropped.extend(bad)
            part = unicodedata.normalize("NFC", "".join(
                ch for ch in unicodedata.normalize("NFD", part) if ch not in bad))
        kept.append(part)
    joined = "".join(kept)
    joined = re.sub(r"[ ]{2,}", " ", joined).strip()
    return joined, sorted(set(dropped))


def _tamil(iso: str) -> str:
    from ..corpus.script import iso_to_tamil_display

    return iso_to_tamil_display(iso)


# Warnings carry a stable ``code`` (+ ``params``) so the app can show them in Tamil (app/web/src/i18n/strings.ts
# ``read.warn.<code>``); ``message`` is the English fallback that also goes into ``warnings``.
WARNING_CODES = ("cut_short", "dropped_chars", "no_text_in_image", "low_reliability_script", "unsure",
                 "lines_capped", "masked_supplied")


def _warn(code: str, message: str, **params: Any) -> dict[str, Any]:
    assert code in WARNING_CODES, code
    return {"code": code, "message": message, "params": params}


def _dropped_warning(dropped: set[str]) -> dict[str, Any]:
    chars = "".join(sorted(dropped))[:40]
    return _warn("dropped_chars", "dropped characters that are not Tamil or ISO-15919: " + chars, chars=chars)


def _capped_warning(max_lines: int) -> dict[str, Any]:
    return _warn("lines_capped", f"only the first {max_lines} lines were kept", max=max_lines)


def _line(n: str, iso: str, confidence: float | None) -> dict[str, Any]:
    return {"n": n, "text": iso, "text_tamil": _tamil(iso), "confidence": confidence,
            "gaps": len(GAP_RE.findall(iso))}


# ---------------------------------------------------------------------------------------------------------------
# text and EpiDoc uploads


def read_text_file(content: str, *, max_lines: int = 60) -> dict[str, Any]:
    lines, dropped = [], set()
    for raw in content.splitlines():
        raw = re.sub(r"^\s*(?:\(?\d{1,3}[.)]|l\.\s*\d+)\s+", "", raw)  # "1. ", "(2) ", "l. 3 " line numbers
        if not raw.strip():
            continue
        iso, bad = clean_line(raw)
        dropped.update(bad)
        if iso:
            lines.append(_line(str(len(lines) + 1), iso, None))
    warnings = []
    if len(lines) > max_lines:
        warnings.append(_capped_warning(max_lines))
        lines = lines[:max_lines]
    if dropped:
        warnings.append(_dropped_warning(dropped))
    return {"lines": lines, "warnings": warnings}


def _safe_parser():
    from lxml import etree

    return etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False,
                           remove_comments=True)


def read_epidoc(content: bytes, *, max_lines: int = 60) -> dict[str, Any]:
    """DHARMA EpiDoc/TEI: the edition's lines, with ``<supplied>`` restorations masked as ``[?N]`` gaps."""
    from lxml import etree

    from ..corpus import epidoc

    try:
        root = etree.fromstring(content, _safe_parser())
    except etree.XMLSyntaxError as exc:
        raise ReadError("bad_xml", f"not well-formed XML: {exc}") from exc
    if root.tag != f"{{{epidoc.TEI}}}TEI":
        raise ReadError("not_epidoc", "XML is not a TEI/EpiDoc document (root element must be tei:TEI)")
    edition = root.find(".//t:body/t:div[@type='edition']", epidoc.NS)
    if edition is None:
        edition = root.find(".//t:div[@type='edition']", epidoc.NS)
    if edition is None:
        raise ReadError("not_epidoc", "TEI document has no <div type=\"edition\">")
    parsed = epidoc.parse_edition(edition)
    title_el = root.find(".//t:titleStmt/t:title", epidoc.NS)
    title = " ".join("".join(title_el.itertext()).split()) if title_el is not None else None
    licence_el = root.find(".//t:availability/t:licence", epidoc.NS)
    idno_el = root.find(".//t:publicationStmt/t:idno[@type='filename']", epidoc.NS)
    if idno_el is None:
        idno_el = root.find(".//t:idno[@type='filename']", epidoc.NS)
    ins_id = re.sub(r"\.xml$", "", (idno_el.text or "").strip()) if idno_el is not None else ""
    ins_id = ins_id if re.fullmatch(r"DHARMA_[A-Za-z0-9_]{1,80}", ins_id) else None
    lines, masked, dropped = [], 0, set()
    for ln in parsed:
        masked += len(ln.spans_of("supplied"))
        iso, bad = clean_line(ln.masked())
        dropped.update(bad)
        if iso.strip():
            lines.append(_line(ln.n or str(len(lines) + 1), iso, None))
    warnings = []
    if masked:
        warnings.append(_warn("masked_supplied", f"{masked} editorial restoration(s) (<supplied>) are shown as gaps "
                              "for you to restore", n=masked))
    if len(lines) > max_lines:
        warnings.append(_capped_warning(max_lines))
        lines = lines[:max_lines]
    if dropped:
        warnings.append(_dropped_warning(dropped))
    licence = " ".join("".join(licence_el.itertext()).split())[:200] if licence_el is not None else None
    licence_url = (licence_el.get("target") or "").strip() if licence_el is not None else ""
    return {"lines": lines, "warnings": warnings, "title": title,
            "licence": licence or None, "masked_supplied": masked,
            "licence_url": licence_url if re.fullmatch(r"https://[^\s\"<>]{1,200}", licence_url) else None,
            "inscription_id": ins_id,
            "source_url": f"https://dharmalekha.info/texts/{ins_id}" if ins_id else None}


# ---------------------------------------------------------------------------------------------------------------
# the reader


@dataclass
class _Attempt:
    role: str
    parsed: dict[str, Any]
    response: LLMResponse
    elapsed_s: float


class RereadTokens:
    """One-time tokens for "read this photo again with Opus" (``router: "opus"``).

    ``POST /api/read`` is public, so the expensive model is not a free choice: a token is issued only when a routed
    read skipped escalation for lack of time, it is bound to a hash of the uploaded bytes, it expires after
    ``ttl_s`` and it is consumed by a conditional write (``Store.put_if_status``), so it buys exactly one Opus read
    of that photo. Stored in the service's store (DynamoDB ``READTOKEN#<id>`` in the cloud)."""

    def __init__(self, store: Any | None = None, *, ttl_s: int = 900, clock=time.time):
        if store is None:
            from ..api.storage import MemoryStore

            store = MemoryStore()
        self.store, self.ttl_s, self.clock = store, ttl_s, clock

    def issue(self, image_sha256: str) -> str:
        token = uuid.uuid4().hex
        self.store.put("read_token", token, {"status": "issued", "image": image_sha256,
                                             "expires_at": self.clock() + self.ttl_s})
        return token

    def consume(self, token: str | None, image_sha256: str) -> bool:
        if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{32}", token):
            return False
        doc = self.store.get("read_token", token)
        if not doc or doc.get("status") != "issued" or doc.get("image") != image_sha256 \
                or float(doc.get("expires_at", 0)) < self.clock():
            return False
        return self.store.put_if_status("read_token", token, {**doc, "status": "used"}, "issued")


class Reader:
    """Image/text/EpiDoc to transcription lines. ``llm`` must support ``complete_image`` for images."""

    def __init__(self, llm: LLMClient | None = None, config: ModelsConfig | None = None,
                 settings: ReaderSettings | None = None, clock=time.perf_counter, store: Any | None = None):
        self.llm = llm
        self.config = config or (llm.config if llm is not None else load_models_config())
        self.settings = settings or reader_settings(self.config)
        self.clock = clock
        self.tokens = RereadTokens(store, ttl_s=self.settings.reread_token_ttl_s)

    @property
    def escalate_below(self) -> float:
        s = self.settings.escalate_if_confidence_below
        return self.config.routing.escalate_if_confidence_below if s is None else s

    # ---- public entry points ----------------------------------------------------------------------------------
    def read(self, *, image_base64: str | None = None, text: str | None = None, filename: str | None = None,
             format: str = "auto", router: str = "routed", hint: str | None = None,
             reread_token: str | None = None) -> dict[str, Any]:
        t0 = self.clock()
        if router not in ROUTERS:
            raise ReadError("bad_router", f"router must be one of {ROUTERS}")
        if (image_base64 is None) == (text is None):
            raise ReadError("bad_request", "send exactly one of image_base64 or text")
        if image_base64 is not None:
            if self.llm is None or not hasattr(self.llm, "complete_image"):
                raise ReaderUnavailable("photo reading needs a live model on the server (EZHUTHU_LIVE=1)")
            data = decode_base64_image(image_base64, max_bytes=self.settings.max_upload_bytes)
            digest = hashlib.sha256(data).hexdigest()
            if router == "opus" and not self.tokens.consume(reread_token, digest):
                raise ReadError("reread_token_invalid", "router 'opus' is only for reading the same photo again "
                                "after a read that ran out of time: send that response's reread_token (it works once)")
            out = self.read_image(prepare_image(data, self.settings), router=router, hint=hint,
                                  deadline=t0 + self.settings.request_budget_s)
            if out.get("escalation_skipped") == "time_budget":
                out["reread_token"] = self.tokens.issue(digest)
        else:
            out = self.read_file(text or "", filename=filename, format=format)
        out["trace_id"] = uuid.uuid4().hex
        out["latency_ms"] = round((self.clock() - t0) * 1000, 1)
        return out

    def read_file(self, content: str, *, filename: str | None = None, format: str = "auto") -> dict[str, Any]:
        if len(content.encode("utf-8")) > self.settings.max_text_bytes:
            raise ReadError("too_large", f"text files are limited to {self.settings.max_text_bytes // 1024} KB")
        fmt = format
        if fmt == "auto":
            name = (filename or "").lower()
            head = content.lstrip()[:400]
            fmt = "epidoc" if name.endswith(".xml") or head.startswith("<?xml") or "<TEI" in head else "txt"
        if fmt not in ("txt", "epidoc"):
            raise ReadError("bad_format", "format must be auto, txt or epidoc")
        if fmt == "epidoc":
            body = read_epidoc(content.encode("utf-8"), max_lines=self.settings.max_lines)
            source = "epidoc"
        else:
            body = read_text_file(content, max_lines=self.settings.max_lines)
            source = "text"
        if not body["lines"]:
            raise ReadError("no_text", "no Tamil or ISO-15919 text found in the file")
        return self._envelope(source, body["lines"], warnings=body["warnings"], script=None,
                              extra={k: body[k] for k in ("title", "licence", "licence_url", "masked_supplied",
                                                          "inscription_id", "source_url") if k in body})

    def read_image(self, img: PreparedImage, *, router: str = "routed", hint: str | None = None,
                   deadline: float | None = None) -> dict[str, Any]:
        """Read ``img``. ``deadline`` (a ``self.clock()`` time) bounds the request: the first call gets the whole
        remaining budget, escalation starts only with ``escalate_min_remaining_s`` left and is itself bounded."""
        if self.llm is None or not hasattr(self.llm, "complete_image"):
            raise ReaderUnavailable("photo reading needs a live model on the server (EZHUTHU_LIVE=1)")
        if deadline is None:
            deadline = self.clock() + self.settings.request_budget_s
        first_role = "escalate" if router == "opus" else "default"
        attempts = [self._attempt(first_role, img, hint, deadline)]
        escalated, skipped = first_role == "escalate", None
        best = attempts[0]
        conf = self._conf(best.parsed)
        if router == "routed" and (conf is None or conf < self.escalate_below):
            if deadline - self.clock() >= self.settings.escalate_min_remaining_s:
                try:
                    second = self._attempt("escalate", img, hint, deadline)
                except LiveCallsDisabled:
                    skipped = "budget"
                except Exception as exc:  # noqa: BLE001  (throttled, timed out, Bedrock error: keep the first read)
                    log.warning("reader escalation failed (%s); keeping the first reading", type(exc).__name__)
                    skipped = "error"
                else:
                    attempts.append(second)
                    escalated = True
                    if self._better(second, best):
                        best = second
            else:
                skipped = "time_budget"
        p = best.parsed
        lines, dropped = [], set()
        for i, (raw, c) in enumerate(p["lines"][: self.settings.max_lines]):
            iso, bad = clean_line(raw)
            dropped.update(bad)
            if iso:
                lines.append(_line(str(i + 1), iso, c))
        warnings = []
        if best.response.truncated or p.get("partial"):
            warnings.append(_warn("cut_short", "the reading was cut short; later lines may be missing"))
        if dropped:
            warnings.append(_dropped_warning(dropped))
        if not lines:
            warnings.append(_warn("no_text_in_image", "no readable Tamil-family text was found in the image"))
        elif p["script"] in LOW_RELIABILITY_SCRIPTS:
            warnings.append(_warn(
                "low_reliability_script",
                f"Ezhuthu cannot yet read {SCRIPT_LABELS[p['script']][0]} reliably from photos (measured error rate "
                "above 50%): treat these letters as a guess and compare them with a published edition",
                script=p["script"]))
        elif (self._conf(p) or 0.0) < LOW_CONFIDENCE:
            warnings.append(_warn("unsure", "the reader is unsure about much of this reading; check every line "
                                  "against the stone"))
        script = {"script": p["script"], "label_en": SCRIPT_LABELS[p["script"]][0],
                  "label_ta": SCRIPT_LABELS[p["script"]][1], "era": p["era"],
                  "confidence": p["script_confidence"], "level": SCRIPT_LEVEL.get(p["script"])}
        models = []
        for a in attempts:
            s = short_name(a.response.model_id)
            if s not in models:
                models.append(s)
        out = self._envelope("image", lines, warnings=warnings, script=script, extra={
            "confidence": self._conf(p), "kind": p["kind"], "note": p["note"], "image": img.to_api(),
            "models_used": models, "escalated": escalated, "model": short_name(best.response.model_id),
        })
        if skipped:
            out["escalation_skipped"] = skipped
        return out

    def read_glyphs(self, clean: PreparedImage, marked: PreparedImage, n_boxes: int, *, role: str = "escalate",
                    script: str | None = None, line_hint: str | None = None) -> dict[str, Any]:
        """Letter-by-letter reading: the modern Tamil letter and a probability for each of ``n_boxes`` numbered
        boxes drawn on ``marked`` (``clean`` is the same crop without marks). Used offline to build the home hero
        (scripts/hero_read.py glyphs); not an API route. One model call."""
        if self.llm is None or not hasattr(self.llm, "complete_image"):
            raise ReaderUnavailable("photo reading needs a live model (EZHUTHU_LIVE=1)")
        if not 1 <= n_boxes <= GLYPH_MAX_BOXES:
            raise ReadError("bad_request", f"n_boxes must be 1..{GLYPH_MAX_BOXES}")
        r = self.llm.complete_image(role, READER_SYSTEM, glyph_prompt(n_boxes, script=script, line_hint=line_hint),
                                    [(clean.data, clean.format), (marked.data, marked.format)],
                                    max_tokens=self.settings.max_tokens,
                                    timeout_s=self.settings.request_budget_s * 4)
        return {"glyphs": parse_glyph_reply(r.text, n_boxes), "model": short_name(r.model_id),
                "truncated": bool(r.truncated)}

    # ---- internals ---------------------------------------------------------------------------------------------
    @staticmethod
    def _conf(parsed: dict[str, Any]) -> float | None:
        if parsed.get("confidence") is not None:
            return parsed["confidence"]
        cs = [c for _, c in parsed["lines"] if c is not None]
        return round(sum(cs) / len(cs), 3) if cs else None

    def _better(self, new: _Attempt, old: _Attempt) -> bool:
        """Keep the escalated reading only if it has lines and is more confident (a tie keeps the first: the OCR
        eval found no accuracy gain from Opus, eval/reports/2026-11-02-ocr-eval.md)."""
        if not new.parsed["lines"]:
            return False
        if not old.parsed["lines"]:
            return True
        return (self._conf(new.parsed) or 0.0) > (self._conf(old.parsed) or 0.0)

    def _attempt(self, role: str, img: PreparedImage, hint: str | None, deadline: float) -> _Attempt:
        t = self.clock()
        r = self.llm.complete_image(role, READER_SYSTEM, reader_prompt(hint=hint),  # type: ignore[union-attr]
                                    [(img.data, img.format)], max_tokens=self.settings.max_tokens,
                                    timeout_s=max(1.0, deadline - t))
        return _Attempt(role, parse_reader_reply(r.text), r, self.clock() - t)

    def _envelope(self, source: str, lines: list[dict[str, Any]], *, warnings: list[str],
                  script: dict[str, Any] | None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        text = "\n".join(ln["text"] for ln in lines)
        out: dict[str, Any] = {
            "source": source, "experimental": source == "image", "lines": lines, "text": text,
            "text_tamil": "\n".join(ln["text_tamil"] for ln in lines),
            "gaps": sum(ln["gaps"] for ln in lines), "script_guess": script, "confidence": None,
            "models_used": [], "escalated": False,
            "warnings": [w["message"] for w in warnings],
            "warning_codes": [{"code": w["code"], "params": w["params"]} for w in warnings],
        }
        out.update(extra or {})
        return out
