"""Record and field-value normalization helpers."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime

from .aliases import AliasResolver


RESERVED_SOURCE_KEYS = {"source", "sourcename", "_source"}
RESERVED_TRUST_KEYS = {
    "trust",
    "trustlevel",
    "_trust_level",
    "sourcetrustlevel",
}


def normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value))
    text = re.sub(r"\s+", " ", text).strip().casefold()
    if re.fullmatch(r"(?:\w\s)+\w", text) and all(
        ord(char) > 127 or char.isspace() for char in text
    ):
        return "".join(text.split())
    return text


def normalize_phone(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value))
    digits = "".join(ch for ch in text if ch.isdigit())
    country_code_match = re.match(r"^(?:0086|86)(?P<local>.*)$", digits)
    if country_code_match:
        local_digits = country_code_match.group("local")
        if len(local_digits) > 11 and local_digits.startswith("1"):
            local_digits = re.sub(r"00", "0", local_digits, count=1)
        if len(local_digits) >= 11:
            digits = local_digits[:11]
    if len(digits) != 11 or not digits.startswith("1"):
        raise ValueError(f"invalid Chinese mobile phone number: {value!r}")
    return digits


def normalize_email(value: object) -> str:
    email = unicodedata.normalize("NFKC", str(value)).strip().casefold()
    email = "".join(email.split())
    if email.count("@") != 1 or email.startswith("@") or email.endswith("@"):
        raise ValueError(f"invalid email address: {value!r}")
    return email


def normalize_date(value: object) -> str:
    raw = unicodedata.normalize("NFKC", str(value)).strip()
    if not raw:
        raise ValueError("empty date value")

    if "T" in raw or re.search(r"\d{1,2}:\d{2}", raw):
        iso_value = raw[:-1] + "+00:00" if raw.endswith(("Z", "z")) else raw
        return datetime.fromisoformat(iso_value).date().isoformat()

    chinese_date = re.fullmatch(
        r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?", raw
    )
    if chinese_date:
        year, month, day = (int(part) for part in chinese_date.groups())
        return datetime(year, month, day).date().isoformat()

    plain_date = raw.replace("/", "-")
    parts = [part.strip() for part in plain_date.split("-")]
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        year, month, day = (int(part) for part in parts)
        return datetime(year, month, day).date().isoformat()

    return datetime.fromisoformat(raw).date().isoformat()


def normalize_value(field_name: str, value: object) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).strip()
    if not text:
        return ""
    if field_name == "phone":
        return normalize_phone(text)
    if field_name == "email":
        return normalize_email(text)
    if field_name == "created_at":
        return normalize_date(text)
    return normalize_text(text)


def _metadata_key(key: str) -> str:
    normalized = unicodedata.normalize("NFKC", key).casefold().strip()
    return "".join(ch for ch in normalized if not ch.isspace() and ch != "_")


def normalize_record(
    record: dict[str, object],
    *,
    default_source: str = "",
    default_trust_level: int | None = None,
    alias_resolver: AliasResolver | None = None,
) -> dict[str, object]:
    resolver = alias_resolver or AliasResolver()
    source = default_source
    trust_level = default_trust_level
    fields: dict[str, str] = {}

    for raw_key, raw_value in record.items():
        key = _metadata_key(raw_key)
        if key in RESERVED_SOURCE_KEYS:
            if raw_value not in (None, ""):
                source = str(raw_value)
            continue
        if key in RESERVED_TRUST_KEYS:
            if raw_value not in (None, ""):
                trust_level = int(raw_value)
            continue

        canonical = resolver.canonical_name(raw_key)
        if canonical is None or raw_value in (None, ""):
            continue
        normalized = normalize_value(canonical, raw_value)
        if normalized:
            fields[canonical] = normalized

    if not source:
        raise ValueError("record is missing a source name")
    if trust_level is None:
        raise ValueError(f"record from {source!r} is missing a trust level")
    if trust_level not in (1, 2, 3):
        raise ValueError("trust level must be one of 1, 2, or 3")

    return {
        "source": source,
        "trust_level": trust_level,
        "fields": fields,
    }
