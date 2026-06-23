"""Frozen normalisation for SUUID — the reproducibility contract.

Reproducibility is a property of *this pinned function*: the same input always
yields the same identifier, on every run and machine. The rules below are
therefore frozen and versioned by :data:`NORMALIZATION_SPEC` — changing any of
them re-mints every name-deterministic huuid and is a breaking change.

Frozen rules (``NORMALIZATION_SPEC = "v1"``):

* Umlaut → ASCII table (German ``ue/oe/ae/ss``) applied *before* NFKD.
* NFKD decomposition + ASCII drop (removes combining marks).
* lowercase, character class ``[a-z0-9]``; disallowed runs collapse to a single
  ``_``; **no** leading/trailing ``_`` and **no** ``__`` (separator protection).
* ``.upper()`` of ``class + safe_name`` feeds the ``uuid5`` hash.
* Separator is exactly ``"__"`` (never ``"___"``); substrings are length-capped
  so a 3-part ``sname`` is a valid filename (see :mod:`suuid.core`).

Stdlib-only (``re``, ``unicodedata``) — runs on any Python 3.10+.
"""

from __future__ import annotations

import re
import unicodedata

#: Version tag of the frozen normalisation rules. Bumping this is a breaking
#: change: it re-mints every name-deterministic huuid.
NORMALIZATION_SPEC = "v1"

#: Exact 3-part separator. Never appears inside a cleaned class/safe substring,
#: which is what makes :func:`suuid.core.SUUID.from_sname` an unambiguous split.
SEP = "__"

#: Class component cap (case preserved, e.g. ``MDK_CLN``).
CLASS_MAXLEN = 64
#: Safe-name component cap. Budgeted so the full ``sname`` — and its metadata
#: sibling ``sname + "_"`` — both stay within the 255-char filesystem/S3 limit:
#: ``64 + 2 + 154 + 2 + 32 = 254``, ``+ "_" = 255``.
SAFE_MAXLEN = 154

#: Umlaut → ASCII map applied *before* NFKD (German ``ue/oe/ae/ss`` convention).
_UMLAUT = {
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
}


def ascii_fold(s: str) -> str:
    """Umlaut map + NFKD decomposition + ASCII drop (strips combining marks)."""
    for k, v in _UMLAUT.items():
        s = s.replace(k, v)
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


def safe_name(name: str) -> str:
    """Normalise a free-text identifier into a filename-safe token.

    lowercase, umlaut → ASCII, non-``[a-z0-9]`` runs → single ``_``, no
    leading/trailing ``_``, no ``__``, capped to :data:`SAFE_MAXLEN`.

    ``"1.50mm ENAW5754"`` → ``"1_50mm_enaw5754"`` (no leading ``_``, separator-safe).
    """
    s = ascii_fold(str(name)).lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s[:SAFE_MAXLEN].rstrip("_")


def clean_class_name(class_name: str) -> str:
    """Sanitise the class component: non-``[A-Za-z0-9]`` runs → ``_``, edge ``_``
    stripped, capped to :data:`CLASS_MAXLEN`. Case is preserved (e.g. ``MDK_CLN``).
    """
    s = re.sub(r"[^A-Za-z0-9]+", "_", str(class_name)).strip("_")
    return s[:CLASS_MAXLEN].rstrip("_")
