from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path

from auto_order_splitting.models import OrderLine, TemplateItem
from auto_order_splitting.splitter import split_orders


class SplitterTests(unittest.TestCase):
    def test_matches_by_owner_product_and_unit(self):
        items = [
            TemplateItem(5, "学校A", "供应商A", "紫菜", "包", Decimal("1"), 5, "上午到", None),
        ]
        orders = [
            OrderLine(2, "DD1", "学校A", None, "紫菜", Decimal("2"), None, None, "包", 5, "下午到", Path("订单.xlsx")),
        ]

        result = split_orders(items, orders, include_template_rows=False, skip_keywords=())

        self.assertEqual(len(result.lines), 1)
        self.assertEqual(result.lines[0].supplier, "供应商A")
        self.assertEqual(result.lines[0].owner, "学校A")
        self.assertEqual(result.lines[0].quantity, Decimal("2"))
        self.assertEqual(result.lines[0].price, 5)
        self.assertEqual(result.lines[0].note, "上午到")

    def test_aggregates_by_supplier_owner_product(self):
        items = [
            TemplateItem(5, "学校A", "供应商A", "鸡排腿", "斤", Decimal("0"), 8, "上午到", None),
        ]
        orders = [
            OrderLine(2, "DD1", "学校A", None, "鸡排腿", Decimal("2"), None, None, "斤", 8, "上午到", Path("订单1.xlsx")),
            OrderLine(3, "DD2", "学校A", None, "鸡排腿", Decimal("3"), None, None, "斤", 8, "下午到", Path("订单2.xlsx")),
        ]

        result = split_orders(items, orders, include_template_rows=False, skip_keywords=())

        self.assertEqual(len(result.lines), 1)
        self.assertEqual(result.lines[0].quantity, Decimal("5"))
        self.assertEqual(result.lines[0].note, "上午到")
        self.assertEqual(len(result.warnings), 0)

    def test_reports_unmatched_without_dropping_silently(self):
        result = split_orders(
            [TemplateItem(5, "学校A", "供应商A", "紫菜", "包", Decimal("0"), 5, "", None)],
            [OrderLine(2, "DD1", "学校A", None, "不存在商品", Decimal("1"), None, None, "斤", None, "", Path("订单.xlsx"))],
            include_template_rows=False,
            skip_keywords=(),
        )

        self.assertEqual(result.lines, [])
        self.assertEqual(len(result.unmatched), 1)
        self.assertEqual(result.unmatched[0].product, "不存在商品")

    def test_unit_mismatch_is_unmatched_to_avoid_wrong_price(self):
        result = split_orders(
            [TemplateItem(5, "学校A", "供应商A", "胡辣汤", "包", Decimal("0"), 13, "", None)],
            [OrderLine(2, "DD1", "学校A", None, "胡辣汤", Decimal("1"), None, None, "件", 130, "", Path("订单.xlsx"))],
            include_template_rows=False,
            skip_keywords=(),
        )

        self.assertEqual(result.lines, [])
        self.assertEqual(len(result.unmatched), 1)
        self.assertIn("单位", result.unmatched[0].reason)

    def test_owner_specific_template_row_wins_for_duplicate_product(self):
        items = [
            TemplateItem(5, "学校A", "供应商A", "猪肉", "斤", Decimal("0"), 8, "上午", None),
            TemplateItem(6, "学校B", "供应商B", "猪肉", "斤", Decimal("0"), 9, "下午", None),
        ]
        orders = [
            OrderLine(2, "DD1", "学校B", None, "猪肉", Decimal("3"), None, None, "斤", 9, "下午", Path("订单.xlsx")),
        ]

        result = split_orders(items, orders, include_template_rows=False, skip_keywords=())

        self.assertEqual(len(result.lines), 1)
        self.assertEqual(result.lines[0].supplier, "供应商B")
        self.assertEqual(result.lines[0].price, 9)
        self.assertEqual(result.lines[0].quantity, Decimal("3"))

    def test_never_falls_back_to_other_school(self):
        items = [
            TemplateItem(5, "学校A", "供应商A", "猪肉", "斤", Decimal("0"), 8, "上午", None),
        ]
        orders = [
            OrderLine(2, "DD1", "学校B", None, "猪肉", Decimal("3"), None, None, "斤", 9, "下午", Path("订单.xlsx")),
        ]

        result = split_orders(items, orders, include_template_rows=False, skip_keywords=())

        self.assertEqual(result.lines, [])
        self.assertEqual(len(result.unmatched), 1)
        self.assertIn("学校", result.unmatched[0].reason)

    def test_uses_order_supplier_when_template_has_no_match(self):
        items = [
            TemplateItem(5, "学校A", "供应商A", "猪肉", "斤", Decimal("0"), 8, "上午", None),
        ]
        orders = [
            OrderLine(
                2,
                "DD1",
                "学校B",
                None,
                "猪肉",
                Decimal("3"),
                None,
                None,
                "斤",
                9,
                "下午",
                Path("订单.xlsx"),
                supplier="订单供应商B",
            ),
        ]

        result = split_orders(items, orders, include_template_rows=False, skip_keywords=())

        self.assertEqual(len(result.unmatched), 0)
        self.assertEqual(len(result.lines), 1)
        self.assertEqual(result.lines[0].supplier, "订单供应商B")
        self.assertEqual(result.lines[0].owner, "学校B")
        self.assertEqual(result.lines[0].product, "猪肉")
        self.assertEqual(result.lines[0].price, 9)

    def test_skip_keywords_match_school_field(self):
        items = [
            TemplateItem(5, "营养餐", "供应商A", "紫菜", "包", Decimal("7"), 5, "上午到", None),
        ]
        orders = [
            OrderLine(2, "DD1", "光山县一中-早晚餐", None, "紫菜", Decimal("2"), None, None, "包", 6, "下午到", Path("订单.xlsx")),
        ]

        result = split_orders(items, orders, include_template_rows=True, skip_keywords=("营养餐、早晚餐",))

        self.assertEqual(result.lines, [])
        self.assertEqual(len(result.skipped), 1)
        self.assertIn("早晚餐", result.skipped[0].reason)

    def test_skip_keywords_do_not_match_product_or_note(self):
        items = [
            TemplateItem(5, "学校A", "供应商A", "紫菜", "包", Decimal("0"), 5, "", None),
        ]
        orders = [
            OrderLine(2, "DD1", "学校B", None, "营养餐紫菜", Decimal("2"), None, None, "包", 5, "早晚餐送", Path("订单.xlsx")),
        ]

        result = split_orders(items, orders, include_template_rows=False, skip_keywords=("营养餐", "早晚餐"))

        self.assertEqual(result.lines, [])
        self.assertEqual(len(result.skipped), 0)
        self.assertEqual(len(result.unmatched), 1)
        self.assertIn("学校", result.unmatched[0].reason)

    def test_out_of_scope_school_is_unmatched_when_template_has_skip_owner(self):
        items = [
            TemplateItem(5, "营养餐", "供应商N", "紫菜", "包", Decimal("0"), 5, "", None),
            TemplateItem(6, "学校A", "供应商A", "紫菜", "包", Decimal("0"), 5, "", None),
        ]
        orders = [
            OrderLine(2, "DD1", "学校B", None, "紫菜", Decimal("2"), None, None, "包", 5, "", Path("订单.xlsx")),
        ]

        result = split_orders(items, orders, include_template_rows=False)

        self.assertEqual(result.lines, [])
        self.assertEqual(len(result.skipped), 0)
        self.assertEqual(len(result.unmatched), 1)
        self.assertIn("学校", result.unmatched[0].reason)


if __name__ == "__main__":
    unittest.main()
