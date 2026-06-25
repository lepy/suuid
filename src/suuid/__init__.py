"""suuid — semantic, filename-safe UUIDs.

A SUUID is a 3-part identifier ``<ClassName>__<safe_name>__<huuid>`` that is safe
to use as an S3 object key or a filename, and short enough (``<= 254`` chars) that
a metadata sibling key ``sname + "_"`` still fits the 255-char limit.

Quick start::

    from suuid import SUUID

    sid = SUUID.from_name("Data", "Messung 2026.csv")
    sid.sname        # 'Data__messung_2026_csv__<huuid>'
    sid.meta_name    # data + '_'  → the metadata object key
    SUUID.from_sname(sid.sname) == sid   # round-trips
"""

from __future__ import annotations

from suuid._normalize import (
    NORMALIZATION_SPEC,
    SEP,
    clean_class_name,
    safe_name,
)
from suuid.core import (
    CONTENT_ALGO,
    MAX_SNAME_LEN,
    OID_NAMESPACE,
    SUUID,
    content_huuid,
    name_deterministic_huuid,
    namespace_from_name,
)

__version__ = "0.1.0"

__all__ = [
    "SUUID",
    "safe_name",
    "clean_class_name",
    "name_deterministic_huuid",
    "content_huuid",
    "namespace_from_name",
    "SEP",
    "MAX_SNAME_LEN",
    "OID_NAMESPACE",
    "CONTENT_ALGO",
    "NORMALIZATION_SPEC",
    "__version__",
]
