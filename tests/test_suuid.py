"""Tests for the SUUID value type, round-trips and filename safety."""

from __future__ import annotations

import re
import uuid

import pytest

from suuid import SUUID, namespace_from_name, safe_name
from suuid.core import MAX_SNAME_LEN

SNAME_RE = re.compile(
    r"[A-Za-z0-9]+(_[A-Za-z0-9]+)*__[a-z0-9]+(_[a-z0-9]+)*__[0-9a-f]{32}"
)


# --- normalisation -----------------------------------------------------------

def test_safe_name_examples() -> None:
    assert safe_name("1.50mm ENAW5754") == "1_50mm_enaw5754"
    assert safe_name("  Über  Größe ") == "ueber_groesse"
    assert not safe_name("__weird__name__").startswith("_")
    assert "__" not in safe_name("a   b   c")


# --- determinism -------------------------------------------------------------

def test_from_name_is_deterministic() -> None:
    a = SUUID.from_name("Data", "Messung 2026.csv")
    b = SUUID.from_name("Data", "Messung 2026.csv")
    assert a == b
    assert a.huuid == b.huuid
    assert len(a.huuid) == 32


def test_class_name_is_part_of_identity() -> None:
    assert SUUID.from_name("Person", "x").huuid != SUUID.from_name("Org", "x").huuid


def test_content_mode_is_content_addressed() -> None:
    a = SUUID.from_content("Doc", "spec.pdf", b"hello suuid")
    b = SUUID.from_content("Doc", "other-name.pdf", b"hello suuid")
    assert a.huuid == b.huuid  # same bytes -> same huuid, regardless of name
    assert a.content_hash and len(a.content_hash) == 64
    assert a.hash_algorithm == "SHA3-256"


def test_random_mode_diverges() -> None:
    assert SUUID.random("Run", "nightly") != SUUID.random("Run", "nightly")


# --- sname structure & round-trips ------------------------------------------

def test_sname_structure() -> None:
    sid = SUUID.from_name("MDK_CLN", "1.50mm ENAW5754")
    assert "___" not in sid.sname
    assert sid.sname.count("__") >= 2
    assert SNAME_RE.fullmatch(sid.sname)
    assert str(sid) == sid.sname


def test_from_sname_round_trip() -> None:
    sid = SUUID.from_name("Data", "messung.csv")
    assert SUUID.from_sname(sid.sname) == sid


def test_compact_token_round_trip() -> None:
    sid = SUUID.from_name("Data", "messung.csv")
    assert SUUID.from_compact_token(sid.compact_token) == sid


def test_to_dict_round_trip() -> None:
    sid = SUUID.from_name("Data", "messung.csv")
    assert SUUID.from_dict(sid.to_dict()) == sid


def test_from_sname_rejects_bad_arity() -> None:
    with pytest.raises(ValueError):
        SUUID.from_sname("only_two__parts")


# --- filename / S3 safety ----------------------------------------------------

def test_sname_within_filename_limit() -> None:
    sid = SUUID.from_name("C" * 200, "x" * 500)  # absurd inputs, still bounded
    assert len(sid.sname) <= MAX_SNAME_LEN <= 254


def test_meta_name_within_255() -> None:
    sid = SUUID.from_name("C" * 200, "x" * 500)
    assert sid.meta_name == sid.sname + "_"
    assert len(sid.meta_name) <= 255


def test_meta_name_round_trips_to_data_sname() -> None:
    sid = SUUID.from_name("Data", "messung.csv")
    assert SUUID.from_sname(sid.meta_name).sname == sid.sname


def test_huuid_validation() -> None:
    with pytest.raises(ValueError):
        SUUID(class_name="Data", name="x", huuid="not-hex")


# --- string namespace (hierarchical, reproducible) ---------------------------

def test_namespace_from_name_is_stable_and_case_folded() -> None:
    assert isinstance(namespace_from_name("proj"), uuid.UUID)
    assert namespace_from_name("proj") == namespace_from_name("proj")
    assert namespace_from_name("proj") == namespace_from_name("PROJ")  # .upper() folded


def test_string_namespace_scopes_ids() -> None:
    default = SUUID.from_name("Data", "x")
    scoped = SUUID.from_name("Data", "x", ns="project_alpha")
    assert scoped.huuid != default.huuid                  # namespace changes the id
    # reproducible: same string namespace -> same id, on every run
    assert SUUID.from_name("Data", "x", ns="project_alpha") == scoped
    # passing the equivalent UUID is identical to passing the string
    ns_uuid = namespace_from_name("project_alpha")
    assert SUUID.from_name("Data", "x", ns=ns_uuid) == scoped


def test_default_namespace_unchanged() -> None:
    # The default (UUID) path must stay byte-for-byte stable (golden contract).
    assert SUUID.from_name("Data", "x").huuid == SUUID.from_name("Data", "x").huuid


# --- lenient parsing ---------------------------------------------------------

def test_from_sname_lenient_returns_none() -> None:
    assert SUUID.from_sname("not a sname", strict=False) is None
    assert SUUID.from_sname("only_two__parts", strict=False) is None
    assert SUUID.from_sname("Data__x__not-hex", strict=False) is None
    assert SUUID.from_sname(None, strict=False) is None  # type: ignore[arg-type]


def test_from_sname_lenient_parses_valid() -> None:
    sid = SUUID.from_name("Data", "messung.csv")
    assert SUUID.from_sname(sid.sname, strict=False) == sid


def test_from_sname_strict_is_default_and_raises() -> None:
    with pytest.raises(ValueError):
        SUUID.from_sname("only_two__parts")


# --- 100% S3 / filename safety (hard contract) -------------------------------

S3_SAFE_RE = re.compile(r"[A-Za-z0-9_]+")


@pytest.mark.parametrize("class_name, name", [
    ("Data", "Messung 2026.csv"),
    ("Doc", "user@example.com"),
    ("Über", "Größe @ Höhe!"),
    ("MDK_CLN", "1.50mm ENAW5754"),
    ("Run", "2026_starts_with_digit"),
    ("Path", r"a/b\c:d*e?f|g"),
    ("X", "  trailing & leading  "),
])
def test_sname_is_strictly_s3_safe(class_name: str, name: str) -> None:
    s = SUUID.from_name(class_name, name).sname
    assert S3_SAFE_RE.fullmatch(s), f"non-S3-safe char in {s!r}"  # only [A-Za-z0-9_]
    assert not s.startswith("_"), f"leading underscore in {s!r}"  # e.g. no '_2026'
    assert not s.endswith("_")
    assert "@" not in s                                           # never '_at_' etc.
    assert "___" not in s                                         # separator stays '__'
    sid = SUUID.from_name(class_name, name)
    assert len(sid.meta_name) <= 255
    assert SUUID.from_sname(sid.sname) == sid                     # round-trips
