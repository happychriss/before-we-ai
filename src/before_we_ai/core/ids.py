"""ULID helpers — all objects are identified and cross-referenced by ULID."""

from ulid import ULID


def new_id() -> str:
    return str(ULID())


def is_valid_id(value: str) -> bool:
    try:
        ULID.from_str(value)
        return True
    except (ValueError, TypeError):
        return False
