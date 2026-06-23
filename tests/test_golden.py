"""Golden vectors — pin the frozen normalisation + uuid5 contract.

If any of these change, the normalisation spec changed and every
name-deterministic identifier in existing data has been invalidated. Treat a
failure here as a breaking change, not a test to "fix".
"""

from __future__ import annotations

import hashlib
import uuid

from suuid import SUUID, name_deterministic_huuid


def test_golden_name_huuid() -> None:
    assert name_deterministic_huuid("MDK_CLN", "1.50mm ENAW5754") == (
        "9e51448c57ab5ef1b92d0c27f554a49e"
    )


def test_golden_sname() -> None:
    sid = SUUID.from_name("MDK_CLN", "1.50mm ENAW5754")
    assert sid.sname == "MDK_CLN__1_50mm_enaw5754__9e51448c57ab5ef1b92d0c27f554a49e"


def test_golden_content_huuid() -> None:
    sid = SUUID.from_content("Doc", "spec.pdf", b"hello suuid")
    digest = hashlib.sha3_256(b"hello suuid").hexdigest()
    expected = uuid.uuid5(uuid.NAMESPACE_OID, digest).hex
    assert sid.content_hash == digest
    assert sid.huuid == expected
