from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any


_BRACKET_CONTENT = re.compile(r"[\(（【\[].*?[\)）】\]]")
_SPACE = re.compile(r"\s+")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_header(value: Any) -> str:
    text = unicodedata.normalize("NFKC", clean_text(value))
    text = text.replace("*", "")
    return _SPACE.sub("", text)


def normalize_product(value: Any, *, remove_bracket_content: bool = True) -> str:
    text = unicodedata.normalize("NFKC", clean_text(value))
    if remove_bracket_content:
        text = _BRACKET_CONTENT.sub("", text)
    text = text.replace("、", "/")
    text = text.replace("\\", "/")
    text = _SPACE.sub("", text)
    return text.lower()


def to_decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    text = clean_text(value).replace(",", "")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Cannot parse number: {value!r}") from exc


def decimal_to_excel(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def same_excel_value(a: Any, b: Any) -> bool:
    return clean_text(a) == clean_text(b)
