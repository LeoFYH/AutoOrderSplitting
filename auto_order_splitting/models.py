from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TemplateItem:
    row_number: int
    owner: str
    supplier: str
    product: str
    unit: str
    quantity: Decimal
    price: Any
    note: str
    agreement_price: Any = None


@dataclass(frozen=True)
class OrderLine:
    row_number: int
    order_no: str
    customer: str
    ship_date: Any
    product: str
    quantity: Decimal
    amount: Any
    subtotal: Any
    unit: str
    order_price: Any
    note: str
    source_file: Path
    supplier: str = ""
    product_note: str = ""
    order_note: str = ""


@dataclass(frozen=True)
class SourceLine:
    source_type: str
    source_file: Path | None
    source_row: int
    owner: str
    supplier: str
    product: str
    unit: str
    quantity: Decimal
    price: Any
    note: str
    agreement_price: Any
    match_method: str = ""
    order_no: str = ""
    original_product: str = ""
    product_note: str = ""
    order_note: str = ""


@dataclass
class PurchaseLine:
    owner: str
    supplier: str
    product: str
    unit: str
    quantity: Decimal
    price: Any
    note: str
    agreement_price: Any = None
    source_rows: list[str] = field(default_factory=list)
    match_methods: set[str] = field(default_factory=set)
    product_note: str = ""
    order_note: str = ""


@dataclass(frozen=True)
class UnmatchedLine:
    source_file: Path
    row_number: int
    order_no: str
    customer: str
    product: str
    quantity: Decimal
    unit: str
    note: str
    reason: str
    product_note: str = ""
    order_note: str = ""


@dataclass(frozen=True)
class SkippedLine:
    source_file: Path
    row_number: int
    order_no: str
    customer: str
    product: str
    quantity: Decimal
    unit: str
    note: str
    reason: str
    product_note: str = ""
    order_note: str = ""


@dataclass
class SplitResult:
    lines: list[PurchaseLine]
    unmatched: list[UnmatchedLine]
    skipped: list[SkippedLine]
    warnings: list[str]
    order_rows_read: int = 0
    template_rows_read: int = 0
