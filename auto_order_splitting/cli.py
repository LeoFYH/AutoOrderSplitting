from __future__ import annotations

import argparse
from pathlib import Path

from .excel_io import read_orders, read_template, write_purchase_import
from .splitter import DEFAULT_SKIP_KEYWORDS, split_orders


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="auto-order-splitting",
        description="按采购模板把苏东坡订单导出拆成采购单。",
    )
    parser.add_argument("--template", required=True, help="采购模板 xlsx 路径")
    parser.add_argument(
        "--orders",
        nargs="*",
        default=[],
        help="订单导出 xlsx 路径，可一次传多个",
    )
    parser.add_argument(
        "--output",
        default="outputs/采购单.xlsx",
        help="采购单输出路径，默认 outputs/采购单.xlsx",
    )
    parser.add_argument(
        "--orders-only",
        action="store_true",
        help="只按订单生成，不带入模板已有数量行",
    )
    parser.add_argument(
        "--skip-keyword",
        action="append",
        default=[],
        help="额外跳过学校关键词，可重复传入；只检查订单学校字段",
    )
    parser.add_argument(
        "--no-default-skip",
        action="store_true",
        help="不使用默认跳过学校关键词（默认：营养餐）",
    )
    parser.add_argument(
        "--fuzzy-threshold",
        type=float,
        default=0.88,
        help="商品名模糊匹配阈值，默认 0.88",
    )
    parser.add_argument(
        "--fail-on-unmatched",
        action="store_true",
        help="存在未匹配订单行时返回非 0；默认只生成报告并正常结束",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    template_path = Path(args.template)
    order_paths = [Path(path) for path in args.orders]
    output_path = Path(args.output)

    skip_keywords: list[str] = []
    if not args.no_default_skip:
        skip_keywords.extend(DEFAULT_SKIP_KEYWORDS)
    skip_keywords.extend(args.skip_keyword)

    template_items = read_template(template_path)
    order_lines = read_orders(order_paths) if order_paths else []
    result = split_orders(
        template_items,
        order_lines,
        include_template_rows=not args.orders_only,
        skip_keywords=skip_keywords,
        fuzzy_threshold=args.fuzzy_threshold,
    )

    write_purchase_import(template_path, output_path, result.lines)
    print(f"模板数据行：{result.template_rows_read}")
    print(f"订单数据行：{result.order_rows_read}")
    print(f"输出采购行：{len(result.lines)}")
    print(f"未匹配行：{len(result.unmatched)}")
    print(f"跳过行：{len(result.skipped)}")
    print(f"警告：{len(result.warnings)}")
    print(f"采购单：{output_path.resolve()}")
    return 2 if args.fail_on_unmatched and result.unmatched else 0
