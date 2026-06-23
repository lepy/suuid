"""Tests for the SUUID value type, round-trips and filename safety."""

from __future__ import annotations

import re

import pytest

from suuid import SUUID, safe_name
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
