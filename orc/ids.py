"""Content-addressed identifiers.

Every model in the registry is identified by an 8-character hex digest of its
own canonical YAML representation. The id is derived from content, not stored
position, so it is:

- *stable* across reordering / reformatting of the source file (we hash a
  canonical dump, not raw bytes), and
- *content-addressed*: edit any parameter and the id changes, which is what
  makes a model family able to pin to exact model versions.

Hashing the model's *own* serialized content (rather than the whole file) means
a change to an unrelated model in the same file does not re-id this model, and
identical models across publications collapse to the same id — a dedupe signal
the assembly layer can use.
"""

from __future__ import annotations

import hashlib
from typing import Any

import yaml

ID_LENGTH = 8
ID_HEX = "0123456789abcdef"


def canonical_dump(obj: Any) -> str:
    """Deterministic YAML serialization of a parsed object.

    Key order, flow style, and scalar quoting are normalized so that cosmetic
    edits to a source file do not change derived ids.
    """
    return yaml.safe_dump(
        obj,
        sort_keys=True,
        default_flow_style=False,
        width=1 << 20,
        allow_unicode=True,
    )


def content_hash(obj: Any) -> str:
    """First ``ID_LENGTH`` hex chars of SHA-256 over ``canonical_dump(obj)``."""
    digest = hashlib.sha256(canonical_dump(obj).encode("utf-8")).hexdigest()
    return digest[:ID_LENGTH]


def is_valid_id(value: str) -> bool:
    """True if ``value`` looks like an orc id (``[0-9a-f]{8}``)."""
    return len(value) == ID_LENGTH and all(c in ID_HEX for c in value)