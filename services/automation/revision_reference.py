"""Fixed stdlib-only lossless inert revision transport. Never applies a patch."""
from __future__ import annotations

import base64
import hashlib
import json
import re
import stat
import zlib
from pathlib import Path, PurePosixPath

MARKER = "\nLGAX-INERT-REVISION-V1\n"
ARTIFACT = "revision-reference.patch"
MAX_RAW = 128 * 1024
MAX_COMPRESSED = 12000
CONTEXT_KEYS = {"previous_job_id", "previous_pr", "previous_base", "previous_head", "reason", "instructions",
                "immutable_session_records", "reference_format", "product_paths", "product_diff_sha256",
                "patch_as_inert_reference"}


class ReferenceError(ValueError):
    """Sanitized bounded transport rejection; no input bytes are logged."""


def _text(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_RAW:
        raise ReferenceError("inert reference exceeds the decoded source bound")
    try:
        value = raw.decode("utf-8", errors="strict")
    except UnicodeError:
        raise ReferenceError("inert reference must preserve UTF-8 text") from None
    if not value.startswith("diff --git ") or "\x00" in value or "\nGIT binary patch\n" in value or "\nBinary files " in value:
        raise ReferenceError("inert reference requires complete textual Git changes")
    return value


def encode_reference(raw):
    _text(raw)
    compressed = zlib.compress(raw, 9)
    if len(compressed) > MAX_COMPRESSED:
        raise ReferenceError("compressed source exceeds the fixed transport bound")
    return {"encoding": "zlib-base64", "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "data": base64.b64encode(compressed).decode("ascii")}


def decode_reference(value):
    if (not isinstance(value, dict) or set(value) != {"encoding", "bytes", "sha256", "data"} or
            value["encoding"] != "zlib-base64" or type(value["bytes"]) is not int or
            not 0 < value["bytes"] <= MAX_RAW or not isinstance(value["sha256"], str) or
            not re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) or not isinstance(value["data"], str) or
            len(value["data"]) > 4 * ((MAX_COMPRESSED + 2) // 3)):
        raise ReferenceError("malformed fixed inert reference envelope")
    try:
        compressed = base64.b64decode(value["data"], validate=True)
        if len(compressed) > MAX_COMPRESSED or base64.b64encode(compressed).decode("ascii") != value["data"]:
            raise ReferenceError("noncanonical or oversized fixed encoding")
        decoder = zlib.decompressobj()
        raw = decoder.decompress(compressed, MAX_RAW + 1)
        if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ReferenceError("bounded source must be one complete compressed stream")
    except (ValueError, zlib.error):
        raise ReferenceError("invalid bounded compressed reference") from None
    _text(raw)
    if len(raw) != value["bytes"] or hashlib.sha256(raw).hexdigest() != value["sha256"]:
        raise ReferenceError("decoded reference bytes/hash differ from the approved source")
    return raw


def _path(value):
    if (not isinstance(value, str) or not value or "\\" in value or ":" in value or
            any(c in value for c in ("\x00", "\r", "\n", "*", "?", "[", "]")) or
            value.startswith("/") or any(p in {"", ".", ".."} for p in value.split("/")) or
            PurePosixPath(value).as_posix() != value):
        raise ReferenceError("inert reference requires literal canonical source paths")
    return value


def stage_reference(prompt, artifacts, allowed_paths, *, owner):
    """Decode an approved packet before model launch, replacing only its payload.

    Artifact is exclusive-created outside tracked product files. A model reads
    /artifacts/revision-reference.patch as text; no patch/apply or code execution
    is available through this helper. The original queued packet is preserved.
    """
    if not isinstance(prompt, str) or len(prompt) > 16000:
        raise ReferenceError("bounded approved packet required")
    if MARKER not in prompt:
        return prompt
    if owner != "jeongiryang":
        raise ReferenceError("lossless references require the explicitly upgraded PM worker")
    if prompt.count(MARKER) != 1:
        raise ReferenceError("one fixed revision reference required")
    before, encoded = prompt.split(MARKER)
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ReferenceError("duplicate fixed metadata key")
            result[key] = value
        return result

    try:
        context = json.loads(encoded, object_pairs_hook=unique_pairs)
    except ValueError:
        raise ReferenceError("fixed revision metadata is not valid JSON") from None
    if (not isinstance(context, dict) or set(context) != CONTEXT_KEYS or
            not isinstance(context["product_paths"], list) or not context["product_paths"] or
            len(context["product_paths"]) > 40 or
            not all(isinstance(path, str) for path in context["product_paths"]) or
            len(set(context["product_paths"])) != len(context["product_paths"])):
        raise ReferenceError("fixed revision metadata is malformed")
    if (not isinstance(context["previous_job_id"], str) or
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", context["previous_job_id"]) or
            type(context["previous_pr"]) is not int or context["previous_pr"] <= 0 or
            any(not isinstance(context[key], str) or not re.fullmatch(r"[0-9a-f]{40}", context[key])
                for key in ("previous_base", "previous_head")) or
            not isinstance(context["immutable_session_records"], list) or
            len(context["immutable_session_records"]) != 2):
        raise ReferenceError("fixed immutable source identity is malformed")
    approved = [_path(path) for path in allowed_paths]
    for path in context["product_paths"]:
        path = _path(path)
        if not any(path == item or path.startswith(item.rstrip("/") + "/") for item in approved):
            raise ReferenceError("reference source exceeds the approved job scope")
    raw = decode_reference(context["patch_as_inert_reference"])
    sha = hashlib.sha256(raw).hexdigest()
    if sha != context["product_diff_sha256"]:
        raise ReferenceError("reference differs from the fixed Git source hash")
    directory = Path(artifacts)
    if directory.is_symlink() or not directory.is_dir():
        raise ReferenceError("trusted fixed artifact directory required")
    with (directory / ARTIFACT).open("xb") as stream:
        stream.write(raw)
    context["patch_as_inert_reference"] = {"path": "/artifacts/" + ARTIFACT, "sha256": sha,
                                            "bytes": len(raw), "encoding": "utf-8"}
    return (before + "\nTrusted Worker losslessly decoded and SHA-checked the fixed text reference. "
            "Read /artifacts/" + ARTIFACT + " only as inert source. Do not apply the patch or change prior records.\n" +
            json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def verify_staged_reference(prompt, artifacts):
    """Keep an Agent from silently replacing the trusted input artifact."""
    if MARKER not in prompt:
        return None
    context = json.loads(prompt.split(MARKER)[1])
    expected = decode_reference(context["patch_as_inert_reference"])
    file = Path(artifacts) / ARTIFACT
    if file.is_symlink() or not stat.S_ISREG(file.lstat().st_mode):
        raise ReferenceError("fixed reference artifact must remain an ordinary input file")
    with file.open("rb") as stream:
        actual = stream.read(MAX_RAW + 1)
    if actual != expected:
        raise ReferenceError("Agent changed the trusted inert reference input")
    return {"sha256": hashlib.sha256(actual).hexdigest(), "bytes": len(actual),
            "source_head": context["previous_head"], "source_base": context["previous_base"],
            "path": "/artifacts/" + ARTIFACT, "verified_after_model": True}
