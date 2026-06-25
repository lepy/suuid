"""Semantic UUID (SUUID) — minting, parsing and the :class:`SUUID` value type.

A SUUID is a **3-part, filename-safe identifier**::

    <ClassName>__<safe_name>__<huuid>
    e.g.  Data__messung_csv__9e51448c57ab5ef1b92d0c27f554a49e

* ``ClassName`` — the ontology/object class, case preserved (``[A-Za-z0-9_]``).
* ``safe_name`` — a normalised human label (``[a-z0-9_]``).
* ``huuid``     — a 32-char lowercase hex UUID.

The separator is exactly ``"__"`` and no component contains ``"__"`` or edge
``_``, so :meth:`SUUID.from_sname` is an unambiguous 3-way split.

**Three minting modes:**

* ``name``    — :meth:`SUUID.from_name`: ``uuid5(NS, upper(class + safe_name))``.
  Same ``(class, name)`` ⇒ same huuid on every run/machine.
* ``content`` — :meth:`SUUID.from_content` / :meth:`SUUID.from_file`:
  ``uuid5(NS, sha3-256(content))``. Same bytes ⇒ same huuid (content-addressed).
* ``random``  — :meth:`SUUID.random`: ``uuid4()``. Not reproducible.

**Filename/S3 safety.** Every ``sname`` is ``<= 254`` chars by construction, so
the metadata sibling key — ``sname + "_"`` (see :attr:`SUUID.meta_name`) — stays
``<= 255``, the safe limit for S3 keys and common filesystems.
"""

from __future__ import annotations

import base64
import hashlib
import os
import uuid
from dataclasses import dataclass, field

from suuid._normalize import (
    CLASS_MAXLEN,
    NORMALIZATION_SPEC,
    SAFE_MAXLEN,
    SEP,
    clean_class_name,
    safe_name,
)

#: Default uuid5 namespace — ``uuid.NAMESPACE_OID``. Pinned alongside the
#: normalisation spec; it is part of the reproducibility contract.
OID_NAMESPACE = uuid.NAMESPACE_OID

#: sha3-256 over the content bytes (the lepus content-mode hash).
CONTENT_ALGO = "SHA3-256"

#: Max length of a full ``sname``. Budgeted so ``sname`` *and* its metadata
#: sibling (``sname + "_"``) both stay ``<= 255``: ``64 + 2 + 154 + 2 + 32 = 254``.
MAX_SNAME_LEN = CLASS_MAXLEN + len(SEP) + SAFE_MAXLEN + len(SEP) + 32  # 254

_HEX = frozenset("0123456789abcdef")


def _validate_huuid(huuid: str) -> str:
    h = str(huuid).lower()
    if len(h) != 32 or not set(h) <= _HEX:
        raise ValueError(f"huuid must be a 32-char lowercase hex string, got {huuid!r}")
    return h


# --- low-level huuid generation ----------------------------------------------

def name_deterministic_huuid(class_name: str, name: str,
                             ns: uuid.UUID = OID_NAMESPACE) -> str:
    """``uuid5(ns, upper(clean_class + safe_name)).hex`` — reproducible."""
    key = (clean_class_name(class_name) + safe_name(name)).upper()
    return uuid.uuid5(ns, key).hex


def content_huuid(content: bytes,
                  ns: uuid.UUID = OID_NAMESPACE) -> tuple[str, str]:
    """``(huuid, content_hash)``: ``huuid = uuid5(ns, sha3-256(content)).hex``;
    ``content_hash`` is the full sha3-256 hex digest (64 chars)."""
    digest = hashlib.sha3_256(content).hexdigest()
    return uuid.uuid5(ns, digest).hex, digest


def namespace_from_name(name: str, base: uuid.UUID = OID_NAMESPACE) -> uuid.UUID:
    """Derive a stable namespace UUID from a string (e.g. a parent/project sname).

    ``uuid5(base, name.upper())`` — the same string yields the same namespace on
    every run and machine. This lets callers *scope* name-deterministic ids to a
    parent (pass the parent's ``sname`` as the namespace) without managing
    :class:`uuid.UUID` objects by hand. Part of the reproducibility contract.
    """
    return uuid.uuid5(base, str(name).upper())


def _resolve_ns(ns: str | uuid.UUID) -> uuid.UUID:
    """Accept a namespace as a :class:`uuid.UUID` or a string.

    A string is resolved to a namespace UUID via :func:`namespace_from_name`.
    """
    return ns if isinstance(ns, uuid.UUID) else namespace_from_name(ns)


@dataclass(frozen=True, slots=True)
class SUUID:
    """An immutable semantic UUID.

    Prefer the classmethod constructors (:meth:`from_name`, :meth:`from_content`,
    :meth:`from_file`, :meth:`random`, :meth:`from_sname`) over ``__init__``; the
    constructor takes already-clean components and only validates them.
    """

    # Identity = the sname (class_name + name + huuid). The remaining fields
    # record *how* this id was minted; they are metadata, not identity, so they
    # are excluded from equality/hashing — a parsed SUUID equals a freshly
    # minted one with the same sname.
    class_name: str
    name: str
    huuid: str
    mode: str = field(default="name", compare=False)          # "name" | "content" | "random"
    namespace: str | None = field(default=None, compare=False)
    content_hash: str | None = field(default=None, compare=False)  # full sha3-256 hex
    hash_algorithm: str | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if not self.class_name:
            raise ValueError("class_name must be a non-empty string")
        object.__setattr__(self, "huuid", _validate_huuid(self.huuid))
        if len(self.sname) > MAX_SNAME_LEN:  # defensive: clean components can't exceed this
            raise ValueError(
                f"sname exceeds {MAX_SNAME_LEN} chars (filename/S3 limit): {self.sname!r}"
            )

    # --- constructors --------------------------------------------------------

    @classmethod
    def from_name(cls, class_name: str, name: str = "",
                  ns: str | uuid.UUID = OID_NAMESPACE) -> SUUID:
        """Name-deterministic SUUID: same ``(class_name, name)`` ⇒ same id.

        ``ns`` may be a :class:`uuid.UUID` *or* a string. A string is resolved to
        a namespace via :func:`namespace_from_name`, so passing a parent's
        ``sname`` scopes the id to that parent (hierarchical, still reproducible).
        """
        ns_uuid = _resolve_ns(ns)
        cn = clean_class_name(class_name)
        sn = safe_name(name)
        return cls(
            class_name=cn, name=sn,
            huuid=name_deterministic_huuid(cn, name, ns_uuid),
            mode="name", namespace=str(ns_uuid),
        )

    @classmethod
    def from_content(cls, class_name: str, name: str, content: bytes,
                     ns: str | uuid.UUID = OID_NAMESPACE) -> SUUID:
        """Content-deterministic SUUID: same ``content`` bytes ⇒ same id.

        ``name`` stays a human-readable ``safe_name``; only ``huuid`` is derived
        from the content hash. ``ns`` accepts a :class:`uuid.UUID` or a string
        (see :meth:`from_name`).
        """
        if not isinstance(content, (bytes, bytearray)):
            raise TypeError("content must be bytes")
        ns_uuid = _resolve_ns(ns)
        huuid, digest = content_huuid(bytes(content), ns_uuid)
        return cls(
            class_name=clean_class_name(class_name), name=safe_name(name),
            huuid=huuid, mode="content", namespace=str(ns_uuid),
            content_hash=digest, hash_algorithm=CONTENT_ALGO,
        )

    @classmethod
    def from_file(cls, class_name: str, filepath: str | os.PathLike[str],
                  ns: str | uuid.UUID = OID_NAMESPACE) -> SUUID:
        """Content-deterministic SUUID from a file's bytes; ``name`` = basename."""
        with open(filepath, "rb") as fh:
            content = fh.read()
        basename = os.path.basename(os.fspath(filepath))
        sid = cls.from_content(class_name, basename, content, ns)
        return sid

    @classmethod
    def random(cls, class_name: str, name: str = "") -> SUUID:
        """Random (non-reproducible) SUUID via ``uuid4``."""
        return cls(
            class_name=clean_class_name(class_name), name=safe_name(name),
            huuid=uuid.uuid4().hex, mode="random",
        )

    @classmethod
    def from_sname(cls, sname: str, strict: bool = True) -> SUUID | None:
        """Parse a 3-part ``sname`` (``class__safe__huuid``) back into a SUUID.

        Accepts the metadata sibling form too (a single trailing ``"_"``), so
        ``from_sname(sid.meta_name).sname == sid.sname``.

        With ``strict=False`` an unparseable or invalid ``sname`` (wrong arity,
        bad huuid, non-string, ``None``) yields ``None`` instead of raising —
        useful for "is this a SUUID?" probes and best-effort coercion.
        """
        try:
            s = sname[:-1] if sname.endswith(SEP[0]) and not sname.endswith(SEP) else sname
            parts = s.split(SEP)
            if len(parts) != 3:
                raise ValueError(
                    f"sname must have exactly 3 '{SEP}'-separated parts, got {sname!r}"
                )
            class_name, name, huuid = parts
            return cls(class_name=class_name, name=name, huuid=huuid)
        except (ValueError, TypeError, AttributeError):
            if strict:
                raise
            return None

    @classmethod
    def from_compact_token(cls, token: str) -> SUUID:
        """Decode a base64 :attr:`compact_token` back into a SUUID."""
        raw = base64.b64decode(token.encode()).decode()
        huuid, rest = raw[:32], raw[32:]
        parts = rest.split(SEP)
        if len(parts) != 2:
            raise ValueError(f"compact-token remainder must have 2 parts: {rest!r}")
        return cls(class_name=parts[0], name=parts[1], huuid=huuid)

    @classmethod
    def from_dict(cls, d: dict) -> SUUID:
        """Reconstruct a SUUID from a :meth:`to_dict` mapping (via ``sname``)."""
        return cls.from_sname(d["sname"])

    # --- serialisations ------------------------------------------------------

    @property
    def sname(self) -> str:
        """The canonical 3-part string ``class_name__name__huuid``."""
        return SEP.join([self.class_name, self.name, self.huuid])

    @property
    def meta_name(self) -> str:
        """Sibling key for this object's metadata: ``sname + "_"`` (``<= 255``)."""
        return self.sname + "_"

    @property
    def did(self) -> str:
        """DID-Core method id ``did:suuid:<sname>``."""
        return f"did:suuid:{self.sname}"

    @property
    def compact_token(self) -> str:
        """Base64 of ``huuid + class_name + SEP + name`` — a compact opaque token."""
        raw = self.huuid + self.class_name + SEP + self.name
        return base64.b64encode(raw.encode()).decode()

    def as_uuid(self) -> uuid.UUID:
        """The :class:`uuid.UUID` object behind :attr:`huuid`."""
        return uuid.UUID(hex=self.huuid)

    @property
    def hex(self) -> str:
        """The 32-char hex huuid (alias of :attr:`huuid`)."""
        return self.huuid

    def to_dict(self) -> dict:
        """A JSON-friendly dict — round-trips via :meth:`from_dict`."""
        d = {
            "class_name": self.class_name,
            "name": self.name,
            "huuid": self.huuid,
            "sname": self.sname,
            "did": self.did,
            "mode": self.mode,
            "compact_token": self.compact_token,
            "spec": NORMALIZATION_SPEC,
        }
        if self.namespace:
            d["namespace"] = self.namespace
        if self.content_hash:
            d["content_hash"] = self.content_hash
            d["hash_algorithm"] = self.hash_algorithm
        return d

    def __str__(self) -> str:
        return self.sname

    def __repr__(self) -> str:
        return f"<SUUID:{self.sname}>"
