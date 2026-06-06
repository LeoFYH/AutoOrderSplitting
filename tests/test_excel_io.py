from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook, load_workbook

from auto_order_splitting.excel_io import read_orders, read_template, write_debug_workbook, write_purchase_import
from auto_order_splitting.models import PurchaseLine


class ExcelIoTests(unittest.TestCase):
    def test_reads_template_and_orders_then_writes_eight_column_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            template = tmp_path / "template.xlsx"
            orders = tmp_path / "orders.xlsx"
            output = tmp_path / "out.xlsx"

            wb = Workbook()
            ws = wb.active
            ws.append(["采购导入模板"])
            ws.append(["仓库：", "默认库房"])
            ws.append(["单据备注"])
            ws.append(["负责人", "采购员/供应商名称", "*商品名称", "*商品单位", "*采购数量", "*采购单价", "商品备注", "已设置采购协议价"])
            ws.append(["营养餐", "供应商A", "紫菜", "包", 7, 5.5, "上午到", None])
            ws.cell(1, 9, "ghost")
            wb.save(template)

            wb = Workbook()
            ws = wb.active
            ws.append(["订单号", "客户名称", "发货日期", "商品名称", "发货数量", "实际金额", "发货小计", "发货单位", "发货单价", "订单备注"])
            ws.append(["DD1", "学校A", "2026-06-08", "紫菜", 2, 11, 11, "包", 5.5, "下午到"])
            ws.append(["小计:", None, None, None, None, 11, 11, None, None, None])
            wb.save(orders)

            template_items = read_template(template)
            order_lines = read_orders([orders])
            write_purchase_import(
                template,
                output,
                [PurchaseLine("学校A", "供应商A", "紫菜", "包", Decimal("2"), 5.5, "下午到")],
            )

            self.assertEqual(len(template_items), 1)
            self.assertEqual(len(order_lines), 1)
            self.assertEqual(order_lines[0].product, "紫菜")

            written = load_workbook(output, data_only=True).active
            self.assertEqual(written.max_column, 8)
            self.assertEqual(written.cell(5, 1).value, "学校A")
            self.assertEqual(written.cell(5, 5).value, 2)

    def test_writes_debug_workbook_with_four_tabs(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "debug.xlsx"
            write_debug_workbook(
                output,
                [PurchaseLine("学校A", "供应商A", "紫菜", "包", Decimal("2"), 5.5, "下午到")],
                [],
                [],
                ["单价不同"],
            )

            wb = load_workbook(output, data_only=True)
            self.assertEqual(wb.sheetnames, ["采购结果", "未匹配", "警告", "跳过"])
            self.assertEqual(wb["采购结果"].cell(2, 1).value, "供应商A")
            self.assertEqual(wb["警告"].cell(2, 1).value, "单价不同")


if __name__ == "__main__":
    unittest.main()
