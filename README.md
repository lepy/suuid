# suuid

**Semantic, filename- and S3-safe UUIDs.**

A SUUID is a 3-part identifier you can use directly as an S3 object key, a
filename, or a database column name:

```
<ClassName>__<safe_name>__<huuid>

Data__messung_2026_csv__9e51448c57ab5ef1b92d0c27f554a49e
└─ class    └─ readable name   └─ 32-char hex uuid
```

- **`ClassName`** — the object/type class, case preserved (`[A-Za-z0-9_]`).
- **`safe_name`** — a normalised human label (`[a-z0-9_]`, no leading/trailing `_`).
- **`huuid`** — a 32-char lowercase hex UUID.

The separator is exactly `__` and no component contains `__` or an edge `_`, so a
SUUID parses back into its three parts unambiguously.

## Why

- **Safe as a filename / S3 key.** Only `[A-Za-z0-9_]` after the class, no spaces,
  no special characters — works on Linux, Windows, S3 and as a DB identifier.
- **Length-bounded.** Every `sname` is **≤ 254 characters**, so the *metadata
  sibling* key — `sname + "_"` — still fits the **255-char** limit. Store an
  object under `sname` and its metadata under `meta_name`.
- **Reproducible.** Name- and content-deterministic modes mean the same input
  always yields the same identifier, on every run and machine. The rules are
  frozen and versioned (`NORMALIZATION_SPEC`).

## Install

```bash
uv add suuid
# or
uv pip install suuid
```

## Usage

```python
from suuid import SUUID

# Name-deterministic: same (class, name) -> same id, everywhere.
sid = SUUID.from_name("Data", "Messung 2026.csv")
sid.sname        # 'Data__messung_2026_csv__9e51...'
sid.meta_name    # 'Data__messung_2026_csv__9e51..._'  (metadata object key)
sid.huuid        # '9e51448c57ab5ef1b92d0c27f554a49e'
sid.did          # 'did:suuid:Data__messung_2026_csv__9e51...'

# Content-deterministic: same bytes -> same id (content-addressed, dedup).
SUUID.from_content("Doc", "spec.pdf", b"...bytes...")
SUUID.from_file("Doc", "spec.pdf")

# Random (non-reproducible).
SUUID.random("Run", "nightly")

# Round-trips.
SUUID.from_sname(sid.sname) == sid
SUUID.from_compact_token(sid.compact_token) == sid
SUUID.from_dict(sid.to_dict()) == sid
```

### CLI

```bash
suuid mint --class Data --name "Messung 2026.csv"
suuid mint --class Doc  --name spec.pdf --mode content --content-file spec.pdf
suuid mint --class Run  --name nightly  --mode random
suuid parse --sname "Data__messung_2026_csv__9e51..."
suuid mint  --class Data --name x --json     # full to_dict() as JSON
```

## The three modes

| Mode      | Constructor                          | huuid                                  | Reproducible |
| --------- | ------------------------------------ | -------------------------------------- | ------------ |
| `name`    | `from_name(cls, name)`               | `uuid5(NS, upper(class + safe_name))`  | yes          |
| `content` | `from_content(cls, name, bytes)` / `from_file(cls, path)` | `uuid5(NS, sha3-256(content))` | yes (per content) |
| `random`  | `random(cls, name)`                  | `uuid4()`                              | no           |

In `content` mode the `name` stays human-readable; only the `huuid` is derived
from the content hash (also exposed as `content_hash`, full sha3-256 hex).

## Length budget

```
class (≤64) + "__" (2) + safe_name (≤154) + "__" (2) + huuid (32)  =  ≤ 254
                                                          + "_"     =  ≤ 255   (meta_name)
```

## Development

```bash
uv sync
uv run pytest
uv run ruff check
```

## License

MIT — see [LICENSE](LICENSE).
