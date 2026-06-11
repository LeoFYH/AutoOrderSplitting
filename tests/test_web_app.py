from __future__ import annotations

from io import BytesIO
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from auto_order_splitting import web_app
from auto_order_splitting.web_app import parse_skip_keywords


class WebAppTests(unittest.TestCase):
    def test_empty_skip_keywords_stay_empty(self):
        self.assertEqual(parse_skip_keywords(""), [])
        self.assertEqual(parse_skip_keywords(None), [])

    def test_skip_keywords_parse_multiple_values(self):
        self.assertEqual(parse_skip_keywords("营养餐，早晚餐, 食材配送"), ["营养餐", "早晚餐", "食材配送"])

    def test_supplier_annotation_endpoint_returns_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_runs_dir = web_app.RUNS_DIR
            web_app.RUNS_DIR = Path(tmp) / "runs"
            try:
                app = web_app.create_app()
                client = app.test_client()
                response = client.post(
                    "/api/supplier-annotate",
                    data={
                        "purchase": (_purchase_export_bytes(), "purchase.xlsx"),
                        "supplierKeyword": "供应商A",
                        "keepFirstCustomerUncolored": "true",
                    },
                    content_type="multipart/form-data",
                )
            finally:
                web_app.RUNS_DIR = old_runs_dir

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["summary"]["matchedRows"], 2)
        self.assertEqual(payload["summary"]["customerCount"], 2)
        self.assertIn("供应商采购单标注.xlsx", payload["downloads"]["annotated"])


def _purchase_export_bytes() -> BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "采购单导出"
    ws.append(["采购类型", "采购负责人", "采购单号", "交货日期", "商品名称", "单位", "计划采购量", "备注"])
    ws.append(["供应商/供应商A", "客户甲", "CG1", "明天", "鸡肉", "斤", 1, None])
    ws.append(["供应商/供应商A", "客户乙", "CG1", "明天", "牛肉", "斤", 2, None])
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream


if __name__ == "__main__":
    unittest.main()
