from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from pathlib import Path
import re
from typing import Iterable

from .models import (
    OrderLine,
    PurchaseLine,
    SkippedLine,
    SourceLine,
    SplitResult,
    TemplateItem,
    UnmatchedLine,
)
from .normalization import clean_text, normalize_product, same_excel_value


DEFAULT_SKIP_KEYWORDS = ("营养餐",)
SKIP_SEPARATOR_RE = re.compile(r"[,，、;\n\r\t]+")


@dataclass(frozen=True)
class Match:
    item: TemplateItem | None
    method: str
    score: float
    reason: str = ""


class TemplateCatalog:
    def __init__(self, items: Iterable[TemplateItem], *, fuzzy_threshold: float = 0.88):
        self.items = list(items)
        self.fuzzy_threshold = fuzzy_threshold
        self.owners = {item.owner for item in self.items if item.owner}
        self.exact: dict[str, list[TemplateItem]] = defaultdict(list)
        self.normalized: dict[str, list[TemplateItem]] = defaultdict(list)
        self.normalized_keep_brackets: dict[str, list[TemplateItem]] = defaultdict(list)

        for item in self.items:
            self.exact[item.product].append(item)
            self.normalized[normalize_product(item.product)].append(item)
            self.normalized_keep_brackets[
                normalize_product(item.product, remove_bracket_content=False)
            ].append(item)

    def match(self, product: str, unit: str = "", owner: str = "") -> Match:
        product = clean_text(product)
        unit = clean_text(unit)
        owner = clean_text(owner)
        if not product:
            return Match(None, "empty", 0, "商品名称为空")

        exact = self._select_unique(self._filter_candidates(self.exact.get(product, []), unit, owner), unit)
        if exact.item:
            return Match(exact.item, "exact_owner" if exact.item.owner == owner and owner else "exact", 1)
        if exact.reason:
            return exact

        keep_key = normalize_product(product, remove_bracket_content=False)
        keep_match = self._select_unique(
            self._filter_candidates(self.normalized_keep_brackets.get(keep_key, []), unit, owner),
            unit,
        )
        if keep_match.item:
            return Match(keep_match.item, "normalized_owner" if keep_match.item.owner == owner and owner else "normalized", 1)
        if keep_match.reason:
            return keep_match

        key = normalize_product(product)
        normalized_match = self._select_unique(self._filter_candidates(self.normalized.get(key, []), unit, owner), unit)
        if normalized_match.item:
            return Match(
                normalized_match.item,
                "normalized_drop_brackets_owner" if normalized_match.item.owner == owner and owner else "normalized_drop_brackets",
                1,
            )
        if normalized_match.reason:
            return normalized_match

        return self._fuzzy_match(product, unit, owner)

    def _filter_candidates(self, candidates: list[TemplateItem], unit: str, owner: str) -> list[TemplateItem]:
        if not candidates or not unit:
            return self._filter_by_owner(candidates, owner)
        candidates = self._filter_by_owner(candidates, owner)
        if not candidates:
            return []
        same_unit = [candidate for candidate in candidates if candidate.unit == unit]
        if same_unit:
            return same_unit
        units = "、".join(sorted({candidate.unit or "空" for candidate in candidates}))
        return [
            TemplateItem(
                row_number=0,
                owner="",
                supplier="",
                product="",
                unit="",
                quantity=candidates[0].quantity,
                price=None,
                note=f"模板商品单位与订单单位不一致：订单单位 {unit}，模板单位 {units}",
            )
        ]

    def _filter_by_owner(self, candidates: list[TemplateItem], owner: str) -> list[TemplateItem]:
        if not candidates or not owner:
            return candidates
        same_owner = [candidate for candidate in candidates if candidate.owner == owner]
        return same_owner

    def _select_unique(self, candidates: list[TemplateItem], unit: str = "") -> Match:
        if not candidates:
            return Match(None, "", 0)
        if candidates[0].row_number == 0 and candidates[0].note.startswith("模板商品单位与订单单位不一致"):
            return Match(None, "unit_mismatch", 0, candidates[0].note)
        signatures = {
            (candidate.supplier, candidate.unit, clean_text(candidate.price))
            for candidate in candidates
        }
        if len(signatures) == 1:
            return Match(candidates[0], "", 1)
        detail = "；".join(
            f"{candidate.row_number}:{candidate.supplier}/{candidate.unit}/{candidate.price}"
            for candidate in candidates[:8]
        )
        return Match(None, "ambiguous", 0, f"模板中同名商品供应商或单价不唯一：{detail}")

    def _fuzzy_match(self, product: str, unit: str = "", owner: str = "") -> Match:
        product_key = normalize_product(product)
        scored: list[tuple[float, TemplateItem]] = []
        if owner:
            candidate_pool = [item for item in self.items if item.owner == owner]
            if not candidate_pool:
                return Match(None, "owner_unmatched", 0, f"模板中找不到学校：{owner}")
        else:
            candidate_pool = self.items

        for item in candidate_pool:
            item_key = normalize_product(item.product)
            if not item_key:
                continue
            score = SequenceMatcher(None, product_key, item_key).ratio()
            if score >= self.fuzzy_threshold:
                scored.append((score, item))

        if not scored:
            return Match(None, "unmatched", 0, f"模板中该学校找不到商品：{product}" if owner else "模板中找不到商品")

        scored.sort(key=lambda pair: pair[0], reverse=True)
        if unit:
            same_unit_scored = [(score, item) for score, item in scored if item.unit == unit]
            if not same_unit_scored:
                top_units = "、".join(sorted({item.unit or "空" for _, item in scored[:5]}))
                return Match(
                    None,
                    "unit_mismatch",
                    scored[0][0],
                    f"模糊匹配到相近商品，但模板单位与订单单位不一致：订单单位 {unit}，候选模板单位 {top_units}",
                )
            scored = same_unit_scored
        best_score = scored[0][0]
        best_items = [item for score, item in scored if score == best_score]
        selected = self._select_unique(best_items, unit)
        if not selected.item:
            return Match(None, "ambiguous_fuzzy", best_score, selected.reason or "模糊匹配结果不唯一")

        second_score = scored[1][0] if len(scored) > 1 else 0
        if best_score - second_score < 0.03 and scored[1][1].product != selected.item.product:
            return Match(
                None,
                "ambiguous_fuzzy",
                best_score,
                f"模糊匹配过近：{selected.item.product}({best_score:.2f}) / {scored[1][1].product}({second_score:.2f})",
            )
        return Match(selected.item, "fuzzy", best_score)


def split_orders(
    template_items: list[TemplateItem],
    order_lines: list[OrderLine],
    *,
    include_template_rows: bool = True,
    skip_keywords: Iterable[str] = DEFAULT_SKIP_KEYWORDS,
    fuzzy_threshold: float = 0.88,
) -> SplitResult:
    skip_keywords = _normalize_skip_keywords(skip_keywords)
    skipped_template_owners = {
        item.owner for item in template_items if _owner_skip_reason(item.owner, skip_keywords)
    }
    active_template_items = [item for item in template_items if item.owner not in skipped_template_owners]
    catalog = TemplateCatalog(active_template_items, fuzzy_threshold=fuzzy_threshold)
    source_lines: list[SourceLine] = []
    unmatched: list[UnmatchedLine] = []
    skipped: list[SkippedLine] = []
    warnings: list[str] = []

    if include_template_rows:
        for item in active_template_items:
            if item.quantity == 0:
                continue
            source_lines.append(
                SourceLine(
                    source_type="template",
                    source_file=None,
                    source_row=item.row_number,
                    owner=item.owner,
                    supplier=item.supplier,
                    product=item.product,
                    unit=item.unit,
                    quantity=item.quantity,
                    price=item.price,
                    note=item.note,
                    agreement_price=item.agreement_price,
                    match_method="template",
                    original_product=item.product,
                    product_note=item.note,
                    order_note="",
                )
            )

    for order in order_lines:
        skip_reason = _skip_reason(order, skip_keywords)
        if skip_reason:
            skipped.append(
                SkippedLine(
                    source_file=order.source_file,
                    row_number=order.row_number,
                    order_no=order.order_no,
                    customer=order.customer,
                    product=order.product,
                    quantity=order.quantity,
                    unit=order.unit,
                    note=order.note,
                    reason=skip_reason,
                    product_note=order.product_note,
                    order_note=order.order_note,
                )
            )
            continue

        match = catalog.match(order.product, order.unit, order.customer)
        if not match.item:
            order_supplier = clean_text(order.supplier)
            if order_supplier:
                source_lines.append(
                    SourceLine(
                        source_type="order",
                        source_file=order.source_file,
                        source_row=order.row_number,
                        owner=order.customer,
                        supplier=order_supplier,
                        product=order.product,
                        unit=order.unit,
                        quantity=order.quantity,
                        price=order.order_price,
                        note=order.note,
                        agreement_price=None,
                        match_method="order_supplier",
                        order_no=order.order_no,
                        original_product=order.product,
                        product_note=order.product_note,
                        order_note=order.order_note,
                    )
                )
                continue
            unmatched.append(
                UnmatchedLine(
                    source_file=order.source_file,
                    row_number=order.row_number,
                    order_no=order.order_no,
                    customer=order.customer,
                    product=order.product,
                    quantity=order.quantity,
                    unit=order.unit,
                    note=order.note,
                    reason=match.reason,
                    product_note=order.product_note,
                    order_note=order.order_note,
                )
            )
            continue

        item = match.item
        if match.method == "fuzzy":
            warnings.append(
                f"{order.source_file.name} 第{order.row_number}行："
                f"商品「{order.product}」按模糊匹配到模板「{item.product}」，得分 {match.score:.2f}"
            )
        if order.order_price is not None and not _same_price(order.order_price, item.price):
            warnings.append(
                f"{order.source_file.name} 第{order.row_number}行："
                f"商品「{order.product}」订单单价 {order.order_price}，模板单价 {item.price}，已按模板单价输出"
            )
        source_lines.append(
            SourceLine(
                source_type="order",
                source_file=order.source_file,
                source_row=order.row_number,
                owner=order.customer,
                supplier=item.supplier,
                product=item.product,
                unit=order.unit or item.unit,
                quantity=order.quantity,
                price=item.price,
                note=order.note or item.note,
                agreement_price=item.agreement_price,
                match_method=match.method,
                order_no=order.order_no,
                original_product=order.product,
                product_note=order.product_note,
                order_note=order.order_note,
            )
        )

    lines = _aggregate(source_lines, warnings)
    lines.sort(key=lambda line: (line.supplier, line.owner, line.product))
    return SplitResult(
        lines=lines,
        unmatched=unmatched,
        skipped=skipped,
        warnings=warnings,
        order_rows_read=len(order_lines),
        template_rows_read=len(template_items),
    )


def _skip_reason(order: OrderLine, skip_keywords: tuple[str, ...]) -> str:
    if not skip_keywords:
        return ""
    customer = clean_text(order.customer)
    for keyword in skip_keywords:
        if keyword in customer:
            return f"学校字段命中跳过关键词：{keyword}"
    return ""


def _normalize_skip_keywords(skip_keywords: Iterable[str]) -> tuple[str, ...]:
    markers: list[str] = []
    seen: set[str] = set()
    for raw_keyword in skip_keywords:
        for keyword in SKIP_SEPARATOR_RE.split(clean_text(raw_keyword)):
            if keyword and keyword not in seen:
                markers.append(keyword)
                seen.add(keyword)
    return tuple(markers)


def _owner_skip_reason(owner: str, skip_keywords: tuple[str, ...]) -> str:
    owner = clean_text(owner)
    for keyword in skip_keywords:
        if keyword in owner:
            return f"模板负责人命中跳过关键词：{keyword}"
    return ""


def _aggregate(source_lines: list[SourceLine], warnings: list[str]) -> list[PurchaseLine]:
    grouped: dict[tuple[str, str, str], PurchaseLine] = {}

    for line in source_lines:
        key = (line.supplier, line.owner, line.product)
        source_label = _source_label(line)
        if key not in grouped:
            grouped[key] = PurchaseLine(
                owner=line.owner,
                supplier=line.supplier,
                product=line.product,
                unit=line.unit,
                quantity=line.quantity,
                price=line.price,
                note=line.note,
                agreement_price=line.agreement_price,
                source_rows=[source_label],
                match_methods={line.match_method} if line.match_method else set(),
                product_note=line.product_note,
                order_note=line.order_note,
            )
            continue

        target = grouped[key]
        if target.unit and line.unit and target.unit != line.unit:
            warnings.append(
                f"{line.supplier}/{line.owner}/{line.product} 单位不一致："
                f"保留 {target.unit}，新增来源为 {line.unit}（{source_label}）"
            )
        elif not target.unit:
            target.unit = line.unit

        if not same_excel_value(target.price, line.price):
            warnings.append(
                f"{line.supplier}/{line.owner}/{line.product} 单价不一致："
                f"保留 {target.price}，新增来源为 {line.price}（{source_label}）"
            )

        if line.note and target.note and target.note != line.note:
            warnings.append(
                f"{line.supplier}/{line.owner}/{line.product} 时间/备注不一致："
                f"已合并「{line.note}」，原为「{target.note}」（{source_label}）"
            )
            target.note = _merge_note_values(target.note, line.note)
        elif line.note:
            target.note = line.note
        target.product_note = _merge_note_values(target.product_note, line.product_note)
        target.order_note = _merge_note_values(target.order_note, line.order_note)

        target.quantity += line.quantity
        target.source_rows.append(source_label)
        if line.match_method:
            target.match_methods.add(line.match_method)

    return [line for line in grouped.values() if line.quantity != 0]


def _source_label(line: SourceLine) -> str:
    if line.source_type == "template":
        return f"template:{line.source_row}"
    file_name = line.source_file.name if isinstance(line.source_file, Path) else ""
    return f"{file_name}:{line.source_row}"


def _same_price(left, right) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    try:
        return Decimal(str(left).replace(",", "")) == Decimal(str(right).replace(",", ""))
    except (InvalidOperation, ValueError):
        return clean_text(left) == clean_text(right)


def _merge_note_values(current: str, new_value: str) -> str:
    current = clean_text(current)
    new_value = clean_text(new_value)
    if not new_value:
        return current
    if not current:
        return new_value
    parts = [part.strip() for part in current.split("；") if part.strip()]
    for part in [part.strip() for part in new_value.split("；") if part.strip()]:
        if part not in parts:
            parts.append(part)
    return "；".join(parts)
