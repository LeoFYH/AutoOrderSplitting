from __future__ import annotations

import json
import os
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .models import TemplateItem
from .normalization import clean_text, to_decimal


DATA_DIR = Path(os.environ.get("AUTO_ORDER_SPLITTING_DATA", ".web_data"))
CURRENT_TEMPLATE = DATA_DIR / "current_template.xlsx"
TEMPLATE_JSON = DATA_DIR / "current_template.json"
RUNS_DIR = DATA_DIR / "runs"


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)


def save_template_items(items: list[TemplateItem], *, source_name: str = "") -> None:
    ensure_data_dirs()
    payload = {
        "source_name": source_name,
        "items": [template_item_to_dict(item) for item in items],
    }
    TEMPLATE_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_template_payload() -> dict[str, Any] | None:
    if not TEMPLATE_JSON.exists():
        return None
    return json.loads(TEMPLATE_JSON.read_text(encoding="utf-8"))


def load_template_items() -> list[TemplateItem]:
    payload = load_template_payload()
    if not payload:
        return []
    return [template_item_from_dict(item) for item in payload.get("items", [])]


def template_item_to_dict(item: TemplateItem) -> dict[str, Any]:
    data = asdict(item)
    data["quantity"] = decimal_to_string(item.quantity)
    return data


def template_item_from_dict(data: dict[str, Any]) -> TemplateItem:
    return TemplateItem(
        row_number=int(data.get("row_number") or 0),
        owner=clean_text(data.get("owner")),
        supplier=clean_text(data.get("supplier")),
        product=clean_text(data.get("product")),
        unit=clean_text(data.get("unit")),
        quantity=to_decimal(data.get("quantity")),
        price=parse_optional_number(data.get("price")),
        note=clean_text(data.get("note")),
        agreement_price=parse_optional_number(data.get("agreement_price")),
    )


def normalize_template_items(raw_items: list[dict[str, Any]]) -> list[TemplateItem]:
    items: list[TemplateItem] = []
    next_row = 5
    for raw in raw_items:
        product = clean_text(raw.get("product"))
        supplier = clean_text(raw.get("supplier"))
        if not product and not supplier:
            continue
        row_number = int(raw.get("row_number") or next_row)
        next_row = max(next_row, row_number + 1)
        items.append(
            TemplateItem(
                row_number=row_number,
                owner=clean_text(raw.get("owner")),
                supplier=supplier,
                product=product,
                unit=clean_text(raw.get("unit")),
                quantity=to_decimal(raw.get("quantity")),
                price=parse_optional_number(raw.get("price")),
                note=clean_text(raw.get("note")),
                agreement_price=parse_optional_number(raw.get("agreement_price")),
            )
        )
    return items


def parse_optional_number(value: Any) -> Any:
    text = clean_text(value)
    if text == "":
        return None
    try:
        decimal = Decimal(text.replace(",", ""))
    except (InvalidOperation, ValueError):
        return text
    if decimal == decimal.to_integral_value():
        return int(decimal)
    return float(decimal)


def decimal_to_string(value: Decimal) -> str:
    return format(value, "f").rstrip("0").rstrip(".") if "." in format(value, "f") else format(value, "f")
