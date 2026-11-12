"""Canonical field-name and extensible alias handling."""

from __future__ import annotations

import unicodedata


DEFAULT_ALIASES = {
    "name": {
        "name",
        "username",
        "user_name",
        "fullname",
        "full_name",
        "姓名",
    },
    "phone": {
        "phone",
        "mobile",
        "telephone",
        "phone_number",
        "mobile_phone",
        "手机号",
        "手机号码",
        "电话",
    },
    "email": {
        "email",
        "mail",
        "email_address",
        "e_mail",
        "邮箱",
    },
    "created_at": {
        "createdat",
        "created_at",
        "create_time",
        "creation_time",
        "创建时间",
    },
    "city": {
        "city",
        "city_name",
        "城市",
    },
    "order_id": {
        "orderid",
        "order_id",
        "order_no",
        "order_number",
        "订单号",
    },
}


def _key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value)).casefold().strip()
    return "".join(ch for ch in normalized if not ch.isspace() and ch != "_")


class AliasResolver:
    """Map source field names to stable canonical field names."""

    def __init__(self, aliases: dict[str, set[str]] | None = None) -> None:
        self._aliases: dict[str, set[str]] = {
            canonical: {_key(alias) for alias in values}
            for canonical, values in (aliases or DEFAULT_ALIASES).items()
        }
        for canonical in self._aliases:
            self._aliases[canonical].add(_key(canonical))

    def add_alias(self, canonical_field: str, alias: str) -> None:
        canonical = _key(canonical_field)
        self._aliases.setdefault(canonical, set()).update(
            {_key(canonical_field), _key(alias)}
        )

    def canonical_name(self, field_name: str) -> str | None:
        key = _key(field_name)
        for canonical, aliases in self._aliases.items():
            if key in aliases:
                return canonical
        return None
